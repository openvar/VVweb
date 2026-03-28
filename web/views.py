# web/views.py
from allauth.account.views import SignupView, LoginView
from allauth.account.utils import send_email_confirmation
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from .object_pool import vval_object_pool, g2t_object_pool
from .utils import render_to_pdf
import VariantValidator
from VariantValidator import settings as vvsettings
import vvhgvs
from configparser import ConfigParser
from celery.result import AsyncResult
import sys
import traceback
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from allauth.account.models import EmailAddress
from django.conf import settings
import logging
from . import forms
from . import tasks
from . import services
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


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


@login_required
# ======================================================================
# GENE TO TRANSCRIPTS
# ======================================================================

def genes_to_transcripts(request):
    """
    Synchronous gene → transcripts lookup.
    Uses the g2t_object_pool as originally intended.
    """

    output = False

    if request.method == "POST":
        logger.debug("Gene2Trans submitted")

        symbol = request.POST.get('symbol')
        select_transcripts = request.POST.get('transcripts') or "all"
        reference_source = request.POST.get('refsource', 'refseq')

        # Acquire validator from pool
        validator = g2t_object_pool.get_object()

        try:
            # PURELY SYNCHRONOUS — DO NOT USE CELERY HERE
            output = tasks.gene2transcripts(
                symbol,
                validator=validator,
                select_transcripts=select_transcripts,
                transcript_set=reference_source
            )

        except Exception as e:
            logger.error(f"Gene2Transcripts error: {e}")
            output = {"error": str(e)}

        finally:
            # Always return validator to pool
            g2t_object_pool.return_object(validator)

        # Add URLs for UI
        if isinstance(output, dict) and 'transcripts' in output:
            for trans in output['transcripts']:
                ref = trans['reference']
                if ref.startswith('LRG'):
                    xml_id = ref.split('t')[0]
                    trans['url'] = f"http://ftp.ebi.ac.uk/pub/databases/lrgex/{xml_id}.xml"
                else:
                    trans['url'] = f"https://www.ncbi.nlm.nih.gov/nuccore/{ref}"

    return render(request, "genes_to_transcripts.html", {"output": output})


