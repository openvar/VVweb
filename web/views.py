from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, Http404
from . import forms
from . import tasks
from . import services
from .utils import render_to_pdf
import VariantValidator
from VariantValidator import settings as vvsettings
import vvhgvs
from configparser import ConfigParser
from celery.result import AsyncResult
from allauth.account.models import EmailAddress
import logging
import codecs

print("Imported views and creating Validator Obj - SHOULD ONLY SEE ME ONCE")
validator = VariantValidator.Validator()

logger = logging.getLogger('vv')


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
    # return render(request, 'about.html')


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


def genes_to_transcripts(request):
    output = False

    if request.method == "POST":
        logger.debug("Gene2Trans submitted")
        symbol = request.POST.get('symbol')

        output = tasks.gene2transcripts(symbol, validator)
        logger.debug(output)
        if 'transcripts' in output.keys():
            for trans in output['transcripts']:
                if trans['reference'].startswith('LRG'):
                    trans['url'] = 'http://ftp.ebi.ac.uk/pub/databases/lrgex/' + trans['reference'].split('t')[0
                    ] + '.xml'
                else:
                    trans['url'] = 'https://www.ncbi.nlm.nih.gov/nuccore/' + trans['reference']

    return render(request, 'genes_to_transcripts.html', {
        'output': output
    })


def validate(request):
    """
    View will validate input and process output. If multiple transcripts are found, each will be presented with their
    own tab. Choice and filtering of results will occur server side after everything returned. Might take a while for
    some sequences so will need loading spinner/timeout.
    :param request:
    :return:
    """

    output = False
    locked = False
    num = int(request.session.get('validations', 0))
    last_genome = request.session.get('genome', None)

    if request.method == 'POST':

        if request.user.is_authenticated or num < 5:
            logger.debug("Going to validate sequences")

            variant = request.POST.get('variant')
            genome = request.POST.get('genomebuild', 'GRCh38')
            pdf_r = request.POST.get('pdf_request')
            if pdf_r is None:
                pdf_r = True
            elif pdf_r is "False":
                pdf_r = False
            output = tasks.validate(variant, genome, validator=validator)
            output = services.process_result(output, validator)
            output['genome'] = genome

            request.session['genome'] = genome

            ucsc_link = services.get_ucsc_link(validator, output)
            varsome_link = services.get_varsome_link(output)
            gnomad_link = services.get_gnomad_link(output)

            if pdf_r is True:
                # Render the template into pdf
                config = ConfigParser()
                config.read(vvsettings.CONFIG_DIR)
                versions = {
                    'VariantValidator': VariantValidator.__version__,
                    'hgvs': vvhgvs.__version__,
                    'uta': config['postgres']['version'],
                    'seqrepo': config['seqrepo']['version'],
                    'vvdb': config['mysql']['version']
                }
                context = {
                    'output': output,
                    'versions': versions
                }
                pdf = render_to_pdf(request, 'pdf_results.html', context)
                if pdf:
                    response = HttpResponse(pdf, content_type='application/pdf')
                    filename = "VariantValidator_report_%s.pdf" % variant
                    content = "inline; filename=%s" % filename
                    download = request.GET.get("download")
                    if download:
                        content = "attachment; filename=%s" % filename
                    response['Content-Disposition'] = content
                    return response
                return HttpResponse("Not found")

            # Count requests to 5
            num += 1
            if not request.user.is_authenticated:
                request.session['validations'] = num
            logger.debug(output)
            logger.info("Successful validation made by user %s" % request.user)
            return render(request, 'validate_results.html', {
                'output': output,
                'ucsc': ucsc_link,
                'varsome': varsome_link,
                'gnomad': gnomad_link
            })

    if not request.user.is_authenticated:
        login_page = reverse('account_login')
        here = reverse('validate')
        if num < 5:
            if num == 4:
                messages.warning(request,
                                 "<span id='msg-body'>Warning: Only <span id='msg-valnum'>%s</span> "
                                 "more submission allowed. "
                                 "For unlimited access please <a href='%s?next=%s' "
                                 "class='alert-link'>login</a>.</span>" % (
                                     5 - num, login_page, here))
            else:
                messages.warning(request,
                                 "<span id='msg-body'>Warning: Only <span id='msg-valnum'>%s</span> more submissions "
                                 "allowed. "
                                 "For unlimited access please <a href='%s?next=%s' "
                                 "class='alert-link'>login</a>.</span>" % (
                                     5 - num, login_page, here))
        else:
            logger.debug("Unauthenticated user blocked from validator")
            messages.error(request,
                           "<span id='msg-body'>Please <a href='%s?next=%s' class='alert-link'>login</a> "
                           "to continue using this service</span>" % (
                               login_page, here))
            locked = True

    initial = request.GET.get('variant')
    if initial:
        last_genome = request.GET.get('genome', 'GRCh38')

    return render(request, 'validate.html', {
        'output': output,
        'locked': locked,
        'last': last_genome,
        'initial': initial,
    })


