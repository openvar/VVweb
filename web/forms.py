from django import forms
from . import models


class ContactForm(forms.ModelForm):
    class Meta:
        model = models.Contact
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your Name'}),
            'email': forms.TextInput(attrs={'placeholder': 'Your email address'}),
            'variant': forms.TextInput(
                attrs={'placeholder': 'Variant description required for variant analysis errors'}),
            'question': forms.Textarea(
                attrs={'placeholder': 'Enter query here'}),
        }
        fields = ('name', 'email', 'variant', 'question')
