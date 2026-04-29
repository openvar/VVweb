# verification/forms.py

from django import forms
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

from VVweb.userprofiles.models import ORG_TYPES
from VVweb.verification.validators import is_valid_orcid, is_valid_url


class VerificationForm(forms.Form):
    org_type = forms.ChoiceField(
        choices=ORG_TYPES,
        required=True,
        label="Organisation Type"
    )

    # NEW: country is required
    country = CountryField().formfield(
        required=True,
        label="Country",
        widget=CountrySelectWidget(attrs={"class": "form-control"})
    )

    orcid_id = forms.CharField(
        required=False,
        label="ORCID iD",
        help_text="Optional but recommended (e.g. 0000-0002-1825-0097)."
    )

    evidence_url_1 = forms.URLField(
        required=False,
        label="Evidence URL #1"
    )

    evidence_url_2 = forms.URLField(
        required=False,
        label="Evidence URL #2"
    )

    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        label="Additional Notes"
    )

    accept_terms = forms.BooleanField(
        required=True,
        label="I confirm the information is accurate and I accept the Terms and Conditions."
    )

    def clean_orcid_id(self):
        orcid = self.cleaned_data.get("orcid_id")
        if orcid and not is_valid_orcid(orcid):
            raise forms.ValidationError("Invalid ORCID iD.")
        return orcid

    def clean_evidence_url_1(self):
        url = self.cleaned_data.get("evidence_url_1")
        if url and not is_valid_url(url):
            raise forms.ValidationError("Invalid URL.")
        return url

    def clean_evidence_url_2(self):
        url = self.cleaned_data.get("evidence_url_2")
        if url and not is_valid_url(url):
            raise forms.ValidationError("Invalid URL.")
        return url


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