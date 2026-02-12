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
    list_display = ('user', 'count', 'max_allowance', 'last_reset', 'remaining')
    readonly_fields = ('remaining',)
    search_fields = ('user__username', 'user__email')
    list_filter = ('last_reset',)
    actions = [reset_variant_count]

# Register Contact
admin.site.register(Contact)