def batch_validate(request):
    """
    View will take input and run validator via Celery. Results will be emailed to user.
    :param request:
    :return:
    """
    locked = False
    last_genome = request.session.get('genome', None)

    if request.method == 'POST':
        form = forms.BatchValidateForm(request.POST)
        if form.is_valid():

            job = tasks.batch_validate.delay(
                form.cleaned_data['input_variants'],
                form.cleaned_data['genome'],
                form.cleaned_data['email_address'],
                form.cleaned_data['gene_symbols'],
                form.cleaned_data['select_transcripts'],
                form.cleaned_data['options']
            )
            messages.success(request, "Success! Validated variants will be emailed to you (Job ID: %s)" % job)
            services.send_initial_email(form.cleaned_data['email_address'], job, 'validation')
            logger.info("Batch validation submitted by user %s" % request.user)
            request.session['genome'] = form.cleaned_data['genome']
            return redirect('batch_validate')
        messages.warning(request, "Form contains errors (see below). Please resubmit")
    else:
        form = forms.BatchValidateForm()
        if not request.user.is_authenticated:
            login_page = reverse('account_login')
            here = reverse('batch_validate')
            messages.error(request, "You must be <a href='%s?next=%s' class='alert-link'>logged in</a> "
                                    "to submit Validator Batch jobs" % (login_page, here))
            form.fields['input_variants'].disabled = True
            form.fields['genome'].disabled = True
            form.fields['email_address'].disabled = True
            form.fields['gene_symbols'].disabled = True
            form.fields['select_transcripts'].disabled = True
            form.fields['options'].disabled = True
            locked = True
        else:
            form.fields['genome'].initial = last_genome
            email_address = getattr(request.user, 'email')
            if email_address:
                email = EmailAddress.objects.get(email=email_address)
                if email.verified:
                    form.fields['email_address'].initial = email.email
                else:
                    form.fields['input_variants'].disabled = True
                    form.fields['genome'].disabled = True
                    form.fields['email_address'].disabled = True
                    form.fields['gene_symbols'].disabled = True
                    form.fields['select_transcripts'].disabled = True
                    form.fields['options'].disabled = True
                    verify = reverse('account_email')
                    messages.error(request,
                                   "Primary email address must be <a href='%s' class='alert-link'>verified</a> "
                                   "before submitting a Batch Validator job" % (
                                       verify))
                    locked = True
            else:
                form.fields['input_variants'].disabled = True
                form.fields['genome'].disabled = True
                form.fields['email_address'].disabled = True
                form.fields['gene_symbols'].disabled = True
                form.fields['select_transcripts'].disabled = True
                form.fields['options'].disabled = True
                verify = reverse('account_email')
                messages.error(request, "Primary email address must be <a href='%s' class='alert-link'>verified</a> "
                                        "before submitting a Batch Validator job" % verify)
                locked = True

    return render(request, 'batch_validate.html', {
        'form': form,
        'locked': locked,
    })


