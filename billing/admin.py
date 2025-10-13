from django.utils import timezone
from django.contrib import admin
from .models import (
    SubscriptionPlan,
    UserSubscription,
    UserCreditBalance,
    AlgorithmPricing,
    TransactionHistory,
    InvoiceRequest
)
from django.utils.html import format_html


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_ft', 'duration_days', 'is_ad_free')
    search_fields = ('name',)
    list_filter = ('is_ad_free',)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'end_date', 'is_active', 'remaining_days')
    search_fields = ('user__username', 'plan__name')
    list_filter = ('is_active', 'plan')
    raw_id_fields = ('user', 'plan')

    def remaining_days(self, obj):
        """Kiszámítja a hátralévő napokat."""
        if obj.is_active and obj.end_date:
            days = (obj.end_date - timezone.now()).days
            return format_html(
                '<span class="{}">{} nap</span>',
                'font-weight: bold; color: green;' if days > 7 else 'color: orange;' if days > 0 else 'color: red;',
                days
            )
        return "Lejárt/Inaktív"
    remaining_days.short_description = 'Hátralévő napok'


@admin.register(UserCreditBalance)
class UserCreditBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_amount')
    search_fields = ('user__username',)
    raw_id_fields = ('user',)


@admin.register(AlgorithmPricing)
class AlgorithmPricingAdmin(admin.ModelAdmin):
    list_display = ('algorithm_name', 'cost_per_run')
    search_fields = ('algorithm_name',)


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'transaction_type', 'amount', 'related_user_display')
    list_filter = ('transaction_type', 'timestamp')
    search_fields = ('user__username', 'related_user__username', 'description')
    date_hierarchy = 'timestamp'
    raw_id_fields = ('user', 'related_user')

    def related_user_display(self, obj):
        return obj.related_user.username if obj.related_user else '-'
    related_user_display.short_description = 'Kapcsolódó felhasználó'


@admin.register(InvoiceRequest)
class InvoiceRequestAdmin(admin.ModelAdmin):
    list_display = ('request_date', 'user', 'amount_ft', 'target_user', 'status')
    list_filter = ('status',)
    search_fields = ('user__username', 'target_user__username', 'billing_name')
    date_hierarchy = 'request_date'
    raw_id_fields = ('user', 'target_user')

    actions = ['mark_sent']

    @admin.action(description='Jelölje meg Elküldöttként (SENT)')
    def mark_sent(self, request, queryset):
        queryset.update(status='SENT')