def validate(request):
    """
    Interactive single-variant validator.
    Allows 5 free anonymous validations, then requires login.
    Runs synchronously using validator pool (NOT Celery).
    """
    output = False
    locked = False

    # Track anonymous usage
    num = int(request.session.get('validations', 0))

    last_genome = request.session.get('genome', None)
    last_source = request.session.get('refsource', None)

    # ------------------------------------------------------------------
    # GET — render input form
    # ------------------------------------------------------------------
    if request.method == 'GET':
        variant = request.GET.get('variant')
        genome = request.GET.get('genomebuild', 'GRCh38')
        select_transcripts = request.GET.get('transcripts')
        source = request.GET.get('refsource', 'refseq')
        autosubmit = request.GET.get('autosubmit', 'false')

        return render(request, 'validate.html', {
            'variant': variant,
            'genome': genome,
            'select_transcripts': select_transcripts,
            'transcripts': select_transcripts,
            'from_get': True,
            'autosubmit': autosubmit,
            'source': source,
        })

    # ------------------------------------------------------------------
    # POST — perform validation
    # ------------------------------------------------------------------
    if request.method == 'POST':

        # Free anonymous limit
        if not request.user.is_authenticated and num >= 5:
            login_page = reverse('account_login')
            here = reverse('validate')

            messages.error(request,
                           f"Please <a href='{login_page}?next={here}' class='alert-link'>login</a> to continue.")
            locked = True
            return render(request, 'validate.html', {
                'output': None,
                'locked': True
            })

        logger.debug("Running interactive validate()")

        variant = request.POST.get('variant')
        genome = request.POST.get('genomebuild', 'GRCh38')
        source = request.POST.get('refsource', 'refseq')

        # Select transcripts
        select_transcripts = request.POST.get('transcripts')
        if not select_transcripts or select_transcripts in ['all', 'transcripts']:
            select_transcripts = 'all'

        pdf_request = request.POST.get('pdf_request')

        # Acquire validator
        validator = vval_object_pool.get_object()

        try:
            # Synchronous variant validation
            raw = validator.validate(
                variant,
                genome,
                select_transcripts,
                transcript_set=source,
                lovd_syntax_check=True,
            )

            raw_dict = raw.format_as_dict()
            output = services.process_result(raw_dict, validator)
            output['genome'] = genome
            output['source'] = source

            # Save user settings
            request.session['genome'] = genome
            request.session['refsource'] = source

            # External links
            ucsc_link = services.get_ucsc_link(validator, output)
            varsome_link = services.get_varsome_link(output)
            gnomad_link = services.get_gnomad_link(output)

        except Exception as e:
            logger.error(f"validate() failed: {e}")
            return render(request, 'validate.html', {
                'output': None,
                'locked': False,
                'error': str(e),
            })
        finally:
            # Always return validator to pool
            vval_object_pool.return_object(validator)

        # Count anonymous submissions
        if not request.user.is_authenticated:
            num += 1
            request.session['validations'] = num

        # ----- PDF generation -----
        if pdf_request and pdf_request != "False":
            config = ConfigParser()
            config.read(vvsettings.CONFIG_DIR)
            versions = {
                'VariantValidator': VariantValidator.__version__,
                'hgvs': vvhgvs.__version__,
                'uta': config['postgres']['version'],
                'seqrepo': config['seqrepo']['version'],
                'vvdb': config['mysql']['version']
            }
            pdf = render_to_pdf(request, 'pdf_results.html',
                                {'output': output, 'versions': versions})

            if pdf:
                response = HttpResponse(pdf, content_type='application/pdf')
                filename = f"VariantValidator_report_{variant}.pdf"
                disposition = f"inline; filename={filename}"
                if request.GET.get("download"):
                    disposition = f"attachment; filename={filename}"
                response['Content-Disposition'] = disposition
                return response

            return HttpResponse("Could not generate PDF")

        # Render results
        return render(request, 'validate_results.html', {
            'output': output,
            'ucsc': ucsc_link,
            'varsome': varsome_link,
            'gnomad': gnomad_link,
        })

    # ------------------------------------------------------------------
    # Fallback for non-GET/POST (rare)
    # ------------------------------------------------------------------
    return render(request, 'validate.html', {
        'output': output,
        'locked': locked,
        'last': last_genome,
        'source': last_source,
    })

# ======================================================================
# BATCH VALIDATION
# ======================================================================

def batch_validate(request):
    """
    Secure Batch Validator View.
    Authenticated + email-verified users only.
    Uses Celery to run long batch jobs asynchronously.
    """

    locked = False
    last_genome = request.session.get('genome')

    # ------------------------------------------------------------------
    # POST — Submit batch job
    # ------------------------------------------------------------------
    if request.method == 'POST':

        # Must be logged in
        if not request.user.is_authenticated:
            return redirect('account_login')

        # Must have a primary email
        email_address = getattr(request.user, 'email', None)
        if not email_address:
            messages.error(request, "Your account does not have a valid email address.")
            return redirect('account_email')

        # Must be verified
        try:
            email_obj = EmailAddress.objects.get(user=request.user, email=email_address)
            if not email_obj.verified:
                messages.error(request, "You must verify your email before submitting batch jobs.")
                return redirect('account_email')
        except EmailAddress.DoesNotExist:
            messages.error(request, "Your email address is not registered or verified.")
            return redirect('account_email')

        # Process form
        form = forms.BatchValidateForm(request.POST)

        if form.is_valid():

            real_email = request.user.email  # ALWAYS authenticated email
            user_id = request.user.id

            # Submit async job

            job = tasks.batch_validate.delay(
                variant=form.cleaned_data['input_variants'],
                genome=form.cleaned_data['genome'],
                email=real_email,
                gene_symbols=form.cleaned_data['gene_symbols'],
                transcripts=form.cleaned_data['select_transcripts'],
                options=form.cleaned_data['options'],
                transcript_set=form.cleaned_data['refsource'],
                user_id=user_id)

            # Notify user
            services.send_initial_email(real_email, job, 'validation')
            messages.success(request, f"Success! Job ID: {job}")

            logger.info(f"Batch job submitted: user_id={user_id}, job={job}")

            request.session['genome'] = form.cleaned_data['genome']
            return redirect('batch_validate')

        messages.warning(request, "Form contains errors. Please fix them below.")

    # ------------------------------------------------------------------
    # GET — render form
    # ------------------------------------------------------------------
    else:
        form = forms.BatchValidateForm()

        if not request.user.is_authenticated:
            # Disable whole form
            for field in form.fields.values():
                field.disabled = True
            messages.error(request, "You must be logged in to submit batch jobs.")
            locked = True

        else:
            form.fields['genome'].initial = last_genome

            try:
                email_obj = EmailAddress.objects.get(user=request.user, email=request.user.email)

                if email_obj.verified:
                    form.fields['email_address'].initial = email_obj.email
                else:
                    for field in form.fields.values():
                        field.disabled = True
                    messages.error(request, "Primary email must be verified first.")
                    locked = True

            except EmailAddress.DoesNotExist:
                for field in form.fields.values():
                    field.disabled = True
                messages.error(request, "Primary email must be verified first.")
                locked = True

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    return render(request, 'batch_validate.html', {
        'form': form,
        'locked': locked,
        'settings': settings,
    })

