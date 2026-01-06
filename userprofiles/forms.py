# -*- coding: utf-8 -*-

from django import forms
from django.http import Http404
from django.contrib.auth.models import User
from .models import UserProfile


class IdentityForm(forms.ModelForm):
    first_name = forms.CharField(max_length=256)
    last_name = forms.CharField(max_length=256)

    class Meta:
        model = UserProfile
        fields = ('first_name', 'last_name', 'institution', 'country', 'jobrole',)
        widgets = {'phone': forms.TextInput()}

    def __init__(self, *args, **kwargs):
        super(IdentityForm, self).__init__(*args, **kwargs)
        try:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
        except User.DoesNotExist:
            raise Http404
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['institution'].required = True
        self.fields['country'].required = True
        self.fields['jobrole'].required = True
        return


class EmailForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['email']

    def __init__(self, *args, **kwargs):
        super(EmailForm, self).__init__(*args, **kwargs)
        self.fields['email'].required = True

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