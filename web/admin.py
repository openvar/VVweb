from django.contrib import admin
from web.models import Contact, VariantQuota

@admin.action(description="Reset variant count to zero")
def reset_variant_count(modeladmin, request, queryset):
    for quota in queryset:
        quota.count = 0
        quota.last_reset = quota.get_now()
        quota.save()

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
    actions = [reset_variant_count]

# Register Contact
admin.site.register(Contact)