def download_batch_res(request, job_id):
    """
    Download batch validator results as a text file.
    Fully updated to handle new Celery result format:
    {
        "result": [...table rows...],
        "user_id": ...,
        "email": ...,
        ...
    }
    """

    job = AsyncResult(job_id)

    buffer = ""
    buffer += '# Job ID:%s\n' % job_id

    try:
        # ------------------------------------------------------------------
        # NEW: Extract actual table rows from Celery result
        # ------------------------------------------------------------------
        raw = job.result

        # If Celery returns raw JSON string, decode it
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}

        # The real table is stored at raw["result"]
        table = raw.get("result", [])

        # ------------------------------------------------------------------
        # Handle empty or malformed results
        # ------------------------------------------------------------------
        if not isinstance(table, list) or not table:
            buffer += "# ERROR: Batch results missing or malformed.\n"
            response = HttpResponse(buffer, content_type='text/plain')
            response['Content-Disposition'] = 'attachment; filename=batch_job.txt'
            return response

        # ------------------------------------------------------------------
        # Find metadata line (first row containing "Metadata:")
        # ------------------------------------------------------------------
        metaline = ""
        for row in table:
            if "Metadata:" in str(row):
                metaline = str(row)
                break

        # ------------------------------------------------------------------
        # Parse metadata for option flags
        # ------------------------------------------------------------------
        transcript_d  = "transcript"  in metaline
        genomic_d     = "genomic"     in metaline
        protein_d     = "protein"     in metaline
        refseqgene_d  = "refseqgene"  in metaline
        lrg_d         = "lrg"         in metaline
        vcf_d         = "vcf"         in metaline
        gene_info_d   = "gene_info"   in metaline
        tx_name_d     = "tx_name"     in metaline
        alt_loci_d    = "alt_loci"    in metaline

        # ------------------------------------------------------------------
        # Build output rows based on selected options
        # ------------------------------------------------------------------
        my_results = []

        for row in table:

            # Metadata row?
            if isinstance(row, str) or "# Metadata" in str(row):
                my_results.append(row)
                continue

            # Convert non-list rows safely
            if not isinstance(row, list):
                row = [str(row)]

            # Defensive: ensure row has enough elements for slicing
            row = [str(x) if x is not None else "" for x in row]
            while len(row) < 26:
                row.append("")

            output = []

            # Always include: variant + warnings
            output += row[0:2]

            if transcript_d:
                output += row[2:5]

            if refseqgene_d:
                output += row[5:7]

            if lrg_d:
                output += row[7:9]

            if protein_d:
                output.append(row[9])

            if genomic_d:
                output.append(row[10])
                output.append(row[16])

            if vcf_d:
                output += row[11:16]
                output += row[17:22]

            if gene_info_d:
                output += row[22:24]

            if tx_name_d:
                output.append(row[24])

            if alt_loci_d:
                output.append(row[25])

            my_results.append(output)

        # ------------------------------------------------------------------
        # Write output rows to response buffer
        # ------------------------------------------------------------------
        for row in my_results:
            if isinstance(row, list):
                buffer += "\t".join(["None" if v in (None, "") else v for v in row])
            else:
                buffer += str(row)
            buffer += "\n"

    except Exception:
        exc_type, exc_value, tb = sys.exc_info()
        logger.error("%s %s" % (exc_type, exc_value))
        traceback.print_tb(tb)
        buffer += "\n# ERROR: Failed to process results.\n"

    # ----------------------------------------------------------------------
    # Return final response
    # ----------------------------------------------------------------------
    response = HttpResponse(buffer, content_type="text/plain")
    response['Content-Disposition'] = 'attachment; filename=batch_job.txt'
    logger.debug("Job %s results downloaded by user %s" % (job_id, request.user))
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

