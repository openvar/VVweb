from django.http import Http404
from .object_pool import vval_object_pool, g2t_object_pool
from .utils import render_to_pdf
import VariantValidator
from VariantValidator import settings as vvsettings
import vvhgvs
from configparser import ConfigParser
from celery.result import AsyncResult
import json
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

logger = logging.getLogger('vv')

print("Imported views and creating Validator Obj - SHOULD ONLY SEE ME ONCE")


def home(request):
    config = ConfigParser()
    config.read(vvsettings.CONFIG_DIR)

    versions = {
        'VariantValidator': VariantValidator.__version__,
        'hgvs': vvhgvs.__version__,
        'uta': config['postgres']['version'],
        'seqrepo': config['seqrepo']['version'],
        'vvdb': config['mysql']['version']
    }

    return render(request, 'home.html', {
        'versions': versions,
    })


def about(request):
    return redirect('https://github.com/openvar/variantValidator/blob/master/README.md')


def contact(request):
    logger.debug("Loading Contact page")
    form = forms.ContactForm()

    if request.method == 'POST':
        logger.debug("POST to contact page")
        form = forms.ContactForm(request.POST)
        if form.is_valid():
            my_contact = form.save()
            services.send_contact_email(my_contact)
            messages.success(request, "Message sent")
            logger.info("Contact from %s made" % my_contact.emailval)
            return redirect('contact')

    return render(request, 'contact.html', {
        'form': form,
    })


def nomenclature(request):
    return render(request, 'nomenclature.html')


def instructions(request):
    return redirect('https://github.com/openvar/VV_databases/blob/master/markdown/instructions.md')
    # return render(request, 'batch_instructions.html')


def faqs(request):
    return render(request, 'faqs.html')


@login_required
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

    return render(request, 'genes_to_transcripts.html', {
        'output': output
    })


def validate(request):
    """
    Interactive single-variant validator.
    Keeps new security + synchronous validation improvements,
    restores old quota, anonymous warnings, lockout behaviour,
    and fully restores working PDF generation.
    """
    output = False
    locked = False

    # Anonymous usage counter
    num = int(request.session.get("validations", 0))

    last_genome = request.session.get("genome", None)
    last_source = request.session.get("refsource", None)

    # ------------------------------------------------------------------
    # GET — render input form + anonymous warnings
    # ------------------------------------------------------------------
    if request.method == 'GET':

        if not request.user.is_authenticated:
            login_page = reverse("account_login")
            here = reverse("validate")

            if num < 5:
                remaining = 5 - num
                if remaining == 1:
                    msg = (
                        f"<span id='msg-body'>Warning: Only "
                        f"<span id='msg-valnum'>1</span> more submission allowed. "
                        f"For full access please "
                        f"<a href='{login_page}?next={here}' class='alert-link'>login</a>.</span>"
                    )
                else:
                    msg = (
                        f"<span id='msg-body'>Warning: Only "
                        f"<span id='msg-valnum'>{remaining}</span> more submissions allowed. "
                        f"For full access please "
                        f"<a href='{login_page}?next={here}' class='alert-link'>login</a>.</span>"
                    )
                messages.warning(request, msg)

            else:
                messages.error(
                    request,
                    (
                        f"<span id='msg-body'>Please "
                        f"<a href='{login_page}?next={here}' class='alert-link'>login</a> "
                        f"to continue using this service.</span>"
                    )
                )
                locked = True

        return render(request, 'validate.html', {
            'variant': request.GET.get('variant'),
            'genome': request.GET.get('genomebuild', 'GRCh38'),
            'select_transcripts': request.GET.get('transcripts'),
            'transcripts': request.GET.get('transcripts'),
            'from_get': True,
            'autosubmit': request.GET.get('autosubmit', 'false'),
            'source': request.GET.get('refsource', 'refseq'),
            'locked': locked,
        })

    # ------------------------------------------------------------------
    # POST — perform validation
    # ------------------------------------------------------------------
    if request.method == 'POST':

        # Anonymous hard lockout
        if not request.user.is_authenticated and num >= 5:
            login_page = reverse('account_login')
            here = reverse('validate')
            messages.error(
                request,
                f"Please <a href='{login_page}?next={here}' class='alert-link'>login</a> to continue."
            )
            return render(request, 'validate.html', {'output': None, 'locked': True})

        # Extract input
        variant = request.POST.get('variant')
        genome = request.POST.get('genomebuild', 'GRCh38')
        source = request.POST.get('refsource', 'refseq')

        select_transcripts = request.POST.get('transcripts')
        if not select_transcripts or select_transcripts in ['all', 'transcripts']:
            select_transcripts = 'all'

        pdf_request = request.POST.get('pdf_request')

        # ------------------------------------------------------------------
        # Acquire validator + synchronous validation
        # ------------------------------------------------------------------
        validator = vval_object_pool.get_object()

        try:
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
            vval_object_pool.return_object(validator)

        # ---------------- Count anonymous submissions ----------------
        if not request.user.is_authenticated:
            num += 1
            request.session['validations'] = num

        # ------------------------------------------------------------------
        # PDF GENERATION — RESTORED + FIXED
        # ------------------------------------------------------------------

        # Normalise exactly like the old working code
        if pdf_request is None:
            pdf_requested = True
        elif pdf_request in ("False", "false", "0"):
            pdf_requested = False
        else:
            pdf_requested = True

        if pdf_requested:
            config = ConfigParser()
            config.read(vvsettings.CONFIG_DIR)

            versions = {
                'VariantValidator': VariantValidator.__version__,
                'hgvs': vvhgvs.__version__,
                'uta': config['postgres']['version'],
                'seqrepo': config['seqrepo']['version'],
                'vvdb': config['mysql']['version'],
            }

            context = {'output': output, 'versions': versions}

            pdf = render_to_pdf(request, 'pdf_results.html', context)

            if pdf:
                response = HttpResponse(pdf, content_type='application/pdf')
                filename = f"VariantValidator_report_{variant}.pdf"

                if request.GET.get("download"):
                    disposition = f"attachment; filename={filename}"
                else:
                    disposition = f"inline; filename={filename}"

                response['Content-Disposition'] = disposition
                return response

            return HttpResponse("Could not generate PDF")

        # ------------------------------------------------------------------
        # Render results
        # ------------------------------------------------------------------
        return render(request, 'validate_results.html', {
            'output': output,
            'ucsc': ucsc_link,
            'varsome': varsome_link,
            'gnomad': gnomad_link,
        })

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------
    return render(request, 'validate.html', {
        'output': output,
        'locked': locked,
        'last': last_genome,
        'source': last_source,
    })


