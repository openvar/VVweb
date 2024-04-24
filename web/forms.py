from django import forms
from . import models
from allauth.account.forms import SignupForm, PasswordField
from django.utils.translation import ugettext_lazy as _
from captcha.fields import ReCaptchaField

BATCH_FORM_OPTIONS = [
    ('transcript', 'Transcript context descriptions'),
    ('genomic', 'Genomic context descriptions'),
    ('protein', 'Protein context descriptions'),
    ('refseqgene', 'RefSeqGene context descriptions'),
    ('lrg', 'LRG context descriptions'),
    ('vcf', 'VCF coordinates'),
    ('gene_info', 'Gene symbol and HGNC ID'),
    ('tx_name', 'Transcript name'),
    ('alt_loci', 'Alternate genomic reference sequences')
]


class ContactForm(forms.ModelForm):
    class Meta:
        model = models.Contact
        widgets = {
            'nameval': forms.TextInput(attrs={'placeholder': 'Your Name'}),
            'emailval': forms.TextInput(attrs={'placeholder': 'Your email address'}),
            'variant': forms.TextInput(
                attrs={'placeholder': 'Variant description required for variant analysis errors'}),
            'question': forms.Textarea(
                attrs={'placeholder': 'Enter query here'}),
        }
        fields = ('nameval', 'emailval', 'variant', 'question')

    def clean(self):
        if self.data['name'] or self.data['email']:
            raise forms.ValidationError("Spam detected")
        return self.cleaned_data


class BatchValidateForm(forms.Form):
    input_variants = forms.CharField(widget=forms.Textarea(
        attrs={'placeholder': 'Variant descriptions must be separated by new lines, spaces or tabs. '
                              'Please be considerate of other users and only submit one job at a time!'}),
                                     label='Input Variant Descriptions'
    )
    gene_symbols = forms.CharField(widget=forms.Textarea(
        attrs={'rows': '3', 'placeholder': 'One gene symbol per line'}),
                                   required=False,
                                   label='Limit search, optionally, to specific genes (use HGNC gene symbols)'
    )
    select_transcripts = forms.CharField(widget=forms.Textarea(
        attrs={'rows': '5', 'placeholder': 'One transcript id per line \n Or use one of: \n\tall (all transcripts at '
                                           'latest version) \n\traw (all transcripts at all versions)'
                                           '\n\tselect \n\t'
                                           'refseq_select \n\tmane'}),
                                         required=False,
                                         label='Optional - limit to specific transcripts (see our Genes to '
                                         'Transcripts tool). '
                                         'or return select transcripts only'
    )
    options = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple(
        attrs={'checked': 'check_label'}),
                                        choices=BATCH_FORM_OPTIONS,
                                        required=False,
                                        label='Customise the information returned in the output file'
                                        )

    email_address = forms.EmailField(widget=forms.EmailInput(
        attrs={'placeholder': 'A validation report will be sent via email.'}))

    genome = forms.ChoiceField(choices=(('GRCh38', 'GRCh38'), ('GRCh37', 'GRCh37')),
                               widget=forms.RadioSelect(attrs={'class': 'custom-control-input'}),
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

    def clean_select_transcripts(self):
        transcripts = self.cleaned_data['select_transcripts'].strip().split()
        if len(transcripts) == 0:
            transcripts = ['all']
        return '|'.join(transcripts)

    def clean_options(self):
        ops = self.cleaned_data['options']
        return '|'.join(ops)


class VCF2HGVSForm(forms.Form):
    vcf_file = forms.FileField(label='VCF file')

    gene_symbols = forms.CharField(widget=forms.Textarea(
        attrs={'rows': '3', 'placeholder': 'One gene symbol per line'}),
                                   required=False,
                                   label='Limit search, optionally, to specific genes (use HGNC gene symbols)')

    select_transcripts = forms.CharField(widget=forms.Textarea(
        attrs={'rows': '3', 'placeholder': 'One transcript id per line'}),
                                         required=False,
                                         label='Limit search, optionally, to specific transcripts (see our Genes to '
                                         'Transcripts tool). The batch instructions page contains further options '
                                         'e.g. raw (all transcripts at all versions) all (all transcripts at latest '
                                         'version only) mane_select (MANE select transcripts)'
    )
    options = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple(
        attrs={'checked': 'check_label'}),
                                        choices=BATCH_FORM_OPTIONS,
                                        required=False,
                                        label='Customise the information returned in the output file'
                                        )

    email_address = forms.EmailField(widget=forms.EmailInput(
        attrs={'placeholder': 'A validation report will be sent via email.'}))

    genome = forms.ChoiceField(choices=(('GRCh38', 'GRCh38'), ('GRCh37', 'GRCh37')),
                               widget=forms.RadioSelect(attrs={'class': 'custom-control-input'}),
                               label='Select genome build')

    def clean_gene_symbols(self):
        symbols = self.cleaned_data['gene_symbols'].strip().split()
        return '|'.join(symbols)

    def clean_select_transcripts(self):
        transcripts = self.cleaned_data['select_transcripts'].strip().split()
        if len(transcripts) == 0:
            transcripts = ['all']
        return '|'.join(transcripts)

    def clean_options(self):
        ops = self.cleaned_data['options']
        return '|'.join(ops)


class UpdatedSignUpForm(SignupForm):
    password1 = PasswordField(label=_("Password"))
    password2 = PasswordField(label=_("Password (again)"))
    captcha = ReCaptchaField()

    def save(self, request):
        # Ensure you call the parent class's save.
        # .save() returns a User object.
        user = super(UpdatedSignUpForm, self).save(request)

        # Add your own processing here.

        # You must return the original result.
        return user

# <LICENSE>
# Copyright (C) 2016-2024 VariantValidator Contributors
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