class StyledEmailSentView(LoginRequiredMixin, TemplateView):
    template_name = "account/email_confirmation_sent.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # address for the template
        ctx["email_to_show"] = self.request.session.get(
            "account_email",
            self.request.user.email if self.request.user.is_authenticated else None,
        )
        # for copy switching and banners
        ctx["annual"] = (self.request.GET.get("annual") == "1")
        ctx["resent"] = (self.request.GET.get("resent") == "1")


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
    Routing on login:
      • Reset account (admin/auto): terms=None & reset_reason in {'admin','auto'}
          - unverified -> /accounts/confirm-email/
          - verified   -> /verify/
      • True new user: terms=None & reset_reason is None
          - unverified -> /accounts/confirm-email/
          - verified   -> normal success
      • Otherwise (terms set): keep normal success path (or your existing logic)
    """

    def post(self, request, *args, **kwargs):
        # Normalize the username/email the user types into the login form
        if request.method == "POST":
            data = request.POST.copy()
            if "login" in data and data["login"]:
                data["login"] = data["login"].lower().strip()
            request.POST = data
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.user

        # Normalize stored email on login
        lowered = (user.email or "").lower().strip()
        if user.email != lowered:
            user.email = lowered
            user.save(update_fields=["email"])

        # Ensure an EmailAddress row exists and is primary
        # (no auto-send here; we’re only routing)
        ea = EmailAddress.objects.filter(user=user, email__iexact=lowered).order_by("-primary").first()
        if not ea:
            ea = EmailAddress.objects.create(user=user, email=lowered, primary=True, verified=False)
        elif not ea.primary:
            ea.primary = True
            ea.save(update_fields=["primary"])

        # Make the email available to the confirm page
        self.request.session["account_email"] = lowered

        # *** Log the user in FIRST so subsequent redirects are authenticated
        response = super().form_valid(form)

        # Snapshot Allauth/ Profile state
        is_verified_now = EmailAddress.objects.filter(user=user, verified=True).exists()
        profile = getattr(user, "profile", None)
        terms = getattr(profile, "terms_accepted_at", None)
        reset_reason = getattr(profile, "reset_reason", None)

        # ---------------------------
        # TERMS == None  (new OR reset)
        # ---------------------------
        if terms is None:
            # (A) Reset account (admin/auto)
            if reset_reason in {"admin", "auto"}:
                if not is_verified_now:
                    return redirect(reverse("account_email_verification_sent"))
                return redirect("/verify/")

            # (B) True new account (no reset marker)
            if reset_reason is None:
                if not is_verified_now:
                    return redirect(reverse("account_email_verification_sent"))
                # verified true new → normal success
                return response

        # ---------------------------
        # TERMS present (not new/reset)
        # ---------------------------
        # Keep your normal post-login path; if you want to require verify,
        # you could bounce unverified users to the confirm page here.
        return response


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