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
      2) Session value set by signup/login/middleware: session["account_email"]
      3) Logged-in user's email
    """
    email = request.GET.get("email") or request.POST.get("email")
    if not email:
        email = request.session.get("account_email")
    if not email and request.user.is_authenticated:
        email = request.user.email
    return _normalize(email)


def _suffix_with_resent_and_annual(request) -> str:
    """
    Always append ?resent=1 so the landing page shows messages
    exactly after a resend, and preserve ?annual=1 when present.
    """
    parts = ["resent=1"]
    if request.GET.get("annual") == "1":
        parts.append("annual=1")
    return "?" + "&".join(parts)


@require_http_methods(["GET", "POST"])
def resend_confirmation(request):
    """
    Resend confirmation email for a user, whether authenticated or not.

    Behavior:
      • Resolve the target email from query/session/logged-in user.
      • If logged in, ensure an EmailAddress row exists and is primary.
      • DO NOT flip 'verified' here (annual reset/middleware handles that).
      • Send the Allauth confirmation email.
      • Redirect back to the confirm page with ?resent=1 (and ?annual=1 if present).
    """
    suffix = _suffix_with_resent_and_annual(request)
    return_to = reverse("account_email_verification_sent") + suffix

    email = _resolve_target_email(request)
    if not email:
        messages.error(request, "No email address provided.")
        return redirect(return_to)

    # Logged-in path: create/repair row, make it primary, then send
    if request.user.is_authenticated:
        email_obj, _ = EmailAddress.objects.get_or_create(
            user=request.user,
            email=email,
            defaults={"primary": True, "verified": False},
        )

        # Ensure this is the sole primary; do not toggle verified state here
        if not email_obj.primary:
            EmailAddress.objects.filter(user=request.user).update(primary=False)
            email_obj.primary = True
            email_obj.save(update_fields=["primary"])

        # Keep for the template regardless of auth state on return
        request.session["account_email"] = email

        # Send confirmation
        send_email_confirmation(request, request.user)
        messages.success(request, f"A new confirmation email has been sent to {email}.")
        return redirect(return_to)

    # Anonymous path: try resolve by EmailAddress
    email_obj = EmailAddress.objects.filter(email__iexact=email).first()
    if not email_obj:
        messages.error(request, "Unknown email address.")
        return redirect(return_to)

    # Prefer the matched row as primary (do not change verified here)
    if not email_obj.primary:
        EmailAddress.objects.filter(user=email_obj.user).update(primary=False)
        email_obj.primary = True
        email_obj.save(update_fields=["primary"])

    # Send confirmation to the owning user
    send_email_confirmation(request, email_obj.user)
    messages.success(request, f"A new confirmation email has been sent to {email}.")

    return redirect(return_to)


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
