from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
import json

from . import models

from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin


User = get_user_model()

# -------------------------------------------------------------------
# Register app-specific models
# -------------------------------------------------------------------
admin.site.register(models.Contact)
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

from allauth.account.models import EmailAddress


# ======================================================================
# UTILITY HELPERS
# ======================================================================

def get_primary_email(user):
    """Return the primary email address (lowercased) or None."""
    try:
        ea = EmailAddress.objects.filter(user=user, primary=True).first()
        if ea:
            return ea.email.lower().strip()
    except Exception:
        pass
    return None


def primary_email_domain(user):
    """Return domain of primary email (for inspection/debug)."""
    email = get_primary_email(user)
    if email and "@" in email:
        return email.split("@", 1)[1].lower()
    return "-"


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
# PLAN MANAGEMENT
# ======================================================================

@admin.action(description="Upgrade to PRO (1 calendar month)")
def upgrade_to_pro(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Only superusers can upgrade plans.",
            level=messages.ERROR,
        )
        return

    for quota in queryset:
        quota.plan = "pro"
        quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(
        request,
        f"{queryset.count()} user(s) upgraded to PRO (1 month)."
    )


@admin.action(description="Upgrade to ENTERPRISE (1 calendar month)")
def upgrade_to_enterprise(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Only superusers can upgrade to Enterprise.",
            level=messages.ERROR,
        )
        return

    for quota in queryset:
        quota.plan = "enterprise"
        quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(
        request,
        f"{queryset.count()} user(s) upgraded to ENTERPRISE (1 month)."
    )


@admin.action(description="Downgrade to STANDARD")
def downgrade_to_standard(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Only superusers can downgrade plans.",
            level=messages.ERROR,
        )
        return

    for quota in queryset:
        quota.plan = "standard"
        quota.subscription_expires = None
        quota.custom_limit = None
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(
        request,
        f"{queryset.count()} user(s) downgraded to STANDARD."
    )


# ======================================================================
# SUBSCRIPTION CONTROL
# ======================================================================

@admin.action(description="Extend subscription by 1 calendar month")
def extend_subscription_1_month(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Only superusers can extend subscriptions.",
            level=messages.ERROR,
        )
        return

    for quota in queryset:
        if quota.subscription_expires:
            quota.subscription_expires += relativedelta(months=1)
        else:
            quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.save()

    modeladmin.message_user(
        request,
        f"{queryset.count()} subscription(s) extended by 1 month."
    )


@admin.action(description="Expire subscription immediately")
def expire_subscription_now(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Only superusers can expire subscriptions.",
            level=messages.ERROR,
        )
        return

    updated = queryset.update(subscription_expires=timezone.now())
    modeladmin.message_user(
        request,
        f"{updated} subscription(s) expired immediately."
    )


# ======================================================================
# MAINTENANCE ACTIONS
# ======================================================================

@admin.action(description="Force recalculation (save trigger)")
def force_recalculation(modeladmin, request, queryset):
    for quota in queryset:
        quota.save()
    modeladmin.message_user(
        request,
        f"{queryset.count()} quota(s) recalculated."
    )


# ======================================================================
# VARIANTQUOTA ADMIN
# ======================================================================

@admin.register(VariantQuota)
class VariantQuotaAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "primary_email_domain",
        "verification_status",
        "plan",
        "institution",
        "institution_status",        # NEW
        "variant_limit_display",
        "count",
        "effective_allowance",
        "remaining",
        "last_reset",
        "subscription_expires",
        "custom_limit",
    )

    readonly_fields = ("remaining", "effective_allowance")

    search_fields = ("user__username", "user__email")

    list_filter = (
        "plan",
        "institution",
        "last_reset",
        "subscription_expires",
    )

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

    # ---------------------------
    # Extra helpful display methods
    # ---------------------------

    def primary_email_domain(self, obj):
        return primary_email_domain(obj.user)
    primary_email_domain.short_description = "Primary Domain"

    def verification_status(self, obj):
        return obj.user.profile.verification_status
    verification_status.short_description = "Verification"

    def variant_limit_display(self, obj):
        if obj.institution:
            return obj.institution.variant_limit
        return "-"
    variant_limit_display.short_description = "Institution Limit"

    # ---------------------------
    # NEW: Institution Active Indicator
    # ---------------------------
    def institution_status(self, obj):
        inst = obj.institution
        if not inst:
            return "-"
        return "✔" if inst.is_active else "✘"
    institution_status.short_description = "Inst. Active?"


# ======================================================================
# INSTITUTION ADMIN with ACTIVE/EXPIRED INDICATOR + FILTER
# ======================================================================

class InstitutionActiveFilter(admin.SimpleListFilter):
    title = "Institution Status"
    parameter_name = "inst_status"

    def lookups(self, request, model_admin):
        return [
            ("active", "Active"),
            ("expired", "Expired"),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        value = self.value()
        if value == "active":
            return queryset.filter(
                active=True
            ).filter(
                subscription_expires__isnull=True
            ) | queryset.filter(
                active=True,
                subscription_expires__gt=now
            )
        if value == "expired":
            return queryset.filter(
                active=True,
                subscription_expires__lt=now
            )
        return queryset


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
        "active_indicator",          # NEW
        "subscription_expires",
        "variant_limit",
        "seats_allowed",
        "seats_in_use",
    )

    search_fields = ("name",)
    list_filter = (
        InstitutionActiveFilter,     # NEW
        "active",
        "level",
    )

    inlines = [InstitutionDomainInline, InstitutionMembershipInline]
    readonly_fields = ("seats_in_use",)

    # NEW: Active/Expired icon in admin list
    def active_indicator(self, obj):
        return "✔" if obj.is_active else "✘"
    active_indicator.short_description = "Active?"


