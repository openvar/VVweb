from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from . import forms
from . import tasks
from . import services
import VariantValidator
import vvhgvs
from configparser import ConfigParser

print("Imported views and creating Validator Obj - SHOULD ONLY SEE ME ONCE")
mything = VariantValidator.Validator()


def home(request):
    config = ConfigParser()
    config.read(VariantValidator.settings.CONFIG_DIR)

    versions = {
        'VariantValidator': VariantValidator.__version__,
        'hgvs': vvhgvs.__version__,
        'uta': config['postgres']['version'],
        'seqrepo': config['seqrepo']['version'],
    }
    print(mything)

    return render(request, 'home.html', {
        'versions': versions,
    })


def about(request):
    print(mything)
    return render(request, 'about.html')


def contact(request):
    form = forms.ContactForm()

    if request.method == 'POST':
        form = forms.ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            contact.send_email()
            return redirect('contact')

    return render(request, 'contact.html', {
        'form': form,
    })


def nomenclature(request):
    return render(request, 'nomenclature.html')


def validate(request):
    """
    View will validate input and process output. If multiple transcripts are found, each will be presented with their
    own tab. Choice and filtering of results will occur server side after everything returned. Might take a while for
    some sequences so will need loading spinner/timeout.
    :param request:
    :return:
    """

    output = False

    if request.method == 'POST':
        print("Going to validate sequences")

        variant = request.POST.get('variant')
        genome = request.POST.get('genomebuild')

        output = tasks.validate(variant, genome, validator=mything)
        output = services.process_result(output, mything)
        output['genome'] = genome
        print(output)

    return render(request, 'validate.html', {
        'output': output,
        'varsome_token': getattr(settings, 'VARSOME_TOKEN'),
    })


def batch_validate(request):
    """
    View will take input and run validator via Celery. Results will be emailed to user.
    :param request:
    :return:
    """

    form = forms.BatchValidateForm()

    if request.method == 'POST':
        print("Form submitted")
        form = forms.BatchValidateForm(request.POST)
        if form.is_valid():
            print(form.cleaned_data)

            input_str = form.cleaned_data['input_variants']
            print(input_str)

            gene_str = form.cleaned_data['gene_symbols']
            print(gene_str)

            tasks.batch_validate.delay(input_str, form.cleaned_data['genome'], transcripts=gene_str)
            messages.success(request, "Batch validation successfully submitted - results will be emailed to you")
            return redirect('batch_validate')
        messages.warning(request, "Form contains errors (see below). Please resubmit")

    return render(request, 'batch_validate.html', {
        'form': form,
    })
