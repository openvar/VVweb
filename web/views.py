# web/views.py

from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.http import HttpResponse, Http404
from . import forms
from . import tasks
from . import services
from .object_pool import vval_object_pool, g2t_object_pool
from .utils import render_to_pdf
import VariantValidator
from VariantValidator import settings as vvsettings
import vvhgvs
from configparser import ConfigParser
from celery.result import AsyncResult
import codecs
import sys
import traceback
from web.models import VariantQuota
import logging
from allauth.account.views import EmailVerificationSentView, SignupView, LoginView
from allauth.account.utils import send_email_confirmation
from allauth.account.models import EmailAddress
from django.contrib import messages

print("Imported views and creating Validator Obj - SHOULD ONLY SEE ME ONCE")
logger = logging.getLogger("vv")


# ======================================================================
# BASIC PAGES
# ======================================================================

def home(request):
    config = ConfigParser()
    config.read(vvsettings.CONFIG_DIR)

    versions = {
        "VariantValidator": VariantValidator.__version__,
        "hgvs": vvhgvs.__version__,
        "uta": config["postgres"]["version"],
        "seqrepo": config["seqrepo"]["version"],
        "vvdb": config["mysql"]["version"],
    }

    return render(request, "home.html", {"versions": versions})


def about(request):
    return redirect("https://github.com/openvar/variantValidator/blob/master/README.md")


def contact(request):
    form = forms.ContactForm()

    if request.method == "POST":
        form = forms.ContactForm(request.POST)
        if form.is_valid():
            my_contact = form.save()
            services.send_contact_email(my_contact)
            messages.success(request, "Message sent")
            logger.info("Contact from %s made" % my_contact.emailval)
            return redirect("contact")

    return render(request, "contact.html", {"form": form})


def nomenclature(request):
    return render(request, "nomenclature.html")


def instructions(request):
    return redirect("https://github.com/openvar/VV_databases/blob/master/markdown/instructions.md")


def faqs(request):
    return render(request, "faqs.html")


# ======================================================================
# GENE TO TRANSCRIPTS
# ======================================================================

def genes_to_transcripts(request):
    output = False

    if request.method == "POST":
        symbol = request.POST.get("symbol")
        select_transcripts = request.POST.get("transcripts")
        reference_source = request.POST.get("refsource", "refseq")

        if not select_transcripts:
            select_transcripts = "all"

        validator = g2t_object_pool.get_object()
        output = tasks.gene2transcripts(
            symbol,
            validator=validator,
            select_transcripts=select_transcripts,
            transcript_set=reference_source,
        )
        g2t_object_pool.return_object(validator)

        if "transcripts" in output:
            for trans in output["transcripts"]:
                if trans["reference"].startswith("LRG"):
                    trans["url"] = (
                        "http://ftp.ebi.ac.uk/pub/databases/lrgex/"
                        + trans["reference"].split("t")[0]
                        + ".xml"
                    )
                else:
                    trans["url"] = "https://www.ncbi.nlm.nih.gov/nuccore/" + trans["reference"]

    return render(request, "genes_to_transcripts.html", {"output": output})


# ======================================================================
# VALIDATE VIEW
# ======================================================================

