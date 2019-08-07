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


class BatchValidateForm(forms.Form):
    input_variants = forms.CharField(widget=forms.Textarea(
        attrs={'placeholder': 'Variant descriptions must be separated by new lines, spaces or tabs.'}),
                                     label='Input Variant Descriptions'
                                     )
    gene_symbols = forms.CharField(widget=forms.Textarea(
        attrs={'rows': '3', 'placeholder': 'One gene symbol per line'}),
                                   required=False,
                                   label='Limit search, optionally, to specific genes (use HGNC gene symbols)')
    email_address = forms.EmailField(widget=forms.EmailInput(
        attrs={'placeholder': 'A validation report will be sent via email.'}))
    genome = forms.ChoiceField(choices=(('GRCh38', 'GRCh38'), ('GRCh37', 'GRCh37')),
                               widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                               label='Select genome build')

    def clean_input_variants(self):
        vars = self.cleaned_data['input_variants'].strip().split()
        if len(vars) == 0:
            raise forms.ValidationError('Invalid input, no variants detected', code='invalid')

        var_str = '|'.join(vars)
        return var_str

    def clean_gene_symbols(self):
        symbols = self.cleaned_data['gene_symbols'].strip().split()
        return '|'.join(symbols)