def batch_validate(request):
    """
    Batch Validator (secure + improved).
    Keeps the new authentication + verification logic,
    restores functional behaviour from the old version,
    and applies quota: N credits = number of submitted variants.
    """

    locked = False
    last_genome = request.session.get("genome")

    # ------------------------------------------------------------------
    # POST — Submit batch job
    # ------------------------------------------------------------------
    if request.method == "POST":

        # Must be logged in
        if not request.user.is_authenticated:
            login_url = reverse("account_login")
            return redirect(f"{login_url}?next={reverse('batch_validate')}")

        # Must have a primary email configured
        email_address = getattr(request.user, "email", None)
        if not email_address:
            messages.error(request, "Your account does not have a valid email address.")
            return redirect("account_email")

        # Must be verified
        try:
            email_obj = EmailAddress.objects.get(user=request.user, email=email_address)
            if not email_obj.verified:
                messages.error(
                    request,
                    "You must verify your email before submitting batch jobs."
                )
                return redirect("account_email")
        except EmailAddress.DoesNotExist:
            messages.error(
                request,
                "Your email address is not registered or verified."
            )
            return redirect("account_email")

        # Instantiate form
        form = forms.BatchValidateForm(request.POST, request=request)

        if form.is_valid():

            # User selects ONE verified email (radio field)
            verified_email = form.cleaned_data["verified_email"]
            user_id = request.user.id

            # print("ABOUT TO CALL CELERY WITH:", {
            #     "variant": form.cleaned_data["input_variants"],
            #     "genome": form.cleaned_data["genome"],
            #     "email": verified_email,
            #     "gene_symbols": form.cleaned_data["gene_symbols"],
            #     "transcripts": form.cleaned_data["select_transcripts"],
            #     "options": form.cleaned_data["options"],
            #     "transcript_set": form.cleaned_data["refsource"],
            #     "user_id": user_id,
            # })

            # Celery async job
            job = tasks.batch_validate.delay(
                variant=form.cleaned_data["input_variants"],
                genome=form.cleaned_data["genome"],
                email=verified_email,
                gene_symbols=form.cleaned_data["gene_symbols"],
                transcripts=form.cleaned_data["select_transcripts"],
                options=form.cleaned_data["options"],
                transcript_set=form.cleaned_data["refsource"],
                user_id=user_id,
            )

            # Notify user
            services.send_initial_email(verified_email, job, 'validation')
            messages.success(request, f"Success! Job ID: {job}")

            logger.info(f"Batch job submitted: user_id={user_id}, job={job}")

            request.session["genome"] = form.cleaned_data["genome"]

            return redirect("batch_validate")

        # Form invalid
        messages.warning(
            request,
            "Form contains errors. Please fix them below."
        )

    # ------------------------------------------------------------------
    # GET — Render form
    # ------------------------------------------------------------------
    else:
        form = forms.BatchValidateForm(request=request)

        if not request.user.is_authenticated:

            login_page = reverse("account_login")
            here = reverse("batch_validate")

            messages.error(
                request,
                f"You must be <a href='{login_page}?next={here}' class='alert-link'>logged in</a> "
                f"to submit batch jobs."
            )

            for field in form.fields.values():
                field.disabled = True

            locked = True

        else:
            form.fields["genome"].initial = last_genome

            email_address = getattr(request.user, "email", None)
            email_obj = EmailAddress.objects.filter(
                user=request.user,
                email__iexact=email_address
            ).first()

            if email_obj and email_obj.verified:
                # Preselect the user's verified primary email
                form.fields["verified_email"].initial = email_obj.email
            else:
                for field in form.fields.values():
                    field.disabled = True

                verify_url = reverse("account_email")

                messages.error(
                    request,
                    f"Primary email must be <a href='{verify_url}' class='alert-link'>verified</a> "
                    "before batch submission."
                )

                locked = True

    return render(
        request,
        "batch_validate.html",
        {
            "form": form,
            "locked": locked,
            "settings": settings,
        }
    )

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


def bed_file(request):
    # Capture the incoming request
    info = request.GET.get('variant')
    if info is None:
        raise Http404("BED file does not exist without providing input variants")

    # Split up the input
    input_elements = info.split('|')
    # Sort out URI encoding
    if '+' in str(input_elements[0]):
        input_elements = str(input_elements[0].replace(' ', '+'))

    validator = vval_object_pool.get_object()
    bed_call = services.create_bed_file(validator, *input_elements)
    vval_object_pool.return_object(validator)

    response = HttpResponse(bed_call, content_type='text/plain; charset=utf-8')
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