def validate(request):
    output = False
    locked = False
    num = int(request.session.get("validations", 0))
    last_genome = request.session.get("genome", None)
    last_source = request.session.get("refsource", None)

    if request.method == "GET":
        return render(
            request,
            "validate.html",
            {
                "variant": request.GET.get("variant"),
                "genome": request.GET.get("genomebuild", "GRCh38"),
                "select_transcripts": request.GET.get("transcripts"),
                "transcripts": request.GET.get("transcripts"),
                "from_get": True,
                "autosubmit": request.GET.get("autosubmit", "false"),
                "source": request.GET.get("refsource", "refseq"),
            },
        )

    if request.method == "POST":
        if request.user.is_authenticated or num < 5:
            variant = request.POST.get("variant")
            genome = request.POST.get("genomebuild", "GRCh38")
            source = request.POST.get("refsource", "refseq")
            select_transcripts = request.POST.get("transcripts")
            pdf_r = request.POST.get("pdf_request")

            if pdf_r in (None, "True"):
                pdf_r = True
            else:
                pdf_r = False

            if not select_transcripts or select_transcripts == "transcripts":
                select_transcripts = "all"

            # --- QUOTA CHECK ---
            if request.user.is_authenticated:
                try:
                    quota, _ = VariantQuota.objects.get_or_create(user=request.user)
                    quota.add_variants(1)
                except ValueError:
                    messages.error(
                        request,
                        f"You have reached your monthly variant validation limit ({quota.effective_allowance}).",
                    )
                    return render(
                        request,
                        "validate.html",
                        {
                            "output": output,
                            "locked": True,
                            "last": last_genome,
                            "source": last_source,
                            "initial": variant,
                        },
                    )
                except Exception as e:
                    logger.error(f"Quota failure for user {request.user.id}: {e}")
                    messages.error(request, "Unable to track your submission quota.")
                    return render(
                        request,
                        "validate.html",
                        {
                            "output": output,
                            "locked": True,
                            "last": last_genome,
                            "source": last_source,
                            "initial": variant,
                        },
                    )

            # --- VALIDATE TASK ---
            validator = vval_object_pool.get_object()
            output = tasks.validate(variant, genome, select_transcripts, validator=validator, transcript_set=source)
            output = services.process_result(output, validator)
            output["genome"] = genome
            output["source"] = source

            request.session["genome"] = genome
            request.session["source"] = source

            ucsc_link = services.get_ucsc_link(validator, output)
            varsome_link = services.get_varsome_link(output)
            gnomad_link = services.get_gnomad_link(output)

            vval_object_pool.return_object(validator)

            # PDF
            if pdf_r:
                config = ConfigParser()
                config.read(vvsettings.CONFIG_DIR)
                versions = {
                    "VariantValidator": VariantValidator.__version__,
                    "hgvs": vvhgvs.__version__,
                    "uta": config["postgres"]["version"],
                    "seqrepo": config["seqrepo"]["version"],
                    "vvdb": config["mysql"]["version"],
                }
                context = {"output": output, "versions": versions}
                pdf = render_to_pdf(request, "pdf_results.html", context)

                if pdf:
                    response = HttpResponse(pdf, content_type="application/pdf")
                    filename = f"VariantValidator_report_{variant}.pdf"
                    content = f"inline; filename={filename}"
                    if request.GET.get("download"):
                        content = f"attachment; filename={filename}"
                    response["Content-Disposition"] = content
                    return response

                return HttpResponse("PDF generation error")

            # Count requests if anonymous
            if not request.user.is_authenticated:
                num += 1
                request.session["validations"] = num

            return render(
                request,
                "validate_results.html",
                {
                    "output": output,
                    "ucsc": ucsc_link,
                    "varsome": varsome_link,
                    "gnomad": gnomad_link,
                },
            )

    # --- ANONYMOUS LOCKOUT WARNINGS ---
    if not request.user.is_authenticated:
        login_page = reverse("account_login")
        here = reverse("validate")

        if num < 5:
            remaining = 5 - num
            if num == 4:
                messages.warning(
                    request,
                    f"<span id='msg-body'>Warning: Only <span id='msg-valnum'>{remaining}</span> more submission allowed. "
                    f"For unlimited access please <a href='{login_page}?next={here}' class='alert-link'>login</a>.</span>",
                )
            else:
                messages.warning(
                    request,
                    f"<span id='msg-body'>Warning: Only <span id='msg-valnum'>{remaining}</span> more submissions allowed. "
                    f"For unlimited access please <a href='{login_page}?next={here}' class='alert-link'>login</a>.</span>",
                )
        else:
            messages.error(
                request,
                f"<span id='msg-body'>Please <a href='{login_page}?next={here}' class='alert-link'>login</a> to continue using this service</span>",
            )
            locked = True

    return render(
        request,
        "validate.html",
        {
            "output": output,
            "locked": locked,
            "last": last_genome,
            "source": last_source,
            "initial": request.GET.get("variant"),
        },
    )


# ======================================================================
# BATCH VALIDATION
# ======================================================================