# -------------------------------------------------------------------
# Unregister default TaskResult admin so we can override it
# -------------------------------------------------------------------
try:
    admin.site.unregister(TaskResult)
except admin.sites.NotRegistered:
    pass

# -------------------------------------------------------------------
# SAFE JSON PARSER — ALWAYS RETURNS A DICT
# -------------------------------------------------------------------
def parse_result(obj):
    """
    Safely parse TaskResult.result. NEVER returns None.
    Handles:
      - None / empty values
      - invalid JSON
      - bytes
      - old Celery pickled formats
    """
    try:
        data = obj.result

        if not data:
            return {}

        if isinstance(data, dict):
            return data

        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return {}

        return {}

    except Exception:
        return {}

# -------------------------------------------------------------------
# ADMIN ACTION — SHOW USERNAME(S)
# -------------------------------------------------------------------
@admin.action(description="Show username(s) for selected tasks")
def show_usernames(modeladmin, request, queryset):
    for tr in queryset:
        data = parse_result(tr)
        uid = data.get("user_id")

        if not uid:
            modeladmin.message_user(
                request, f"Task {tr.task_id}: SYSTEM TASK (no user_id)"
            )
            continue

        try:
            user = User.objects.get(id=uid)
            modeladmin.message_user(
                request,
                f"Task {tr.task_id}: username={user.username}, email={user.email}"
            )
        except User.DoesNotExist:
            modeladmin.message_user(
                request, f"Task {tr.task_id}: user_id {uid} does NOT exist"
            )

# -------------------------------------------------------------------
# ADMIN ACTION — DISABLE USER ACCOUNTS
# -------------------------------------------------------------------
@admin.action(description="Disable associated user accounts")
def disable_users(modeladmin, request, queryset):
    disabled = 0
    for tr in queryset:
        uid = parse_result(tr).get("user_id")
        if not uid:
            continue
        try:
            user = User.objects.get(id=uid)
            user.is_active = False
            user.save(update_fields=["is_active"])
            disabled += 1
        except User.DoesNotExist:
            pass
    modeladmin.message_user(request, f"Disabled {disabled} user(s).")

# -------------------------------------------------------------------
# ADMIN ACTION — DELETE USER ACCOUNTS
# -------------------------------------------------------------------
@admin.action(description="DELETE associated user accounts (dangerous!)")
def delete_users(modeladmin, request, queryset):
    deleted = 0
    for tr in queryset:
        uid = parse_result(tr).get("user_id")
        if not uid:
            continue
        try:
            User.objects.get(id=uid).delete()
            deleted += 1
        except User.DoesNotExist:
            pass
    modeladmin.message_user(request, f"Deleted {deleted} user account(s).")

# -------------------------------------------------------------------
# CUSTOM TASKRESULT ADMIN
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    ordering = ("-date_done",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.defer("result")  # speeds up admin massively

    list_display = (
        "task_id",
        "safe_task_name",
        "status",
        "date_done",
        "safe_user_id",
        "safe_email",
        "safe_username",
        "user_link",
    )

    list_filter = ("status", "date_done")
    search_fields = ("task_id", "status", "result")
    actions = [show_usernames, disable_users, delete_users]

    # ---- SAFE ACCESSORS ----

    def safe_user_id(self, obj):
        try:
            if obj is None:
                return "-"
            data = parse_result(obj) or {}
            return data.get("user_id", "-")
        except Exception:
            return "-"

    safe_user_id.short_description = "User ID"

    def safe_email(self, obj):
        try:
            if obj is None:
                return "-"
            data = parse_result(obj) or {}
            return data.get("email", "-")
        except Exception:
            return "-"

    safe_email.short_description = "Email"

    def safe_task_name(self, obj):
        try:
            if obj is None:
                return "-"
            data = parse_result(obj) or {}
            if not isinstance(data, dict):
                data = {}
            return data.get("task_name") or obj.task_name or "-"
        except Exception:
            return "-"

    safe_task_name.short_description = "Task Name"

    def safe_username(self, obj):
        try:
            if obj is None:
                return "SYSTEM"
            data = parse_result(obj) or {}
            uid = data.get("user_id")
            if not uid:
                return "SYSTEM"
            try:
                return User.objects.get(id=uid).username
            except User.DoesNotExist:
                return f"(missing {uid})"
        except Exception:
            return "SYSTEM"

    # ---- CLICKABLE LINK TO USER ADMIN PAGE ----

    def user_link(self, obj):
        try:
            uid = parse_result(obj).get("user_id")
        except AttributeError:
            return "SYSTEM"
        try:
            User.objects.get(id=uid)
        except User.DoesNotExist:
            return f"(missing: {uid})"

        url = reverse("admin:auth_user_change", args=[uid])
        return format_html("<a href='{}'>View User</a>", url)

    user_link.short_description = "User Profile"

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/
# </LICENSE>