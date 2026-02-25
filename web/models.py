# web/models.py
#
# Expanded to support:
# - Institutions with multiple domains
# - Proper institutional membership table
# - Per-institution variant limits
# - Retains existing VariantQuota structure
# - Personal (standard/pro/enterprise) plans AND institution inheritance
# - Commercial users ALWAYS inherit COMMERCIAL_TRIAL_LIMIT (0 unless trial assigned)
# - Admins can assign custom_limit as trial
# - Monthly reset clears trial (custom_limit) automatically

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from dateutil.relativedelta import relativedelta


# -------------------------------------------------------
# CONTACT MODEL
# -------------------------------------------------------
class Contact(models.Model):
    nameval = models.CharField(max_length=100, verbose_name='Name')
    emailval = models.EmailField(verbose_name='Email')
    variant = models.CharField(max_length=100, null=True, blank=True)
    question = models.TextField()
    asked = models.DateTimeField(default=timezone.now)
    answered = models.BooleanField(default=False)

    def __str__(self):
        return "%s - %s (dealt with: %s)" % (self.nameval, self.asked.date(), self.answered)


# =======================================================================
#   INSTITUTION STRUCTURE
# =======================================================================

class Institution(models.Model):
    """
    Represents an organisation (NHS Trust, University, Hospital, Lab).
    Users may join based on verified email domain or manual membership.
    """
    name = models.CharField(max_length=200)

    # Whether the institution subscription is active
    active = models.BooleanField(default=True)
    subscription_expires = models.DateTimeField(null=True, blank=True)

    # Optional seats
    seats_allowed = models.PositiveIntegerField(null=True, blank=True)
    seats_in_use = models.PositiveIntegerField(default=0)

    # Stripe or purchase-order metadata
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    po_number = models.CharField(max_length=100, null=True, blank=True)

    # Per-institution variant limit (default = global INSTITUTION_LIMIT)
    variant_limit = models.PositiveIntegerField(
        default=getattr(settings, "INSTITUTION_LIMIT", 1000000),
        help_text="Monthly variant allowance for this institution."
    )

    # For future feature gating
    level = models.CharField(max_length=50, default="institution_basic")

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        """True if institution is active AND subscription (if any) is valid."""
        if not self.active:
            return False
        if self.subscription_expires is None:
            return True
        return timezone.now() < self.subscription_expires


# -------------------------------------------------------
# INSTITUTION DOMAIN SUFFIXES
# -------------------------------------------------------
class InstitutionDomain(models.Model):
    """
    Multiple email domains belonging to an institution.
    e.g. nhs.uk, manchester.ac.uk, trust.nhs.uk
    """
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="domains"
    )
    domain = models.CharField(
        max_length=200,
        help_text="Domain suffix. Example: 'nhs.uk' or 'manchester.ac.uk'"
    )

    class Meta:
        unique_together = ("institution", "domain")

    def __str__(self):
        return f"{self.institution.name}: {self.domain}"


# -------------------------------------------------------
# INSTITUTION MEMBERSHIP
# -------------------------------------------------------
class InstitutionMembership(models.Model):
    """
    A user belongs to at most one active institution at a time.
    Membership is created automatically when a verified email domain matches.
    Can also be created manually by an admin.
    """
    SOURCE_CHOICES = [
        ("domain", "Domain-based"),
        ("manual", "Manual / Admin assigned"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="institution_memberships"
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="memberships"
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="domain"
    )
    active = models.BooleanField(default=True)
    email_used = models.EmailField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "institution")

    def __str__(self):
        return f"{self.user.username} → {self.institution.name} ({'active' if self.active else 'inactive'})"


# =======================================================================
#   VARIANT QUOTA (CORRECTED FOR COMMERCIAL USERS)
# =======================================================================

class VariantQuota(models.Model):
    """
    Personal subscription + institutional inheritance + monthly usage.
    """

    PLAN_CHOICES = [
        ("standard", "Standard"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    # One per user
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="variant_quota"
    )

    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="standard"
    )

    subscription_expires = models.DateTimeField(null=True, blank=True)

    # Monthly counts
    count = models.PositiveIntegerField(default=0)
    last_reset = models.DateTimeField(default=timezone.now)

    # Manual override (used for commercial trial variants)
    custom_limit = models.PositiveIntegerField(null=True, blank=True)

    # Stripe metadata
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)

    # Institution pointer (if membership active)
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_quotas"
    )

    # -------------------------------------------------------
    # PERSONAL ALLOWANCE (COMMERCIAL FIX INCLUDED)
    # -------------------------------------------------------
    @property
    def personal_allowance(self):
        """
        Base allowance before institutional uplift.

        Order of precedence:
          1. custom_limit → ALWAYS wins (manual trial/allocation)
          2. commercial user with standard plan → COMMERCIAL_TRIAL_LIMIT (e.g., 0)
          3. plan-based defaults (standard/pro/enterprise)
        """

        # 1. Manual trial allocation
        if self.custom_limit is not None:
            return self.custom_limit

        # 2. Commercial users inherit COMMERCIAL_TRIAL_LIMIT
        profile = getattr(self.user, "profile", None)
        if (
            profile is not None
            and getattr(profile, "verification_status", None) == "commercial"
            and self.plan == "standard"
        ):
            return getattr(settings, "COMMERCIAL_TRIAL_LIMIT", 0)

        # 3. Plan defaults
        if self.plan == "standard":
            return getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)

        if self.plan == "pro":
            return getattr(settings, "PRO_LIMIT", 1000)

        if self.plan == "enterprise":
            return getattr(settings, "ENTERPRISE_LIMIT", 1000000)

        return getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)

    # -------------------------------------------------------
    # EFFECTIVE ALLOWANCE (institution may uplift)
    # -------------------------------------------------------
    @property
    def effective_allowance(self):
        base = self.personal_allowance

        if self.institution and self.institution.is_active:
            return max(base, self.institution.variant_limit)

        return base

    # -------------------------------------------------------
    # CHECK PERSONAL SUBSCRIPTION EXPIRY
    # -------------------------------------------------------
    def check_subscription_status(self):
        if (
            self.plan != "standard"
            and self.subscription_expires
            and timezone.now() >= self.subscription_expires
        ):
            self.plan = "standard"
            self.subscription_expires = None
            self.count = 0
            self.last_reset = timezone.now()
            self.custom_limit = None
            self.save()

    # -------------------------------------------------------
    # MONTHLY RESET
    # -------------------------------------------------------
    def reset_if_needed(self):
        """
        Reset usage one calendar month after last_reset.
        Trials disappear because custom_limit resets to None.
        """
        now = timezone.now()
        next_reset = self.last_reset + relativedelta(months=1)

        if now >= next_reset:
            self.count = 0
            self.last_reset = now
            self.custom_limit = None    # TRIAL EXPIRES
            self.save()

    # -------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------
    def remaining(self):
        self.check_subscription_status()
        self.reset_if_needed()
        return max(self.effective_allowance - self.count, 0)

    def add_variants(self, n):
        self.check_subscription_status()
        self.reset_if_needed()

        if self.count + n > self.effective_allowance:
            raise ValueError("Monthly allowance exceeded")

        self.count += n
        self.save()


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
