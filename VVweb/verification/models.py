# verification/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

TRUST_CATEGORIES = (
    ("university", "University"),
    ("public_health", "Public Health"),
    ("government", "Government"),
    ("charity", "Charity / NGO"),
    ("research", "Research Institute"),
)


class TrustedDomain(models.Model):
    """
    Suffixes that auto-approve academic / public / research users.
    Example: 'ac.uk', 'edu', 'nhs.uk', 'nih.gov', 'ebi.ac.uk'
    """
    domain = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=50, choices=TRUST_CATEGORIES)
    notes = models.TextField(blank=True)
    auto_approve = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.domain} ({self.get_category_display()})"


class VerificationEvidence(models.Model):
    """
    Flexible evidence links supplied by users during verification.
    Allows multiple URLs per user (Scholar, LinkedIn, institutional page, etc.).
    """

    KIND_CHOICES = (
        ("institution", "Institutional Profile"),
        ("scholar", "Google Scholar"),
        ("orcid", "ORCID"),
        ("linkedin", "LinkedIn"),
        ("company", "Company Page"),
        ("other", "Other"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="verification_evidence",
    )

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="other")
    url = models.URLField()
    display_name = models.CharField(max_length=120, blank=True)

    submitted_at = models.DateTimeField(default=timezone.now)

    # Admin side: approval workflow
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_evidence_links",
    )

    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} → {self.kind}: {self.url}"

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