def batch_validate(request):
    locked = False
    last_genome = request.session.get("genome", None)

    if request.method == "POST":
        form = forms.BatchValidateForm(request.POST, request=request)
        if form.is_valid():
            job = tasks.batch_validate.delay(
                form.cleaned_data["input_variants"],
                form.cleaned_data["genome"],
                form.cleaned_data["email_address"],
                form.cleaned_data["gene_symbols"],
                form.cleaned_data["select_transcripts"],
                options=form.cleaned_data["options"],
                transcript_set=form.cleaned_data["refsource"],
            )
            messages.success(
                request,
                "Success! Validated variants will be emailed to you (Job ID: %s)" % job,
            )
            services.send_initial_email(form.cleaned_data["email_address"], job, "validation")
            logger.info("Batch validation submitted by user %s" % request.user)
            request.session["genome"] = form.cleaned_data["genome"]
            return redirect("batch_validate")

        messages.warning(request, "Form contains errors. Please resubmit.")

    else:
        form = forms.BatchValidateForm(request=request)

        if not request.user.is_authenticated:
            login_page = reverse("account_login")
            here = reverse("batch_validate")

            messages.error(
                request,
                f"You must be <a href='{login_page}?next={here}' class='alert-link'>logged in</a> to submit batch jobs.",
            )
            for f in form.fields.values():
                f.disabled = True
            locked = True

        else:
            form.fields["genome"].initial = last_genome
            email_address = getattr(request.user, "email")

            email_obj = EmailAddress.objects.filter(email__iexact=email_address).first()

            if email_obj and email_obj.verified:
                form.fields["email_address"].initial = email_obj.email
            else:
                for f in form.fields.values():
                    f.disabled = True
                verify = reverse("account_email")
                messages.error(
                    request,
                    f"Primary email must be <a href='{verify}' class='alert-link'>verified</a> before batch submission.",
                )
                locked = True

    return render(
        request,
        "batch_validate.html",
        {"form": form, "locked": locked, "settings": settings},
    )


# ======================================================================
# VCF2HGVS (left unchanged, even if unused)
# ======================================================================

def vcf2hgvs(request):
    locked = False
    last_genome = request.session.get("genome", None)

    if request.method == "POST":
        form = forms.VCF2HGVSForm(request.POST, request.FILES)
        if form.is_valid():
            if request.FILES["vcf_file"].multiple_chunks():
                jobs = []
                for chunk in request.FILES["vcf_file"].chunks():
                    res = tasks.vcf2hgvs.delay(
                        chunk,
                        form.cleaned_data["genome"],
                        form.cleaned_data["gene_symbols"],
                        form.cleaned_data["email_address"],
                    )
                    jobs.append(str(res))
                res = ", ".join(jobs)
            else:
                try:
                    res = tasks.vcf2hgvs.delay(
                        codecs.decode(request.FILES["vcf_file"].read(), "UTF-8"),
                        form.cleaned_data["gene_symbols"],
                        form.cleaned_data["email_address"],
                        form.cleaned_data["genome"],
                        form.cleaned_data["select_transcripts"],
                        form.cleaned_data["options"],
                    )
                except Exception:
                    res = tasks.vcf2hgvs.delay(
                        request.FILES["vcf_file"].read(),
                        form.cleaned_data["gene_symbols"],
                        form.cleaned_data["email_address"],
                        form.cleaned_data["genome"],
                        form.cleaned_data["select_transcripts"],
                        form.cleaned_data["options"],
                    )

            messages.success(request, "Success! Your VCF job has been submitted.")
            services.send_initial_email(form.cleaned_data["email_address"], res, "VCF to HGVS")
            request.session["genome"] = form.cleaned_data["genome"]
            return redirect("vcf2hgvs")

        messages.warning(request, "Form error. Please correct and resubmit.")

    else:
        form = forms.VCF2HGVSForm()

        if not request.user.is_authenticated:
            login_page = reverse("account_login")
            here = reverse("vcf2hgvs")

            messages.error(
                request,
                f"You must be <a href='{login_page}?next={here}' class='alert-link'>logged in</a> to submit VCF jobs.",
            )
            for f in form.fields.values():
                f.disabled = True
            locked = True

        else:
            form.fields["genome"].initial = last_genome
            email_address = getattr(request.user, "email")

            email_obj = EmailAddress.objects.filter(email__iexact=email_address).first()

            if email_obj and email_obj.verified:
                form.fields["email_address"].initial = email_obj.email
            else:
                for f in form.fields.values():
                    f.disabled = True
                verify = reverse("account_email")
                messages.error(
                    request,
                    f"Primary email must be <a href='{verify}' class='alert-link'>verified</a> before VCF job submission.",
                )
                locked = True

    return render(
        request,
        "vcf_to_hgvs.html",
        {"form": form, "max": settings.MAX_VCF, "locked": locked},
    )


# ======================================================================
# DOWNLOAD BATCH RESULTS
# ======================================================================

