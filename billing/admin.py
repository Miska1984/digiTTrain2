# billing/admin.py
from django.contrib import admin, messages
from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render
from .models import FinancialTransaction, ServicePlan, UserCreditBalance, UserAnalysisBalance, UserSubscription, TopUpInvoice
from .utils import activate_service

# 1. FORM AZ EGYEDI JÓVÁÍRÁSHOZ
class CreditActionForm(forms.Form):
    amount = forms.IntegerField(label="Kredit összege", min_value=1, initial=100)
    comment = forms.CharField(label="Megjegyzés a naplóba", max_length=255, initial="Adminisztrátori jóváírás")

# 2. SZOLGÁLTATÁSI CSOMAGOK
@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'display_price_ft', 'display_price_credits', 'is_active')
    list_filter = ('plan_type', 'is_active')
    search_fields = ('name',)

    def display_price_ft(self, obj):
        return f"{obj.price_ft} Ft" if obj.price_ft else "Nem vehető pénzért"
    display_price_ft.short_description = "Ár (Ft)"

    def display_price_credits(self, obj):
        return f"{obj.price_in_credits} Cr" if obj.price_in_credits else "Nem váltható be"
    display_price_credits.short_description = "Ár (Kredit)"

# 3. VÁSÁRLÁSI IGÉNYEK
@admin.register(TopUpInvoice)
class TopUpInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'status', 'amount_ft', 'created_at') 
    list_filter = ('status', 'plan')
    search_fields = ('user__email', 'billing_name')
    actions = ['approve_invoice']

    @admin.action(description="Kiválasztott igények JÓVÁHAGYÁSA és aktiválása")
    def approve_invoice(self, request, queryset):
        for invoice in queryset.filter(status__in=['PENDING', 'INVOICED']):
            # Meghatározzuk, ki a célpont (ha másnak vette, akkor a target_user)
            target = invoice.target_user if invoice.target_user else invoice.user
            
            # --- EZ A FONTOS RÉSZ ---
            # 1. Szolgáltatás aktiválása az UTILS-on keresztül
            # Átadjuk a payer=invoice.user-t, hogy az utils.py tudja, ki fizetett!
            activate_service(target, invoice.plan, payer=invoice.user)
            
            # 2. Szép nevek lekérése a naplózáshoz (ez már jó volt nálad)
            from .utils import get_user_display_info
            payer_info = get_user_display_info(invoice.user)
            target_info = get_user_display_info(target)

            # 3. Tranzakció naplózása a FIZETŐNÉL (aki az utalást küldte)
            # Itt csak akkor hozunk létre manuálisan bejegyzést, ha az activate_service 
            # nem tette meg (banki utalásnál érdemes itt hagyni a visszaigazolást)
            FinancialTransaction.objects.create(
                user=invoice.user,
                transaction_type='ADMIN',
                amount=0, 
                description=f"Vásárlás visszaigazolva: {invoice.plan.name} -> {target_info}"
            )
            
            # 4. Tranzakció a SPORTOLÓNÁL (aki kapta - ha nem önmaga)
            if invoice.user != target:
                FinancialTransaction.objects.create(
                    user=target,
                    transaction_type='EARN',
                    amount=0,
                    description=f"Csomag érkezett: {invoice.plan.name} (Küldte: {payer_info})"
                )

            # 5. Státusz frissítése
            invoice.status = 'APPROVED'
            invoice.save()
            
        self.message_user(request, "A kiválasztott csomagok aktiválva lettek és a naplózás megtörtént.")

# 4. KREDIT EGYENLEGEK (Itt vontuk össze a funkciókat)
@admin.register(UserCreditBalance)
class UserCreditBalanceAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'credits', 'user_email')
    search_fields = ('user__email', 'user__profile__first_name', 'user__profile__last_name')
    actions = ['add_custom_credits']

    def get_full_name(self, obj):
        if hasattr(obj.user, 'profile'):
            return f"{obj.user.profile.last_name} {obj.user.profile.first_name}"
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Felhasználó'

    def user_email(self, obj):
        return obj.user.email

    @admin.action(description="Egyedi kredit jóváírás (beírással)")
    def add_custom_credits(self, request, queryset):
        if 'apply' in request.POST:
            form = CreditActionForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                comment = form.cleaned_data['comment']
                for wallet in queryset:
                    wallet.credits += amount
                    wallet.save()
                    FinancialTransaction.objects.create(
                        user=wallet.user,
                        transaction_type='ADMIN',
                        amount=amount,
                        description=comment
                    )
                self.message_user(request, f"Sikeresen hozzáadva {amount} kredit.", messages.SUCCESS)
                return HttpResponseRedirect(request.get_full_path())

        form = CreditActionForm()
        return render(request, 'admin/billing/add_credit_intermediate.html', {
            'items': queryset,
            'form': form,
            'action': 'add_custom_credits',
            'title': 'Egyedi kredit hozzáadása'
        })

# 5. EGYÉB ADMIN REGISZTRÁCIÓK
@admin.register(UserAnalysisBalance)
class UserAnalysisBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'count')
    search_fields = ('user__email',)

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'sub_type', 'expiry_date')
    list_filter = ('sub_type',)
    search_fields = ('user__email',)

@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'transaction_type', 'amount', 'description')
    list_filter = ('transaction_type', 'timestamp')