def vcf2hgvs(request):
    """
    View will take uploaded vcf file and convert to HGVS via celery. Results will be emailed to user.
    :param request:
    :return:
    """
    locked = False
    last_genome = request.session.get('genome', None)

    if request.method == 'POST':
        form = forms.VCF2HGVSForm(request.POST, request.FILES)
        if form.is_valid():
            logger.debug("VCF to HGVS input: %s" % form.cleaned_data)
            # json_version = serialize('json', [form.cleaned_data['vcf_file']])
            # print(json_version)

            if request.FILES['vcf_file'].multiple_chunks():
                messages.info(request, 'Large file detected, multiple jobs will be submitted')
                jobs = []
                for chunk in request.FILES['vcf_file'].chunks():
                    res = tasks.vcf2hgvs.delay(
                        chunk,
                        form.cleaned_data['genome'],
                        form.cleaned_data['gene_symbols'],
                        form.cleaned_data['email_address'],
                        form.cleaned_data['select_transcripts'],
                        form.cleaned_data['options']
                    )
                    jobs.append(str(res))
                res = ', '.join(jobs)
            else:
                try:
                    res = tasks.vcf2hgvs.delay(
                        codecs.decode(request.FILES['vcf_file'].read(), 'UTF-8'),
                        form.cleaned_data['genome'],
                        form.cleaned_data['gene_symbols'],
                        form.cleaned_data['email_address'],
                        form.cleaned_data['select_transcripts'],
                        form.cleaned_data['options']
                    )
                except TypeError:
                    res = tasks.vcf2hgvs.delay(
                    request.FILES['vcf_file'].read(),
                    form.cleaned_data['genome'],
                    form.cleaned_data['gene_symbols'],
                    form.cleaned_data['email_address'],
                    form.cleaned_data['select_transcripts'],
                    form.cleaned_data['options']
                )
            messages.success(request, "Success! Validated variants will be emailed to you (Job ID: %s)" % res)
            services.send_initial_email(form.cleaned_data['email_address'], res, 'VCF to HGVS')

            request.session['genome'] = form.cleaned_data['genome']

            logger.info("VCF to HGVS job submitted by user %s" % request.user)
            return redirect('vcf2hgvs')
        messages.warning(request, "Form contains errors (see below). Please resubmit")

    else:
        form = forms.VCF2HGVSForm()
        if not request.user.is_authenticated:
            login_page = reverse('account_login')
            here = reverse('vcf2hgvs')
            messages.error(request, "You must be <a href='%s?next=%s' class='alert-link'>logged in</a> "
                                    "to submit VCF to HGVS jobs" % (login_page, here))
            form.fields['vcf_file'].disabled = True
            form.fields['genome'].disabled = True
            form.fields['email_address'].disabled = True
            form.fields['gene_symbols'].disabled = True
            form.fields['select_transcripts'].disabled = True
            form.fields['options'].disabled = True
            locked = True
        else:
            form.fields['genome'].initial = last_genome
            email_address = getattr(request.user, 'email')
            if email_address:
                email = EmailAddress.objects.get(email=email_address)
                if email.verified:
                    form.fields['email_address'].initial = email.email
                else:
                    form.fields['vcf_file'].disabled = True
                    form.fields['genome'].disabled = True
                    form.fields['email_address'].disabled = True
                    form.fields['gene_symbols'].disabled = True
                    form.fields['select_transcripts'].disabled = True
                    form.fields['options'].disabled = True
                    verify = reverse('account_email')
                    messages.error(request,
                                   "Primary email address must be <a href='%s' class='alert-link'>verified</a> before "
                                   "submitting VCF to HGVS jobs" % (
                                       verify))
                    locked = True
            else:
                form.fields['vcf_file'].disabled = True
                form.fields['genome'].disabled = True
                form.fields['email_address'].disabled = True
                form.fields['gene_symbols'].disabled = True
                form.fields['select_transcripts'].disabled = True
                form.fields['options'].disabled = True
                verify = reverse('account_email')
                messages.error(request, "Primary email address must be <a href='%s' class='alert-link'>verified</a> "
                                        "before submitting VCF to HGVS jobs" % (verify))
                locked = True

    return render(request, 'vcf_to_hgvs.html', {
        'form': form,
        'max': settings.MAX_VCF,
        'locked': locked,
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
                l = row[0:2]
                output_these_elements = output_these_elements + l
                if transcript_d is True:
                    l = row[2:4]
                    output_these_elements = output_these_elements + l
                if refseqgene_d is True:
                    l = row[4:6]
                    output_these_elements = output_these_elements + l
                if lrg_d is True:
                    l = row[6:8]
                    output_these_elements = output_these_elements + l
                if protein_d is True:
                    l = [row[8]]
                    output_these_elements = output_these_elements + l
                if genomic_d is True:
                    l = [row[9]]
                    output_these_elements = output_these_elements + l
                    l = [row[15]]
                    output_these_elements = output_these_elements + l
                if vcf_d is True:
                    l = row[10:14]
                    output_these_elements = output_these_elements + l
                    l = row[16:20]
                    output_these_elements = output_these_elements + l
                if gene_info_d is True:
                    l = row[21:22]
                    output_these_elements = output_these_elements + l
                if tx_name_d is True:
                    l = [row[23]]
                    output_these_elements = output_these_elements + l
                if alt_loci_d is True:
                    l = [row[24]]
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
        print(ex)

    # print(buffer)   # Jon Wakelin 17/Sep/2020
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

    bed_call = services.create_bed_file(validator, *input_elements)

    response = HttpResponse(bed_call, content_type='text/plain; charset=utf-8')
    return response

# <LICENSE>
# Copyright (C) 2016-2021 VariantValidator Contributors
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
