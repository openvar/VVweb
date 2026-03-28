# userprofiles/views.py

from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic.edit import UpdateView
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta

from .models import UserProfile
from .forms import IdentityForm


class ProfileHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'userprofiles/home.html'
    user_check_failure_path = reverse_lazy("account_signup")

    def check_user(self, user):
        return user.is_active

    def get_context_data(self, **kwargs):
        context = super(ProfileHomeView, self).get_context_data(**kwargs)

        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)

        # ------------------------------
        # ANNUAL RE-VERIFICATION CHECK
        # ------------------------------
        if profile.terms_accepted_at:
            one_year_later = profile.terms_accepted_at + timedelta(days=365)

            if timezone.now() >= one_year_later:
                # Reset verification requirements
                profile.email_is_verified = False
                profile.terms_accepted_at = None
                profile.org_type = None
                profile.verification_status = "not_started"
                profile.verified_at = None
                profile.verified_by = None
                profile.rejection_reason = ""

                profile.save()

                # Add a flag to template: "You must re-verify"
                context["reverify_required"] = True

        else:
            # terms never accepted -> also require verification
            context["reverify_required"] = True

        context['profile'] = profile
        return context


class ProfileIdentity(LoginRequiredMixin, UpdateView):
    template_name = "userprofiles/identity_form.html"
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
