from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic.edit import UpdateView
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import UserProfile
from .forms import IdentityForm


class ProfileHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'userprofiles/home.html'
    user_check_failure_path = reverse_lazy("account_signup")

    def check_user(self, user):
        if user.is_active:
            return True
        return False

    def get_context_data(self, **kwargs):
        context = super(ProfileHomeView, self).get_context_data(**kwargs)
        profile = UserProfile.objects.get_or_create(user=self.request.user)[0]
        context['profile'] = profile
        return context


class ProfileIdentity(LoginRequiredMixin, UpdateView):
    template_name = "userprofiles/identity_form.html"
    form_class = IdentityForm
    user_check_failure_path = reverse_lazy("account_signup")
    success_url = reverse_lazy("profile-home")

    def get_queryset(self):
        queryset = UserProfile.objects.filter(user=self.request.user)
        return queryset

    def form_valid(self, form, **kwargs):
        super(ProfileIdentity, self).form_valid(form)
        profile = form.save(commit=False)
        user = self.request.user
        user.first_name = form.cleaned_data['first_name']
        user.last_name = form.cleaned_data['last_name']
        user.save()
        profile.institution = form.cleaned_data['institution']
        profile.jobrole = form.cleaned_data['jobrole']
        profile.personal_info_is_completed = True
        profile.completion_level = profile.get_completion_level()
        profile.save()
        return HttpResponseRedirect(self.get_success_url())

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
