from django.shortcuts import render, redirect
from . import forms


def home(request):

    return render(request, 'home.html')


def about(request):
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
