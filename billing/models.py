# billing/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# ============================================================
# 1. SZOLGÁLTATÁSI CSOMAGOK (Az "Étlap")
# ============================================================

class ServicePlan(models.Model):
    PLAN_TYPES = [
        ('AD_FREE', 'Hirdetésmentesség (Időalapú)'),
        ('ML_ACCESS', 'ML Funkciók (Időalapú)'),
        ('ANALYSIS', 'Elemzési Csomag (Darabszám alapú)'),
    ]

    name = models.CharField(max_length=100, verbose_name="Csomag neve")
    description = models.TextField(blank=True, null=True, verbose_name="Leírás")
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, verbose_name="Típus")
    
    # Árazás
    price_ft = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="Ár (Ft)"
    )
    price_in_credits = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="Ár (Kreditben)"
    )
    
    # Érték
    duration_days = models.PositiveIntegerField(null=True, blank=True, verbose_name="Időtartam (nap)")
    analysis_count = models.PositiveIntegerField(default=0, verbose_name="Elemzések száma (db)")
    
    is_active = models.BooleanField(default=True, verbose_name="Aktív?")

    class Meta:
        verbose_name = "Szolgáltatási Csomag"
        verbose_name_plural = "Szolgáltatási Csomagok"

    def __str__(self):
        return f"{self.name} ({self.price_ft} Ft / {self.price_in_credits} Cr)"


# ============================================================
# 2. FELHASZNÁLÓI EGYENLEGEK
# ============================================================

class UserCreditBalance(models.Model):
    """Hirdetésnézéssel gyűjtött kreditek 'pénztárcája'."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_balance")
    credits = models.PositiveIntegerField(default=0, verbose_name="Kreditek")

    def __str__(self):
        return f"{self.user.email}: {self.credits} Cr"


class UserAnalysisBalance(models.Model):
    """Hány darab elemzést futtathat a user."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="analysis_balance")
    count = models.PositiveIntegerField(default=0, verbose_name="Elemzési keret (db)")

    def __str__(self):
        return f"{self.user.email}: {self.count} db"


class UserSubscription(models.Model):
    """Aktív időalapú jogosultságok (Hirdetésmentesség vagy ML)."""
    SUB_TYPES = [('ML_ACCESS', 'ML'), ('AD_FREE', 'Hirdetésmentesség')]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    
    # Ezt a sort add vissza (kapcsolat a ServicePlan-hez):
    plan = models.ForeignKey('ServicePlan', on_delete=models.CASCADE, null=True, blank=True)
    
    sub_type = models.CharField(max_length=20, choices=SUB_TYPES)
    expiry_date = models.DateTimeField()
    
    # Ez a korábbi hiba megoldása:
    active = models.BooleanField(default=True, verbose_name="Aktív")

    def is_active(self):
        return self.active and self.expiry_date > timezone.now()

# ============================================================
# 3. VÁSÁRLÁSI FOLYAMAT (Direct Path - Pénzes út)
# ============================================================

class TopUpInvoice(models.Model):
    """
    Ez tárolja az igényeket. 
    A user igényel -> státusz: PENDING -> Te kapsz mailt -> Számlázol -> 
    Ha megjött a pénz -> Adminban APPROVED -> Automata aktiválás.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Igényelve (Várakozik)'),
        ('INVOICED', 'Számla kiküldve'),
        ('APPROVED', 'Fizetve / Jóváhagyva'),
        ('REJECTED', 'Elutasítva'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices_paid')
    plan = models.ForeignKey(ServicePlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    amount_ft = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Összeg (Ft)")

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='invoices_received',
        null=True, blank=True
    )

    # Számlázási adatok (amiket a user megad az igényléskor)
    billing_name = models.CharField(max_length=255)
    billing_email = models.EmailField()
    billing_address = models.TextField()
    tax_number = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Igény #{self.id} - {self.user.email} ({self.plan.name})"

class FinancialTransaction(models.Model):
    """Minden pontmozgás és vásárlás naplózása a felhasználó számára."""
    TRANSACTION_TYPES = [
        ('EARN', 'Szerzés (Hirdetés/Bónusz)'),
        ('SPEND', 'Levonás (Vásárlás/Beváltás)'),
        ('ADMIN', 'Adminisztrátori módosítás'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="financial_history")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.IntegerField(help_text="Pozitív ha kap, negatív ha költ")
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pénzügyi Tranzakció"
        verbose_name_plural = "Pénzügyi Tranzakciók"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.email} | {self.amount} | {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
