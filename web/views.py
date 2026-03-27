from django.http import Http404
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
    Request will download job results
    :param request:
    :param job_id:
    :return:
    """
    job = AsyncResult(job_id)

    buffer = str()
    buffer += '# Job ID:%s\n' % job_id
    try:
        # Modify the output based on the options selected by the user.

        # First pass, collect the metadata line which has had the options embedded
        metaline = ''
        for row in job.result:
            if "Metadata:" in str(row):
                metaline = str(row)

        # Next parse the metaline to set the options
        # 'options': 'transcript|genomic|protein|refseqgene|lrg|vcf|gene_info|tx_name|alt_loci'
        if 'transcript' in metaline:
            transcript_d = True
        else:
            transcript_d = False
        if 'genomic' in metaline:
            genomic_d = True
        else:
            genomic_d = False
        if 'protein' in metaline:
            protein_d = True
        else:
            protein_d = False
        if 'refseqgene' in metaline:
            refseqgene_d = True
        else:
            refseqgene_d = False
        if 'lrg' in metaline:
            lrg_d = True
        else:
            lrg_d = False
        if 'vcf' in metaline:
            vcf_d = True
        else:
            vcf_d = False
        if 'gene_info' in metaline:
            gene_info_d = True
        else:
            gene_info_d = False
        if 'tx_name' in metaline:
            tx_name_d = True
        else:
            tx_name_d = False
        if 'alt_loci' in metaline:
            alt_loci_d = True
        else:
            alt_loci_d = False

        # Based on the option controls, add the correct list elements from job.result into the list my_results
        my_results = []
        for row in job.result:
            if "# Metadata" not in row:
                output_these_elements = []
                # Add selected variant and warnings
                row[2] = str(row[2])
                l = row[0:2]
                output_these_elements = output_these_elements + l
                if transcript_d is True:
                    l = row[2:5]
                    output_these_elements = output_these_elements + l
                if refseqgene_d is True:
                    l = row[5:7]
                    output_these_elements = output_these_elements + l
                if lrg_d is True:
                    l = row[7:9]
                    output_these_elements = output_these_elements + l
                if protein_d is True:
                    l = [row[9]]
                    output_these_elements = output_these_elements + l
                if genomic_d is True:
                    l = [row[10]]
                    output_these_elements = output_these_elements + l
                    l = [row[16]]
                    output_these_elements = output_these_elements + l
                if vcf_d is True:
                    l = row[11:16]
                    output_these_elements = output_these_elements + l
                    l = row[17:22]
                    output_these_elements = output_these_elements + l
                if gene_info_d is True:
                    l = row[22:24]
                    output_these_elements = output_these_elements + l
                if tx_name_d is True:
                    l = [row[24]]
                    output_these_elements = output_these_elements + l
                if alt_loci_d is True:
                    l = [row[25]]
                    output_these_elements = output_these_elements + l
            else:
                output_these_elements = row
            my_results.append(output_these_elements)

        # String together the list into an output string for transfer into a text file (tab delimited "\n" newlines)
        for row in my_results:
            if isinstance(row, list):
                # The sql query returns null for some columns which is converted
                # to a Python NoneType. In this case the join() was failing.
                # Added a list comprehension to convert the NoneType to a string
                # containing the word 'None'.
                buffer += '\t'.join(['None' if v is None else v for v in row])
            elif isinstance(row, str):
                # Converted the else statement to an elif, to test whether we got a string.
                # If yes we append it here (Usually the Metadata row).
                # Add an else statement if needed.
                buffer += row
            buffer += '\n'
    except Exception as ex:
        # This will print errors to the Apache log
        exc_type, exc_value, last_traceback = sys.exc_info()
        logger.error(str(exc_type) + " " + str(exc_value))
        traceback.print_tb(last_traceback, file=sys.stdout)

    response = HttpResponse(buffer, content_type='text/plain')
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
