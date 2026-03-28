# userprofiles/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

# Enforce unique email across all users
User._meta.get_field('email')._unique = True


# ------------------------------------------------------------
# Organisation Types (mandatory user declaration)
# ------------------------------------------------------------
ORG_TYPES = (
    ("university", "University"),
    ("public_health", "Public Health"),
    ("government", "Government"),
    ("charity", "Charity / NGO"),
    ("research", "Research Institute"),
    ("commercial", "Commercial Organisation"),
)


# ------------------------------------------------------------
# Verification Status (system decision)
# ------------------------------------------------------------
VERIFICATION_STATUS = (
    ("not_started", "Not Started"),
    ("auto_verified", "Auto Verified"),
    ("pending", "Pending Manual Review"),
    ("verified", "Verified Non‑Commercial User"),
    ("commercial", "Commercial – Requires Paid Licence"),
    ("banned", "Banned / Malicious User"),
)


# ------------------------------------------------------------
# Existing job roles (kept from your original)
# ------------------------------------------------------------
JOBS = (
    ('academic', 'Research (academic)'),
    ('commercial', 'Research (commercial)'),
    ('clinical', 'Clinical'),
    ('healthcare', 'Healthcare'),
    ('student', 'Student'),
    ('other', 'Other'),
)


class UserProfile(models.Model):
    """
    Stores identity, affiliation, and verification state for VariantValidator users.
    """

    user = models.OneToOneField(
        User,
        null=True,
        related_name="profile",
        verbose_name=_('User'),
        on_delete=models.CASCADE
    )

    # -------- Existing fields you already had --------
    institution = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        verbose_name=_('Institution')
    )
    country = CountryField()
    jobrole = models.CharField(
        max_length=140,
        blank=True,
        verbose_name=_('Job Role/Interest'),
        choices=JOBS
    )
    completion_level = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Profile completion percentage')
    )
    email_is_verified = models.BooleanField(
        default=False,
        verbose_name=_('Email is verified')
    )
    personal_info_is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Personal info completed')
    )
    contacted_for_deletion = models.BooleanField(
        default=False,
        verbose_name=_('Has been told account will be deleted')
    )

    # -------- Mandatory fields --------
    org_type = models.CharField(
        max_length=50,
        choices=ORG_TYPES,
        null=True,
        blank=True,
        verbose_name=_("Organisation Type")
    )

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default="not_started",
        verbose_name=_("Verification Status")
    )

    # -------- Identity evidence fields --------
    orcid_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("ORCID ID")
    )

    affiliation_url = models.URLField(
        blank=True,
        verbose_name=_("Institutional Profile URL")
    )

    company_profile_url = models.URLField(
        blank=True,
        verbose_name=_("Company / LinkedIn URL")
    )

    verification_notes = models.TextField(
        blank=True,
        verbose_name=_("Additional Verification Notes")
    )

    # -------- Admin/audit-trail fields --------
    terms_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Terms Accepted At")
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Verified At")
    )

    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_users",
        verbose_name=_("Verified By")
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_("Rejection Reason")
    )

    # -------- NEW: reset markers to distinguish NEW vs RESET --------
    RESET_REASON_CHOICES = (
        ("admin", "Admin"),
        ("auto", "AutoExpired"),
    )
    reset_reason = models.CharField(
        max_length=16,
        choices=RESET_REASON_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Reset Reason"),
        help_text=_("Blank for true new users; 'admin' for manual reset; 'auto' for auto-expiry reset.")
    )
    reset_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reset At"),
        help_text=_("Timestamp of the last reset to new-account state.")
    )

    class Meta:
        verbose_name = _('User profile')
        verbose_name_plural = _('User profiles')
        indexes = [
            models.Index(fields=["reset_reason"]),
            models.Index(fields=["terms_accepted_at"]),
        ]

    def __str__(self):
        return f"User profile: {self.user.username}"

    # -------- Completion helpers --------
    def get_completion_level(self):
        level = 0
        if self.email_is_verified:
            level += 50
        if self.personal_info_is_completed:
            level += 50
        return level

    def update_completion_level(self):
        self.completion_level = self.get_completion_level()
        self.save(update_fields=["completion_level"])

    # -------- Convenience predicates --------
    def is_banned(self):
        return self.verification_status == "banned"

    def is_verified(self):
        return self.verification_status in ("verified", "auto_verified")

    def requires_commercial(self):
        return self.verification_status == "commercial"

    def requires_verification(self):
        return self.verification_status in ("not_started", "pending")

    def is_revalidation(self) -> bool:
        """
        True when this profile was reset (admin or auto) and is currently in
        a 'new-account' state (terms_accepted_at is None).
        """
        return self.terms_accepted_at is None and self.reset_reason is not None

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
