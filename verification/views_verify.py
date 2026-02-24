# verification/views_verify.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.utils import ProgrammingError, OperationalError

from userprofiles.models import UserProfile
from verification.models import TrustedDomain, VerificationEvidence
from verification.forms import VerificationForm
from verification.validators import (
    is_valid_url,
    is_probable_google_scholar,
    is_linkedin_profile
)


def extract_domain(email: str) -> str:
    """Extract the host part after '@' (lowercased), e.g. 'manchester.ac.uk'."""
    try:
        return email.split("@", 1)[1].lower().strip()
    except Exception:
        return ""


def is_trusted_domain(email_domain: str):
    """
    Return the TrustedDomain record if the email_domain ends with one of the
    trusted suffixes (e.g. 'manchester.ac.uk' -> matches 'ac.uk').
    """
    if not email_domain:
        return None
    try:
        for td in TrustedDomain.objects.all():
            if email_domain.endswith(td.domain.lower().strip()):
                return td
    except (ProgrammingError, OperationalError):
        # If the table isn't ready during deploy/migration, fail safe (treat as untrusted)
        return None
    return None


def classify_url_kind(url: str) -> str:
    """Heuristically classify evidence URLs."""
    if not is_valid_url(url):
        return "other"
    u = url.lower()
    if "orcid.org" in u:
        return "orcid"
    if is_probable_google_scholar(url):
        return "scholar"
    if is_linkedin_profile(url):
        return "linkedin"
    if "team" in u or "company" in u or "about" in u:
        return "company"
    if "university" in u or "research" in u or "lab" in u or "nhs" in u:
        return "institution"
    return "other"


@login_required
def verify_identity(request):
    """
    One-page verification flow for all users.
    - Auto-verifies trusted domains (suffix match, e.g., *.ac.uk, nhs.uk).
    - Routes commercial users to /commercial/.
    - Sends untrusted domains to manual review (pending) and emails admins + user.
    """
    profile: UserProfile = request.user.profile

    # Already allowed → go home.
    if profile.verification_status in ("verified", "auto_verified"):
        return redirect("/")

    # Banned/Commercial short-circuits
    if profile.verification_status == "banned":
        return redirect("/banned/")
    if profile.verification_status == "commercial":
        return redirect("/commercial/")

    if request.method == "POST":
        form = VerificationForm(request.POST)
        if form.is_valid():
            # Save core fields
            org_type = form.cleaned_data["org_type"]
            profile.org_type = org_type
            profile.orcid_id = form.cleaned_data.get("orcid_id", "")
            profile.verification_notes = form.cleaned_data.get("notes", "")
            profile.terms_accepted_at = timezone.now()

            # Trust check (suffix based)
            domain = extract_domain(request.user.email)
            trusted = is_trusted_domain(domain)

            if trusted:
                profile.verification_status = "auto_verified"
                profile.verified_at = timezone.now()
                profile.verified_by = None
                profile.save()
                messages.success(request, "Your account was automatically verified.")
                return redirect("/")

            # Commercial users → commercial route
            if org_type == "commercial":
                profile.verification_status = "commercial"
                profile.save()
                return redirect("/commercial/")

            # Untrusted → manual review (pending)
            profile.verification_status = "pending"
            profile.save()

            # Save evidence links
            url1 = form.cleaned_data.get("evidence_url_1")
            url2 = form.cleaned_data.get("evidence_url_2")
            if url1:
                VerificationEvidence.objects.create(
                    user=request.user, url=url1, kind=classify_url_kind(url1)
                )
            if url2:
                VerificationEvidence.objects.create(
                    user=request.user, url=url2, kind=classify_url_kind(url2)
                )

            # Email superusers about pending request
            admin_emails = list(
                User.objects.filter(is_superuser=True).values_list("email", flat=True)
            )
            if admin_emails:
                send_mail(
                    subject="VariantValidator: New verification request",
                    message=(
                        "A new verification request has been submitted.\n\n"
                        f"User: {request.user.username}\n"
                        f"Email: {request.user.email}\n"
                        f"Organisation Type: {profile.org_type}\n\n"
                        "Review in admin:\n"
                        f"{request.build_absolute_uri('/admin/userprofiles/userprofile/')}"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
                    recipient_list=admin_emails,
                    fail_silently=True,
                )

            # Email the user confirming receipt
            user_email = request.user.email
            if user_email:
                send_mail(
                    subject="VariantValidator: Your verification request is pending",
                    message=(
                        "Thank you for submitting your verification request.\n\n"
                        "What happens next:\n"
                        " • We confirm your organisation and intended use.\n"
                        " • If more information is required, we will contact you by email.\n"
                        " • Once approved, you will be able to use VariantValidator immediately.\n\n"
                        "You can add more evidence anytime here:\n"
                        f"{request.build_absolute_uri('/verify/')}\n\n"
                        "Terms and Conditions of Use:\n"
                        "https://github.com/openvar/variantValidator/blob/master/README.md#terms-and-conditions-of-use\n"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
                    recipient_list=[user_email],
                    fail_silently=True,
                )

            messages.info(request, "Your verification request has been submitted.")
            return redirect("/verify/pending/")
    else:
        form = VerificationForm()

    return render(request, "verify.html", {"form": form})


@login_required
def verify_pending(request):
    """Shown after submission while waiting for admin review."""
    profile = getattr(request.user, "profile", None)
    return render(request, "verify_pending.html", {"profile": profile})


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
