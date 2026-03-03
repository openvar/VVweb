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
    is_linkedin_profile,
)


# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------

def extract_domain(email: str) -> str:
    """Extract domain name safely and in lowercase."""
    try:
        return email.split("@", 1)[1].lower().strip()
    except Exception:
        return ""


def is_trusted_domain(email_domain: str):
    """
    Return a TrustedDomain object if email_domain endswith a known trusted suffix.
    E.g., manchester.ac.uk → matches ac.uk
    """
    if not email_domain:
        return None
    try:
        for td in TrustedDomain.objects.all():
            if email_domain.endswith(td.domain.strip().lower()):
                return td
    except (ProgrammingError, OperationalError):
        return None
    return None


def classify_url_kind(url: str) -> str:
    """Heuristic classifier for evidence URLs."""
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


# ---------------------------------------------------------------------
# VERIFICATION WORKFLOW
# ---------------------------------------------------------------------

@login_required
def verify_identity(request):
    """
    Main verification endpoint.
    Handles:
      - Trusted academic domains → auto_verified
      - Commercial → routed to /commercial/ + emails sent
      - All other users → pending admin review + evidence saved
    """
    profile: UserProfile = request.user.profile

    # Already verified → go home
    if profile.verification_status in ("verified", "auto_verified"):
        return redirect("/")

    # Banned user shortcut
    if profile.verification_status == "banned":
        return redirect("/banned/")

    # Commercial user shortcut
    if profile.verification_status == "commercial":
        return redirect("/commercial/")

    # -----------------------------------------------------------------
    # POST: handle form submission
    # -----------------------------------------------------------------
    if request.method == "POST":
        form = VerificationForm(request.POST)

        if form.is_valid():

            # Basic field population
            org_type = form.cleaned_data["org_type"]
            profile.org_type = org_type

            # NEW: Save country (required field on the form)
            profile.country = form.cleaned_data["country"]

            profile.orcid_id = form.cleaned_data.get("orcid_id", "")
            profile.verification_notes = form.cleaned_data.get("notes", "")
            profile.terms_accepted_at = timezone.now()

            # Trusted-domain auto verification
            domain = extract_domain(request.user.email)
            trusted = is_trusted_domain(domain)

            if trusted:
                profile.verification_status = "auto_verified"
                profile.verified_at = timezone.now()
                profile.verified_by = None
                profile.save()
                messages.success(request, "Your account was automatically verified.")
                return redirect("/")

            # -----------------------------------------------------------------
            # COMMERCIAL FLOW (FULL EMAIL + ADMIN ALERT)
            # -----------------------------------------------------------------
            if org_type == "commercial":
                profile.verification_status = "commercial"
                profile.save()

                # Email user the commercial instructions
                send_mail(
                    subject="VariantValidator – Commercial Access Required",
                    message=(
                        f"Hello {request.user.username},\n\n"
                        "Your VariantValidator account is now set up — thank you for registering.\n\n"
                        "We’ve recently updated our service model to ensure we can maintain the infrastructure, "
                        "support continued development, and keep VariantValidator running reliably into the future.\n\n"
                        "Based on the information provided, your account has been classified as *commercial use*. "
                        "Commercial users require a paid licence to perform variant validations.\n\n"
                        "• If you would like to evaluate VariantValidator before committing, or wish to have your account reviewed, please email "
                        "admin@variantvalidator.org to request a manual trial allocation.\n"
                        "• Paid licensing options will be available soon. A purchase link will appear here once the "
                        "subscription portal is live:\n"
                        "  https://variantvalidator.org/paid-options/   <-- placeholder link\n\n"
                        "Until a licence or trial is applied to your account, your commercial quota is set to "
                        "zero variants per month.\n\n"
                        "Thank you for your interest in VariantValidator — your support helps us keep the service "
                        "available for the wider community.\n"
                        "— VariantValidator Team"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
                    recipient_list=[request.user.email],
                    fail_silently=True,
                )

                # Email admins notification of a new commercial submission
                admin_emails = list(
                    User.objects.filter(is_superuser=True).values_list("email", flat=True)
                )

                if admin_emails:
                    send_mail(
                        subject="VariantValidator: New Commercial Account Submission",
                        message=(
                            "A new commercial user has submitted information via the verification form.\n\n"
                            f"User: {request.user.username}\n"
                            f"Email: {request.user.email}\n"
                            "Organisation Type: Commercial\n\n"
                            "They have been routed to the commercial access workflow."
                        ),
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
                        recipient_list=admin_emails,
                        fail_silently=True,
                    )

                return redirect("/commercial/")

            # -----------------------------------------------------------------
            # NON-COMMERCIAL UNTRUSTED USERS (PENDING → ADMIN REVIEW)
            # -----------------------------------------------------------------
            profile.verification_status = "pending"
            profile.save()

            # Save evidence URLs
            url1 = form.cleaned_data.get("evidence_url_1")
            url2 = form.cleaned_data.get("evidence_url_2")

            if url1:
                VerificationEvidence.objects.create(
                    user=request.user,
                    url=url1,
                    kind=classify_url_kind(url1),
                )
            if url2:
                VerificationEvidence.objects.create(
                    user=request.user,
                    url=url2,
                    kind=classify_url_kind(url2),
                )

            # Notify admins
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
                        "You can review this user in the admin interface.\n"
                        f"{request.build_absolute_uri('/admin/userprofiles/userprofile/')}"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
                    recipient_list=admin_emails,
                    fail_silently=True,
                )

            # Email user confirming receipt
            send_mail(
                subject="VariantValidator: Your verification request is pending",
                message=(
                    "Thank you for submitting your verification request.\n\n"
                    "What happens next:\n"
                    " • We confirm your organisation and intended use.\n"
                    " • If more information is required, we will contact you.\n"
                    " • Once approved, you will be able to use VariantValidator immediately.\n\n"
                    "You can add more evidence anytime at:\n"
                    f"{request.build_absolute_uri('/verify/')}\n\n"
                    "Terms and Conditions of Use:\n"
                    "https://github.com/openvar/variantValidator/blob/master/README.md#terms-and-conditions-of-use\n"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
                recipient_list=[request.user.email],
                fail_silently=True,
            )

            messages.info(request, "Your verification request has been submitted.")
            return redirect("/verify/pending/")

    # ---------------------------------------------------------------------
    # GET: Show form (prefill from profile when possible)
    # ---------------------------------------------------------------------
    else:
        form = VerificationForm(initial={
            "org_type": profile.org_type or "",
            "country": getattr(profile, "country", None) or None,
            "orcid_id": profile.orcid_id or "",
            "notes": profile.verification_notes or "",
        })

    return render(request, "verify.html", {"form": form})


@login_required
def verify_pending(request):
    """Simple waiting page for users awaiting manual approval."""
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