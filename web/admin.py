# web/admin.py# web/adminfrom django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
import json
from dateutil.relativedelta import relativedelta
from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin
from allauth.account.models import EmailAddress
from userprofiles.models import UserProfile
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from web.models import (
    Contact,
    VariantQuota,
    Institution,
    InstitutionDomain,
    InstitutionMembership,
)

# -------------------------------------------------------------------
# USER ADMIN (ADD LINK TO USERPROFILE)
# -------------------------------------------------------------------

User = get_user_model()


class CustomUserAdmin(DjangoUserAdmin):
    """
    Extend the default Django User admin to include
    a direct link to the associated UserProfile.
    """

    readonly_fields = DjangoUserAdmin.readonly_fields + (
        "user_profile_link",
    )

    def user_profile_link(self, obj):
        if not obj:
            return "-"

        try:
            profile = obj.profile
        except UserProfile.DoesNotExist:
            return "No user profile"

        url = reverse(
            "admin:userprofiles_userprofile_change",
            args=(profile.id,),
        )
        return format_html(
            "<a href='{}'>View User Profile</a>",
            url,
        )

    user_profile_link.short_description = "User Profile"


try:
    admin.site.unregister(User)
except NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)

# -------------------------------------------------------------------
# BASIC REGISTRATIONS
# -------------------------------------------------------------------

admin.site.register(Contact)

# -------------------------------------------------------------------
# UTILITY HELPERS
# -------------------------------------------------------------------

def get_primary_email(user):
    try:
        ea = EmailAddress.objects.filter(user=user, primary=True).first()
        if ea:
            return ea.email.lower().strip()
    except Exception:
        pass
    return None


def primary_email_domain(user):
    email = get_primary_email(user)
    if email and "@" in email:
        return email.split("@", 1)[1].lower()
    return "-"


# -------------------------------------------------------------------
# QUOTA ACTIONS
# -------------------------------------------------------------------

@admin.action(description="Reset variant count to zero")
def reset_variant_count(modeladmin, request, queryset):
    updated = queryset.update(count=0, last_reset=timezone.now())
    modeladmin.message_user(request, f"{updated} quota(s) reset successfully.")


@admin.action(description="Grant 100 bonus variants")
def grant_100_bonus(modeladmin, request, queryset):
    for quota in queryset:
        quota.custom_limit = (quota.custom_limit or 0) + 100
        quota.save()


@admin.action(description="Grant 1000 bonus variants")
def grant_1000_bonus(modeladmin, request, queryset):
    for quota in queryset:
        quota.custom_limit = (quota.custom_limit or 0) + 1000
        quota.save()


@admin.action(description="Clear custom limit")
def clear_custom_limit(modeladmin, request, queryset):
    queryset.update(custom_limit=None)


# -------------------------------------------------------------------
# PLAN MANAGEMENT
# -------------------------------------------------------------------

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


@admin.action(description="Upgrade to ENTERPRISE (1 calendar month)")
def upgrade_to_enterprise(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Only superusers can upgrade plans.",
            level=messages.ERROR,
        )
        return

    for quota in queryset:
        quota.plan = "enterprise"
        quota.subscription_expires = timezone.now() + relativedelta(months=1)
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()


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


# -------------------------------------------------------------------
# SUBSCRIPTION CONTROL
# -------------------------------------------------------------------

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
        quota.subscription_expires = (
            quota.subscription_expires + relativedelta(months=1)
            if quota.subscription_expires
            else timezone.now() + relativedelta(months=1)
        )
        quota.save()


@admin.action(description="Expire subscription immediately")
def expire_subscription_now(modeladmin, request, queryset):
    queryset.update(subscription_expires=timezone.now())


# -------------------------------------------------------------------
# VARIANTQUOTA ADMIN
# -------------------------------------------------------------------

@admin.register(VariantQuota)
class VariantQuotaAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "primary_email_domain",
        "verification_status",
        "plan",
        "institution",
        "institution_status",
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
    list_filter = ("plan", "institution")

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
    ]

    def primary_email_domain(self, obj):
        return primary_email_domain(obj.user)

    def verification_status(self, obj):
        return obj.user.profile.verification_status

    def variant_limit_display(self, obj):
        return obj.institution.variant_limit if obj.institution else "-"

    def institution_status(self, obj):
        return "✔" if obj.institution and obj.institution.is_active else "✘"


# -------------------------------------------------------------------
# INSTITUTION ADMIN
# -------------------------------------------------------------------

class InstitutionActiveFilter(admin.SimpleListFilter):
    title = "Institution Status"
    parameter_name = "inst_status"

    def lookups(self, request, model_admin):
        return [("active", "Active"), ("expired", "Expired")]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "active":
            return queryset.filter(active=True, subscription_expires__gt=now)
        if self.value() == "expired":
            return queryset.filter(active=True, subscription_expires__lt=now)
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
        "subscription_expires",
        "variant_limit",
        "seats_allowed",
        "seats_in_use",
    )

    list_filter = (InstitutionActiveFilter, "active")
    search_fields = ("name",)
    inlines = [InstitutionDomainInline, InstitutionMembershipInline]
    readonly_fields = ("seats_in_use",)


# -------------------------------------------------------------------
# TASKRESULT ADMIN (UNCHANGED)
# -------------------------------------------------------------------

try:
    admin.site.unregister(TaskResult)
except NotRegistered:
    pass


def parse_result(obj):
    try:
        if not obj.result:
            return {}
        if isinstance(obj.result, dict):
            return obj.result
        if isinstance(obj.result, bytes):
            return json.loads(obj.result.decode("utf-8", errors="ignore"))
        return json.loads(obj.result)
    except Exception:
        return {}


@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    ordering = ("-date_done",)

    list_display = (
        "task_id",
        "status",
        "date_done",
        "user_link",
    )

    def user_link(self, obj):
        uid = parse_result(obj).get("user_id")
        if not uid:
            return "SYSTEM"
        try:
            reverse("admin:auth_user_change", args=[uid])
        except Exception:
            return "MISSING"
        return format_html(
            "<a href='{}'>View User</a>",
            reverse("admin:auth_user_change", args=[uid]),
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

