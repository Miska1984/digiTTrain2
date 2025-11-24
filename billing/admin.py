# billing/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import (
    SubscriptionPlan,
    UserSubscription,
    InvoiceRequest,
    JobPrice,
    UserJobDiscount,
    UserWallet,
    FinancialTransaction,
    TopUpInvoice,
    UserAnalysisBalance,
    AnalysisTransaction,
    AdViewStreak
)
from .utils import add_analysis_balance

# ============================================================
# INLINE ADMINOK (Segédeszközök)
# ============================================================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_ft', 'duration_days', 'is_ad_free')
    list_filter = ('is_ad_free',)
    search_fields = ('name',)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date')
    search_fields = ('user__username',)
    list_filter = ('plan',)


@admin.register(JobPrice)
class JobPriceAdmin(admin.ModelAdmin):
    list_display = ('name', 'analysis_count', 'price_ft')
    ordering = ('price_ft',)


@admin.register(UserJobDiscount)
class UserJobDiscountAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_type', 'discount_percentage')
    list_filter = ('job_type',)
    search_fields = ('user__username',)


@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_ft')
    search_fields = ('user__username',)


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_ft', 'transaction_type', 'transaction_status', 'timestamp')
    list_filter = ('transaction_type', 'transaction_status')
    search_fields = ('user__username',)
    ordering = ('-timestamp',)


@admin.register(UserAnalysisBalance)
class UserAnalysisBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'analysis_count')
    search_fields = ('user__username',)


@admin.register(AnalysisTransaction)
class AnalysisTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'timestamp', 'description')
    search_fields = ('user__username',)
    ordering = ('-timestamp',)


@admin.register(AdViewStreak)
class AdViewStreakAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_streak', 'total_rewards_earned', 'last_view_date')
    search_fields = ('user__username',)
    ordering = ('-last_view_date',)


# ============================================================
# 🔹  KULCS: ADMIN ACTIONS – SZÁMLAJÓVÁHAGYÁSOK
# ============================================================

@admin.action(description="✅ Jóváhagyás: Elemzési csomag aktiválása")
def approve_analysis_invoice(modeladmin, request, queryset):
    """
    Admin jóváhagyás után:
    - Hozzáadja a usernek a megvásárolt elemzéseket
    - Naplózza tranzakcióként
    - Frissíti a számla státuszát SENT-re
    """
    approved = 0
    for invoice in queryset.filter(status='PENDING', related_analysis_package__isnull=False):
        pkg = invoice.related_analysis_package
        user = invoice.target_user
        add_analysis_balance(
            user=user,
            amount=pkg.analysis_count,
            description=f"Elemzési csomag aktiválva: {pkg.name}"
        )
        invoice.status = 'SENT'
        invoice.save()
        approved += 1
    modeladmin.message_user(request, f"{approved} db elemzési csomag jóváírva és aktiválva.")


@admin.action(description="🚫 Elutasítás / törlés")
def cancel_invoice(modeladmin, request, queryset):
    queryset.update(status='CANCELLED')
    modeladmin.message_user(request, f"{queryset.count()} számlaigénylés törölve.")


@admin.action(description="🎯 Hirdetésmentes előfizetés aktiválása")
def activate_ad_free_subscription(modeladmin, request, queryset):
    """
    Aktiválja a hirdetésmentes előfizetést a kiválasztott számlák alapján.
    """
    activated = 0
    for invoice in queryset.filter(status='PENDING', subscription_plan__isnull=False):
        plan = invoice.subscription_plan
        user = invoice.target_user
        start = timezone.now()
        end = start + timezone.timedelta(days=plan.duration_days)

        UserSubscription.objects.update_or_create(
            user=user,
            defaults={'plan': plan, 'start_date': start, 'end_date': end}
        )

        invoice.status = 'SENT'
        invoice.save()
        activated += 1
    modeladmin.message_user(request, f"{activated} db hirdetésmentes előfizetés aktiválva.")


# ============================================================
# SZÁMLA ADMIN (TOPUPINVOICE)
# ============================================================

@admin.register(TopUpInvoice)
class TopUpInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'target_user', 'amount_ft',
        'invoice_type', 'status', 'request_date'
    )
    list_filter = ('invoice_type', 'status')
    search_fields = ('user__username', 'target_user__username')
    date_hierarchy = 'request_date'
    actions = [approve_analysis_invoice, activate_ad_free_subscription, cancel_invoice]

    def get_queryset(self, request):
        """Egy kis optimalizálás – kevesebb DB lekérés."""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'target_user', 'subscription_plan', 'related_analysis_package')
