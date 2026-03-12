# web/views_resend.py

from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation

User = get_user_model()


def _normalize(email: str) -> str:
    return (email or "").strip().lower()


def _resolve_target_email(request) -> str:
    """
    Order of precedence:
      1) Explicit query or form param:  ?email=<addr>
      2) Session value set by signup/login: session["account_email"]
      3) Logged-in user's email
    """
    email = request.GET.get("email") or request.POST.get("email")
    if not email:
        email = request.session.get("account_email")
    if not email and request.user.is_authenticated:
        email = request.user.email
    return _normalize(email)


@require_http_methods(["GET", "POST"])
def resend_confirmation(request):
    """
    Resend confirmation email for a user, whether authenticated or not.

    Robust behavior:
      • Finds the target email from query/session/logged-in user.
      • Ensures an EmailAddress row exists (creates if missing for logged-in user).
      • Forces it to primary & unverified.
      • Sends the allauth confirmation email.
      • Redirects back to the 'email sent' page, preserving ?annual=1 if present.
    """
    # Keep the 'annual' context flag for UX differentiation on the confirm page
    annual_flag = "?annual=1" if request.GET.get("annual") == "1" else ""

    email = _resolve_target_email(request)
    if not email:
        messages.error(request, "No email address provided.")
        return redirect(reverse("account_email_verification_sent") + annual_flag)

    # If the requester is logged in, ensure their EmailAddress exists/repairs cleanly
    if request.user.is_authenticated:
        # Create or fetch the email row for this user specifically
        email_obj, _ = EmailAddress.objects.get_or_create(
            user=request.user,
            email=email,
            defaults={"primary": True, "verified": False},
        )
        # Guarantee "new-account" style state
        email_obj.primary = True
        email_obj.verified = False
        email_obj.save()

        # Optional: if user somehow had multiple email rows, make this the only primary
        EmailAddress.objects.filter(user=request.user).exclude(pk=email_obj.pk).update(primary=False)

        # Send confirmation
        send_email_confirmation(request, request.user)
        messages.success(request, f"A new confirmation email has been sent to {email}.")
        return redirect(reverse("account_email_verification_sent") + annual_flag)

    # Anonymous path: find an existing EmailAddress row by email
    email_obj = EmailAddress.objects.filter(email__iexact=email).first()
    if not email_obj:
        messages.error(request, "Unknown email address.")
        return redirect(reverse("account_email_verification_sent") + annual_flag)

    # Force "needs confirmation" state for that account
    email_obj.verified = False
    email_obj.primary = True
    email_obj.save()

    # Also make it the only primary for that user
    EmailAddress.objects.filter(user=email_obj.user).exclude(pk=email_obj.pk).update(primary=False)

    # Send confirmation to the owning user
    send_email_confirmation(request, email_obj.user)
    messages.success(request, f"A new confirmation email has been sent to {email}.")

    return redirect(reverse("account_email_verification_sent") + annual_flag)

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
