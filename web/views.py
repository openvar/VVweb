from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from . import forms
from . import tasks
from . import services
import VariantValidator
from VariantValidator import settings as vvsettings
import vvhgvs
from configparser import ConfigParser
from celery.result import AsyncResult
from allauth.account.models import EmailAddress
import logging

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
    }

    return render(request, 'home.html', {
        'versions': versions,
    })


def about(request):
    return render(request, 'about.html')


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
    return render(request, 'batch_instructions.html')


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
                    trans['url'] = 'http://ftp.ebi.ac.uk/pub/databases/lrgex/' + trans['reference'].split('t')[0] + '.xml'
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
            num += 1
            if not request.user.is_authenticated:
                request.session['validations'] = num

            logger.debug("Going to validate sequences")

            variant = request.POST.get('variant')
            genome = request.POST.get('genomebuild', 'GRCh37')

            output = tasks.validate(variant, genome, validator=validator)
            output = services.process_result(output, validator)
            output['genome'] = genome

            request.session['genome'] = genome
            last_genome = genome

            logger.debug(output)
            logger.info("Successful validation made by user %s" % request.user)
            return render(request, 'validate_results.html', {
                'output': output,
                'varsome_token': getattr(settings, 'VARSOME_TOKEN')
            })

    if not request.user.is_authenticated:
        login_page = reverse('account_login')
        here = reverse('validate')
        if num < 5:
            if num == 4:
                messages.warning(request,
                                 "<span id='msg-body'>Warning: Only <span id='msg-valnum'>%s</span> more submission allowed. "
                                 "For unlimited access please <a href='%s?next=%s' class='alert-link'>login</a>.</span>" % (
                                         5 - num, login_page, here))
            else:
                messages.warning(request,
                                 "<span id='msg-body'>Warning: Only <span id='msg-valnum'>%s</span> more submissions allowed. "
                                 "For unlimited access please <a href='%s?next=%s' class='alert-link'>login</a>.</span>" % (
                                     5 - num, login_page, here))
        else:
            logger.debug("Unauthenticated user blocked from validator")
            messages.error(request,
                           "<span id='msg-body'>Please <a href='%s?next=%s' class='alert-link'>login</a> to continue using this service</span>" % (
                               login_page, here))
            locked = True

    return render(request, 'validate.html', {
        'output': output,
        'varsome_token': getattr(settings, 'VARSOME_TOKEN'),
        'locked': locked,
        'last': last_genome,
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
            print(form.cleaned_data)

            job = tasks.batch_validate.delay(
                form.cleaned_data['input_variants'],
                form.cleaned_data['genome'],
                form.cleaned_data['email_address'],
                form.cleaned_data['gene_symbols']
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
            messages.error(request, "You must be <a href='%s?next=%s' class='alert-link'>logged in</a> to submit Validator Batch jobs" % (login_page, here))
            form.fields['input_variants'].disabled = True
            form.fields['genome'].disabled = True
            form.fields['email_address'].disabled = True
            form.fields['gene_symbols'].disabled = True
            locked = True
        else:
            form.fields['genome'].initial = last_genome
            email = EmailAddress.objects.get(email=request.user.email)
            if email.verified:
                form.fields['email_address'].initial = email.email
            else:
                form.fields['input_variants'].disabled = True
                form.fields['genome'].disabled = True
                form.fields['email_address'].disabled = True
                form.fields['gene_symbols'].disabled = True
                verify = reverse('account_email')
                messages.error(request, "Primary email address must be <a href='%s' class='alert-link'>verified</a> before submitting a Batch Validator job" % (verify))
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
                        form.cleaned_data['email_address']
                    )
                    jobs.append(str(res))
                res = ', '.join(jobs)
            else:
                res = tasks.vcf2hgvs.delay(
                    request.FILES['vcf_file'].read(),
                    form.cleaned_data['genome'],
                    form.cleaned_data['gene_symbols'],
                    form.cleaned_data['email_address']
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
            messages.error(request, "You must be <a href='%s?next=%s' class='alert-link'>logged in</a> to submit VCF to HGVS jobs" % (login_page, here))
            form.fields['vcf_file'].disabled = True
            form.fields['genome'].disabled = True
            form.fields['email_address'].disabled = True
            form.fields['gene_symbols'].disabled = True
            locked = True
        else:
            form.fields['genome'].initial = last_genome
            email = EmailAddress.objects.get(email=request.user.email)
            if email.verified:
                form.fields['email_address'].initial = email.email
            else:
                form.fields['vcf_file'].disabled = True
                form.fields['genome'].disabled = True
                form.fields['email_address'].disabled = True
                form.fields['gene_symbols'].disabled = True
                verify = reverse('account_email')
                messages.error(request, "Primary email address must be <a href='%s' class='alert-link'>verified</a> before submitting VCF to HGVS jobs" % (verify))
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
    for row in job.result:
        if isinstance(row, list):
            buffer += '\t'.join(row)
        else:
            buffer += row
        buffer += '\n'
    print(buffer)

    response = HttpResponse(buffer, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename=batch_job.txt'
    logger.debug("Job %s results downloaded by user %s" % (job_id, request.user))
    return response
