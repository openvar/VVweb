from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
import json
from dateutil.relativedelta import relativedelta

from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin
from allauth.account.models import EmailAddress

from userprofiles.models import UserProfile
from web.models import (
    Contact,
    VariantQuota,
    Institution,
    InstitutionDomain,
    InstitutionMembership,
)

User = get_user_model()

# -------------------------------------------------------------------
# USER ADMIN (ADD LINK TO USERPROFILE)
# -------------------------------------------------------------------

class CustomUserAdmin(DjangoUserAdmin):
    readonly_fields = DjangoUserAdmin.readonly_fields + ("user_profile_link",)

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("User Profile", {"fields": ("user_profile_link",)}),
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
        return format_html("<a href='{}'>View User Profile</a>", url)

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
    ea = EmailAddress.objects.filter(user=user, primary=True).first()
    if ea:
        return ea.email.lower().strip()
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
# TASKRESULT ADMIN
# -------------------------------------------------------------------

try:
    admin.site.unregister(TaskResult)
except NotRegistered:
    pass


def parse_result(obj):
    """
    Safely parse TaskResult.result.
    ALWAYS returns a dict.
    """
    if obj is None:
        return {}

    try:
        data = obj.result
    except Exception:
        return {}

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

# -------------------------------------------------------------------
# TASKRESULT ACTIONS (RESTORED)
# -------------------------------------------------------------------

@admin.action(description="Show username(s) for selected tasks")
def show_usernames(modeladmin, request, queryset):
    for tr in queryset:
        data = parse_result(tr)
        uid = data.get("user_id")

        if not uid:
            modeladmin.message_user(request, f"{tr.task_id}: SYSTEM TASK")
            continue

        try:
            user = User.objects.get(id=uid)
            modeladmin.message_user(
                request,
                f"{tr.task_id}: {user.username} ({user.email})"
            )
        except User.DoesNotExist:
            modeladmin.message_user(
                request, f"{tr.task_id}: user_id {uid} missing"
            )


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
    modeladmin.message_user(request, f"Deleted {deleted} user(s).")


@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    ordering = ("-date_done",)

    def get_queryset(self, request):
        return super().get_queryset(request).defer("result")

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

    def safe_user_id(self, obj):
        if obj is None:
            return "-"
        data = parse_result(obj)
        if not isinstance(data, dict):
            return "-"
        return data.get("user_id", "-")

    safe_user_id.short_description = "User ID"

    def safe_email(self, obj):
        if obj is None:
            return "-"
        data = parse_result(obj)
        if not isinstance(data, dict):
            return "-"
        return data.get("email", "-")

    def safe_task_name(self, obj):
        if obj is None:
            return "-"
        data = parse_result(obj)
        if not isinstance(data, dict):
            return obj.task_name or "-"
        return data.get("task_name") or obj.task_name or "-"

    def safe_username(self, obj):
        if obj is None:
            return "-"
        data = parse_result(obj)
        if not isinstance(data, dict):
            return "SYSTEM"
        uid = data.get("user_id")
        if not uid:
            return "SYSTEM"
        try:
            return User.objects.get(id=uid).username
        except User.DoesNotExist:
            return f"(missing {uid})"

    def user_link(self, obj):
        if obj is None:
            return "-"
        data = parse_result(obj)
        if not isinstance(data, dict):
            return "SYSTEM"
        uid = data.get("user_id")
        if not uid:
            return "SYSTEM"
        try:
            User.objects.get(id=uid)
        except User.DoesNotExist:
            return f"(missing {uid})"
        url = reverse("admin:auth_user_change", args=[uid])
        return format_html("<a href='{}'>View User</a>", url)

    user_link.short_description = "User Profile"