def download_batch_res(request, job_id):
    job = AsyncResult(job_id)
    buffer = f"# Job ID:{job_id}\n"

    try:
        # Determine which columns to include based on metadata
        metaline = ""
        for row in job.result:
            if "Metadata:" in str(row):
                metaline = str(row)

        transcript_d = "transcript" in metaline
        genomic_d = "genomic" in metaline
        protein_d = "protein" in metaline
        refseqgene_d = "refseqgene" in metaline
        lrg_d = "lrg" in metaline
        vcf_d = "vcf" in metaline
        gene_info_d = "gene_info" in metaline
        tx_name_d = "tx_name" in metaline
        alt_loci_d = "alt_loci" in metaline

        my_results = []
        for row in job.result:
            if not isinstance(row, list):
                my_results.append(row)
                continue

            out = row[0:2]  # basic fields
            if transcript_d:
                out += row[2:5]
            if refseqgene_d:
                out += row[5:7]
            if lrg_d:
                out += row[7:9]
            if protein_d:
                out.append(row[9])
            if genomic_d:
                out.append(row[10])
                out.append(row[16])
            if vcf_d:
                out += row[11:16]
                out += row[17:22]
            if gene_info_d:
                out += row[22:24]
            if tx_name_d:
                out.append(row[24])
            if alt_loci_d:
                out.append(row[25])

            my_results.append(out)

        for row in my_results:
            if isinstance(row, list):
                buffer += "\t".join(["None" if v is None else str(v) for v in row])
            else:
                buffer += str(row)
            buffer += "\n"

    except Exception as ex:
        exc_type, exc_value, last_traceback = sys.exc_info()
        logger.error(f"{exc_type} {exc_value}")
        traceback.print_tb(last_traceback, file=sys.stdout)

    response = HttpResponse(buffer, content_type="text/plain")
    response["Content-Disposition"] = "attachment; filename=batch_job.txt"
    return response


# ======================================================================
# BED FILE OUTPUT
# ======================================================================

def bed_file(request):
    info = request.GET.get("variant")
    if info is None:
        raise Http404("BED file requires input variants")

    input_elements = info.split("|")
    if "+" in input_elements[0]:
        input_elements[0] = input_elements[0].replace(" ", "+")

    validator = vval_object_pool.get_object()
    bed_call = services.create_bed_file(validator, *input_elements)
    vval_object_pool.return_object(validator)

    return HttpResponse(bed_call, content_type="text/plain; charset=utf-8")


# ======================================================================
# CUSTOM EMAIL VIEWS
# ======================================================================

class StyledEmailSentView(EmailVerificationSentView):
    template_name = "account/email_confirmation_sent.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["email"] = self.request.session.get(
            "account_email",
            self.request.GET.get("email", "your email"),
        )
        return ctx



class StyledSignupView(SignupView):
    """
    Custom signup:
    • Lowercase email BEFORE user is created.
    • Ensure EmailAddress exists (Allauth requirement).
    • Always send confirmation email.
    """

    def form_valid(self, form):
        # Normalize email
        email = form.cleaned_data.get("email", "").lower().strip()
        form.cleaned_data["email"] = email

        # Let Allauth create the user
        response = super().form_valid(form)

        user = self.user  # Allauth sets self.user after super()

        # ============================================================
        # ENSURE EmailAddress EXISTS — THIS FIXES YOUR WHOLE SYSTEM
        # ============================================================
        email_obj, created = EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={"primary": True, "verified": False},
        )

        # Guarantee correct state
        email_obj.primary = True
        email_obj.verified = False
        email_obj.save()

        # ============================================================
        # SEND CONFIRMATION EMAIL (Allauth’s proper function)
        # ============================================================
        send_email_confirmation(self.request, user)

        # Store email in session (your original behaviour)
        self.request.session["account_email"] = email

        return response



class StrictLoginView(LoginView):
    """
    Enforces:
    • Lowercase login input
    • Lowercase stored user.email
    • Verified-primary-email requirement
    """

    def post(self, request, *args, **kwargs):
        if request.method == "POST":
            request.POST = request.POST.copy()
            if "login" in request.POST and request.POST["login"]:
                request.POST["login"] = request.POST["login"].lower().strip()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.user

        # Normalize stored email
        lowered = (user.email or "").lower().strip()
        if user.email != lowered:
            user.email = lowered
            user.save(update_fields=["email"])

        # Verified?
        email_address = EmailAddress.objects.filter(
            user=user, email__iexact=user.email
        ).first()

        if email_address and not email_address.verified:
            send_email_confirmation(self.request, user)
            self.request.session["account_email"] = lowered
            messages.error(
                self.request,
                "Your email address is not verified. A new confirmation email has been sent.",
            )
            return redirect("account_email_verification_sent")

        return super().form_valid(form)

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>