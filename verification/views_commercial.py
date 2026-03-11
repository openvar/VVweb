# verification/views_commercial.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from web.models import VariantQuota


@login_required
def commercial_landing(request):
    """
    Page shown to commercial users until they purchase a licence
    or request a manual trial.
    """
    return render(request, "commercial.html")


# -------------------------------------------------------------------
# ONE-TIME COMMERCIAL TRIAL REDEMPTION ENDPOINT (WITH REDIRECT)
# -------------------------------------------------------------------
@login_required
@require_POST
def redeem_trial(request):
    """
    One-time commercial trial endpoint.

    Behaviour:
    • Only commercial users may use it.
    • Applies DEFAULT_MONTHLY_VARIANT_ALLOWANCE as custom_limit.
    • Marks VariantQuota.trial_redeemed = True.
    • Redirects to main application page upon success.
    """

    user = request.user

    # ---------------------------------------------------------------
    # Fetch VariantQuota
    # ---------------------------------------------------------------
    try:
        quota = user.variant_quota
    except VariantQuota.DoesNotExist:
        return JsonResponse({"error": "No VariantQuota found for this user."}, status=400)

    # ---------------------------------------------------------------
    # Check user is commercial
    # ---------------------------------------------------------------
    profile = getattr(user, "profile", None)

    if not profile or profile.verification_status != "commercial":
        return HttpResponseForbidden("Only commercial users may redeem this trial.")

    # ---------------------------------------------------------------
    # If already redeemed, just redirect them immediately
    # ---------------------------------------------------------------
    if quota.trial_redeemed:
        return redirect("/")   # main page

    # ---------------------------------------------------------------
    # Apply the trial using system default
    # ---------------------------------------------------------------
    trial_amount = getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)

    quota.custom_limit = trial_amount
    quota.trial_redeemed = True
    quota.save()

    # ---------------------------------------------------------------
    # Redirect user to main app (now they have access)
    # ---------------------------------------------------------------
    return redirect("/")

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
