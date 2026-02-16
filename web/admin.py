from django.contrib import admin, messages
from django.utils import timezone
from datetime import timedelta
from web.models import Contact, VariantQuota


# =========================
# QUOTA ACTIONS
# =========================

@admin.action(description="Reset variant count to zero")
def reset_variant_count(modeladmin, request, queryset):
    updated = queryset.update(
        count=0,
        last_reset=timezone.now()
    )
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
    modeladmin.message_user(request, f"{updated} custom limits cleared.")


# =========================
# PLAN MANAGEMENT
# =========================

@admin.action(description="Upgrade to PRO (30 days)")
def upgrade_to_pro(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can upgrade plans.", level=messages.ERROR)
        return

    for quota in queryset:
        quota.plan = "pro"
        quota.subscription_expires = timezone.now() + timedelta(days=30)
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} user(s) upgraded to PRO.")


@admin.action(description="Downgrade to FREE")
def downgrade_to_free(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can downgrade plans.", level=messages.ERROR)
        return

    for quota in queryset:
        quota.plan = "free"
        quota.subscription_expires = None
        quota.custom_limit = None
        quota.count = 0
        quota.last_reset = timezone.now()
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} user(s) downgraded to FREE.")


# =========================
# SUBSCRIPTION CONTROL
# =========================

@admin.action(description="Extend subscription by 30 days")
def extend_subscription_30(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can extend subscriptions.", level=messages.ERROR)
        return

    for quota in queryset:
        if quota.subscription_expires:
            quota.subscription_expires += timedelta(days=30)
        else:
            quota.subscription_expires = timezone.now() + timedelta(days=30)
        quota.save()

    modeladmin.message_user(request, f"{queryset.count()} subscription(s) extended by 30 days.")


@admin.action(description="Expire subscription immediately")
def expire_subscription_now(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(request, "Only superusers can expire subscriptions.", level=messages.ERROR)
        return

    updated = queryset.update(subscription_expires=timezone.now())
    modeladmin.message_user(request, f"{updated} subscription(s) expired immediately.")


# =========================
# MAINTENANCE
# =========================

@admin.action(description="Force recalculation (save trigger)")
def force_recalculation(modeladmin, request, queryset):
    for quota in queryset:
        quota.save()
    modeladmin.message_user(request, f"{queryset.count()} quota(s) recalculated.")


# =========================
# ADMIN REGISTRATION
# =========================

@admin.register(VariantQuota)
class VariantQuotaAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'plan',
        'count',
        'max_allowance',
        'remaining',
        'last_reset',
        'subscription_expires',
        'custom_limit'
    )
    readonly_fields = ('remaining', 'max_allowance')
    search_fields = ('user__username', 'user__email')
    list_filter = ('plan', 'last_reset', 'subscription_expires')
    actions = [
        reset_variant_count,
        grant_100_bonus,
        grant_1000_bonus,
        clear_custom_limit,
        upgrade_to_pro,
        downgrade_to_free,
        extend_subscription_30,
        expire_subscription_now,
        force_recalculation,
    ]


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
