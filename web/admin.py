# web/admin.py

from django.contrib import admin, messages
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from web.models import (
    Contact,
    VariantQuota,
    Institution,
    InstitutionDomain,
    InstitutionMembership,
)


# ======================================================================
# QUOTA ACTIONS
# ======================================================================

@admin.action(description="Reset variant count to zero")
def reset_variant_count(modeladmin, request, queryset):
    updated = queryset.update(count=0, last_reset=timezone.now())
    modeladmin.message_user(request, f"{updated} quota(s) reset successfully.")


@admin.action(description="Grant 100 bonus variants")
def grant_100_bonus(modeladmin, request, queryset):
    for quota in queryset:
        quota.custom_limit = (quota.custom_limit or 0) + 100
        quota.save()
    modeladmin.message_user(request, f"{queryset.count()} user(s) granted 100 bonus variants.")


@admin.action(description="Grant 1000 bonus variants")
def grant_1000_bonus(modeladmin, request, queryset):
    for quota in queryset:
        quota.custom_limit = (quota.custom_limit or 0) + 1000
        quota.save()
    modeladmin.message_user(request, f"{queryset.count()} user(s) granted 1000 bonus variants.")


@admin.action(description="Clear custom limit")
def clear_custom_limit(modeladmin, request, queryset):
    updated = queryset.update(custom_limit=None)
    modeladmin.message_user(request, f"{updated} custom limit(s) cleared.")


# ======================================================================
# PLAN MANAGEMENT — UPDATED TO CALENDAR MONTHS
# ======================================================================

@admin.action(description="Upgrade to PRO (1 calendar month)")
def upgrade_to_pro(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can upgrade plans.", level=messages.ERROR)
        return

    for quota in queryset:
        quota.plan = "pro"
        quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} user(s) upgraded to PRO (1 month).")


@admin.action(description="Upgrade to ENTERPRISE (1 calendar month)")
def upgrade_to_enterprise(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can upgrade to Enterprise.", level=messages.ERROR)
        return

    for quota in queryset:
        quota.plan = "enterprise"
        quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} user(s) upgraded to ENTERPRISE (1 month).")


@admin.action(description="Downgrade to STANDARD")
def downgrade_to_standard(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can downgrade plans.", level=messages.ERROR)
        return

    for quota in queryset:
        quota.plan = "standard"
        quota.subscription_expires = None
        quota.custom_limit = None
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} user(s) downgraded to STANDARD.")


# ======================================================================
# SUBSCRIPTION CONTROL — UPDATED TO CALENDAR MONTHS
# ======================================================================

@admin.action(description="Extend subscription by 1 calendar month")
def extend_subscription_1_month(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can extend subscriptions.", level=messages.ERROR)
        return

    for quota in queryset:
        if quota.subscription_expires:
            quota.subscription_expires += relativedelta(months=1)
        else:
            quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} subscription(s) extended by 1 month.")


@admin.action(description="Expire subscription immediately")
def expire_subscription_now(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can expire subscriptions.", level=messages.ERROR)
        return

    updated = queryset.update(subscription_expires=timezone.now())
    modeladmin.message_user(request, f"{updated} subscription(s) expired immediately.")


# ======================================================================
# MAINTENANCE
# ======================================================================

@admin.action(description="Force recalculation (save trigger)")
def force_recalculation(modeladmin, request, queryset):
    for quota in queryset:
        quota.save()
    modeladmin.message_user(request, f"{queryset.count()} quota(s) recalculated.")


# ======================================================================
# VARIANTQUOTA ADMIN
# ======================================================================

@admin.register(VariantQuota)
class VariantQuotaAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "institution",
        "count",
        "effective_allowance",
        "remaining",
        "last_reset",
        "subscription_expires",
        "custom_limit",
    )

    readonly_fields = ("remaining", "effective_allowance")

    search_fields = ("user__username", "user__email")

    list_filter = ("plan", "institution", "last_reset", "subscription_expires")

    actions = [
        reset_variant_count,
        grant_100_bonus,
        grant_1000_bonus,
        clear_custom_limit,
        upgrade_to_pro,
        upgrade_to_enterprise,
        downgrade_to_standard,
        extend_subscription_1_month,
        expire_subscription_now,
        force_recalculation,
    ]


# ======================================================================
# INSTITUTION ADMIN
# ======================================================================

class InstitutionDomainInline(admin.TabularInline):
    model = InstitutionDomain
    extra = 1


class InstitutionMembershipInline(admin.TabularInline):
    model = InstitutionMembership
    extra = 0
    readonly_fields = ("verified_at", "email_used", "source")


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "active",
        "subscription_expires",
        "variant_limit",
        "seats_allowed",
        "seats_in_use",
    )

    search_fields = ("name",)
    list_filter = ("active", "level")

    inlines = [InstitutionDomainInline, InstitutionMembershipInline]
    readonly_fields = ("seats_in_use",)


# ======================================================================
# MEMBERSHIP ADMIN
# ======================================================================

@admin.register(InstitutionMembership)
class InstitutionMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "institution",
        "active",
        "source",
        "email_used",
        "verified_at",
    )
    list_filter = ("active", "source", "institution")
    search_fields = ("user__username", "user__email", "institution__name")


# ======================================================================
# CONTACT ADMIN
# ======================================================================

admin.site.register(Contact)


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
