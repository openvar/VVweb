# verification/admin.py

from django.contrib import admin
from django.utils import timezone
from .models import TrustedDomain, VerificationEvidence
from .validators import (
    is_valid_orcid,
    is_probable_google_scholar,
    is_linkedin_profile,
    looks_like_company_site,
)


@admin.register(TrustedDomain)
class TrustedDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "category", "auto_approve")
    search_fields = ("domain",)
    list_filter = ("category", "auto_approve")


@admin.action(description="Mark selected evidence as verified")
def mark_evidence_verified(modeladmin, request, queryset):
    now = timezone.now()
    updated = 0
    for item in queryset:
        item.verified = True
        item.verified_at = now
        item.verified_by = request.user
        item.save()
        updated += 1
    modeladmin.message_user(request, f"{updated} item(s) verified.")


@admin.register(VerificationEvidence)
class VerificationEvidenceAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "url", "verified", "submitted_at")
    list_filter = ("kind", "verified", "submitted_at")
    search_fields = ("user__username", "user__email", "url", "display_name")
    actions = [mark_evidence_verified]

    readonly_fields = (
        "submitted_at",
        "verified",
        "verified_at",
        "verified_by",
        "notes",
        "url",
        "kind",
    )


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
