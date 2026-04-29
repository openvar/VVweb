# userprofiles/views.py

from django.http import HttpResponseRedirect
from django.views.generic.edit import UpdateView
from .forms import IdentityForm

from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import UserProfile


class ProfileHomeView(LoginRequiredMixin, TemplateView):
    """
    User profile landing page.

    IMPORTANT:
    - This view MUST NOT perform any lifecycle mutations.
    - Annual verification expiry and auto-reset are enforced globally
      by UserProfileAutoResetMiddleware.
    - This view only reflects current profile state to the UI.
    """

    template_name = "userprofiles/userprofiles/home.html"
    user_check_failure_path = reverse_lazy("account_signup")

    def check_user(self, user):
        return user.is_active

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)

        # -----------------------------------------
        # UI FLAGS ONLY (NO STATE MUTATION HERE)
        # -----------------------------------------

        # User must reverify if middleware has cleared terms
        context["reverify_required"] = profile.is_revalidation()

        context["profile"] = profile
        return context


class ProfileIdentity(LoginRequiredMixin, UpdateView):
    template_name = "userprofiles/userprofiles/identity_form.html"
    form_class = IdentityForm
    user_check_failure_path = reverse_lazy("account_signup")
    success_url = reverse_lazy("profile-home")

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

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
