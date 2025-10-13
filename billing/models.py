from django.db import models
from django.conf import settings
from django.utils import timezone

# ----------------------------------------------------------------------
# 1. Előfizetési csomagok (Pl. Hirdetésmentes)
# ----------------------------------------------------------------------

class SubscriptionPlan(models.Model):
    """Definiálja a különböző előfizetési csomagokat (pl. Hirdetésmentes)."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Csomag neve")
    price_ft = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Ár (Ft/ciklus)")
    duration_days = models.IntegerField(verbose_name="Időtartam (nap)")
    
    # A hirdetésmentes funkcióhoz szükséges flag
    is_ad_free = models.BooleanField(default=False, verbose_name="Hirdetésmentes funkció")

    class Meta:
        verbose_name = "Előfizetési Csomag"
        verbose_name_plural = "Előfizetési Csomagok"

    def __str__(self):
        return f"{self.name} ({self.price_ft} Ft/{self.duration_days} nap)"

# ----------------------------------------------------------------------
# 2. Felhasználói előfizetés követése
# ----------------------------------------------------------------------

class UserSubscription(models.Model):
    """Egy felhasználó aktív előfizetésének követése."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name="Felhasználó"
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, verbose_name="Csomag")
    start_date = models.DateTimeField(default=timezone.now, verbose_name="Kezdés dátuma")
    end_date = models.DateTimeField(verbose_name="Lejárat dátuma")
    is_active = models.BooleanField(default=True, verbose_name="Aktív")

    class Meta:
        verbose_name = "Felhasználói Előfizetés"
        verbose_name_plural = "Felhasználói Előfizetések"

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'Nincs Csomag'} (Lejár: {self.end_date.date()})"


# ----------------------------------------------------------------------
# 3. Felhasználói Credit Egyenleg (az algoritmusok futtatásához)
# ----------------------------------------------------------------------

class UserCreditBalance(models.Model):
    """A felhasználó algoritmus futtatáshoz használható Credit egyenlege."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_balance',
        verbose_name="Felhasználó"
    )
    # Credit használata, mivel rugalmasabb az ár/érték arány változtatásánál, mint a közvetlen pénz
    balance_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Credit Egyenleg"
    )

    class Meta:
        verbose_name = "Credit Egyenleg"
        verbose_name_plural = "Credit Egyenlegek"

    def __str__(self):
        return f"{self.user.username} - {self.balance_amount} Credit"


# ----------------------------------------------------------------------
# 4. Algoritmusok árazása
# ----------------------------------------------------------------------

class AlgorithmPricing(models.Model):
    """Minden fizetős algoritmus Credit költségének definiálása."""
    algorithm_name = models.CharField(max_length=255, unique=True, verbose_name="Algoritmus neve")
    # A felhasználó által említett árakat Creditnek vesszük (2500 Credit, 2250 Credit)
    cost_per_run = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        verbose_name="Költség (Credit)"
    )
    description = models.TextField(blank=True, verbose_name="Leírás")

    class Meta:
        verbose_name = "Algoritmus Ár"
        verbose_name_plural = "Algoritmus Árak"

    def __str__(self):
        return f"{self.algorithm_name}: {self.cost_per_run} Credit/elemzés"


# ----------------------------------------------------------------------
# 5. Tranzakciós Előzmények
# ----------------------------------------------------------------------

class TransactionHistory(models.Model):
    """Naplózza az összes Credit mozgást (feltöltés, algoritmus futtatás, hirdetésnézés)."""
    
    TRANSACTION_TYPES = (
        ('TOP_UP', 'Credit Feltöltés (Ft-ból)'),
        ('ALGO_RUN', 'Algoritmus Futtatás'),
        ('AD_EARN', 'Hirdetésnézésből szerzett Credit'),
        ('SUB_PAY', 'Előfizetés fizetés'),
        ('TRANSFER', 'Egyenleg átutalás'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='transactions_affected',
        verbose_name="Érintett felhasználó (Credit tulajdonosa)"
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="Típus")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Összeg (Credit)")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Időpont")
    
    # Ha a tranzakció valamilyen másik entitáshoz/személyhez kapcsolódik (pl. kifizetés)
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='transactions_related',
        verbose_name="Kapcsolódó felhasználó (pl. fizető/cél)"
    )
    description = models.TextField(blank=True, verbose_name="Leírás")

    class Meta:
        verbose_name = "Tranzakció"
        verbose_name_plural = "Tranzakciók"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.get_transaction_type_display()}] {self.user.username}: {self.amount} Credit ({self.timestamp.strftime('%Y.%m.%d %H:%M')})"


# ----------------------------------------------------------------------
# 6. Számlaigénylés
# ----------------------------------------------------------------------

class InvoiceRequest(models.Model):
    """Felhasználó által kért számla rögzítése a feltöltéshez."""

    STATUS_CHOICES = (
        ('PENDING', 'Függőben'),
        ('SENT', 'Elküldve'),
        ('CANCELLED', 'Törölve'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_invoices',
        verbose_name="Igénylő felhasználó"
    )
    amount_ft = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Feltöltendő összeg (Ft)")
    
    # A credit feltöltés célja: lehet az igénylő maga, vagy egy sportoló
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='credit_target_invoices',
        verbose_name="Cél felhasználó (aki kapja a Creditet)"
    )

    # Számlázási adatok
    billing_name = models.CharField(max_length=255, verbose_name="Számlázási Név")
    billing_address = models.TextField(verbose_name="Számlázási Cím")
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Adószám")

    request_date = models.DateTimeField(default=timezone.now, verbose_name="Igénylés dátuma")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="Státusz")

    class Meta:
        verbose_name = "Számlaigénylés"
        verbose_name_plural = "Számlaigénylések"
        ordering = ['-request_date']

    def __str__(self):
        return f"Számlaigénylés: {self.amount_ft} Ft - Cél: {self.target_user.username} (Státusz: {self.status})"