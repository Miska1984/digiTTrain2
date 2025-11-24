from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

try:
    # ❗️ Fontos: Ez az importálás működjön!
    from diagnostics_jobs.models import DiagnosticJob 
    JOB_TYPE_CHOICES = DiagnosticJob.JobType.choices
    logger.info("DiagnosticJob.JobType importálva.")
except ImportError:
    # Vészmegoldás, ha az importálás még nem működik (később törölni kell)
    logger.warning("DiagnosticJob.JobType nem importálható, alapértelmezett beállítások használata.")
    JOB_TYPE_CHOICES = [
        ('GENERAL', 'Általános (Régi)'),
        ('WRESTLING', 'Birkózás Specifikus Elemzés'),
        ('MOVEMENT_ASSESSMENT', 'Általános mozgáselemzés'),
        ('SQUAT_ASSESSMENT', 'Guggolás Biomechanikai Elemzés'),
        ('POSTURE_ASSESSMENT','Testtartás Statikus/Dinamikus Elemzés'),
        ('ANTHROPOMETRY_CALIBRATION','Antropometria Kalibráció Két Képpel'),
        ('SHOULDER_CIRCUMDUCTION','Vállkörzés elemzés'),
        ('VERTICAL_JUMP','Helyből Magassági Ugrás Elemzés'),
        ('SINGLE_LEG_STANCE_LEFT','Egylábon Állás (Bal)'),
        ('SINGLE_LEG_STANCE_RIGHT','Egylábon Állás (Jobb)'),
    ]

# ----------------------------------------------------------------------
# 1. Előfizetési csomagok (Pl. Hirdetésmentes)
# ----------------------------------------------------------------------

class SubscriptionPlan(models.Model):
    """Definiálja a különböző előfizetési csomagokat (pl. Hirdetésmentes)."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Csomag neve")
    # 🌟 KRITIKUS: Ezt a mezőt állítja a superuser az Admin felületen
    price_ft = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Ár (Ft/ciklus)")
    duration_days = models.IntegerField(verbose_name="Időtartam (nap)")
    
    # A hirdetésmentes funkcióhoz szükséges flag (csak a hirdetésmentes csomagokra True)
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
        related_name='ad_free_subscription',
        verbose_name="Felhasználó"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.PROTECT, 
        verbose_name="Előfizetési Csomag"
    )
    start_date = models.DateTimeField(default=timezone.now, verbose_name="Kezdete")
    end_date = models.DateTimeField(verbose_name="Vége")
    
    class Meta:
        verbose_name = "Felhasználói Előfizetés"
        verbose_name_plural = "Felhasználói Előfizetések"

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} (Vége: {self.end_date.strftime('%Y-%m-%d')})"


# ----------------------------------------------------------------------
# MEGLÉVŐ: 3. Számla igénylés rögzítése
# ----------------------------------------------------------------------

class InvoiceRequest(models.Model):
    INVOICE_TYPES = (
        ('SUBSCRIPTION', 'Előfizetés (Hirdetésmentes)'),
        ('TOPUP', 'Egyenleg Feltöltés'), # 💥 ÚJ TÍPUS hozzáadva
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Függőben'),
        ('SENT', 'Elküldve'),
        ('CANCELLED', 'Törölve'),
        # Esetleg 'PAID' statusz bevezetése admin action után
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_invoices',
        verbose_name="Igénylő felhasználó"
    )
    amount_ft = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Feltöltendő összeg (Ft)")
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='credit_target_invoices',
        verbose_name="Jóváírás Személye"
    )
    invoice_type = models.CharField(
        max_length=50, 
        choices=INVOICE_TYPES, 
        default='TOPUP', 
        verbose_name="Számla típusa"
    )

    # Számlázási adatok
    billing_name = models.CharField(max_length=255, verbose_name="Számlázási Név")
    billing_address = models.TextField(verbose_name="Számlázási Cím")
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Adószám")

    request_date = models.DateTimeField(default=timezone.now, verbose_name="Igénylés dátuma")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="Státusz")

    class Meta:
        verbose_name = "Számla Igénylés"
        verbose_name_plural = "Számla Igénylések"

    def __str__(self):
        return f"Számla #{self.id} - {self.target_user.username} - {self.amount_ft} Ft"
    
# ----------------------------------------------------------------------
# ÚJ: 4. Feladattípusok Alapárának Rögzítése (JobPrice)
# ----------------------------------------------------------------------

class JobPrice(models.Model):
    """
    Rögzíti az elemzési csomagok árát (Ft-ban) és darabszámát.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Csomag neve"
    )

    analysis_count = models.IntegerField(
        default=1, 
        verbose_name="Elemzések száma a csomagban"
    )

    price_ft = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Ár (Ft)"
    )

    def __str__(self):
        return f"{self.name} ({self.analysis_count} db) - {self.price_ft} Ft"
        
    class Meta:
        ordering = ['price_ft'] 
        verbose_name = "Elemzési Csomag Ár"
        verbose_name_plural = "Elemzési Csomag Árak"

# ----------------------------------------------------------------------
# ÚJ: 5. Felhasználói / Sport Specifikus Kedvezmények (UserJobDiscount)
# ----------------------------------------------------------------------

class UserJobDiscount(models.Model):
    """
    Felhasználóra szabott kedvezmény egy adott feladattípusra (pl. birkózó -5%).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_discounts',
        verbose_name="Felhasználó",
        null=True, blank=True,
    )
    
    job_type = models.CharField(
        max_length=50, 
        choices=JOB_TYPE_CHOICES, 
        verbose_name="Feladat Típus, amire a kedvezmény vonatkozik"
    )
    
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="Kedvezmény (%)"
    )
    
    class Meta:
        verbose_name = "Feladat Kedvezmény"
        verbose_name_plural = "Feladat Kedvezmények"
        unique_together = ('user', 'job_type')

    def __str__(self):
        user_str = self.user.username if self.user else "Összes/Sportág"
        job_name = dict(JOB_TYPE_CHOICES).get(self.job_type, self.job_type)
        return f"{user_str} | {job_name}: -{self.discount_percentage}%"

# ----------------------------------------------------------------------
# ÚJ: 6. Felhasználói Pénztárca / Egyenleg (UserWallet)
# ----------------------------------------------------------------------

class UserWallet(models.Model):
    """
    Egy felhasználó aktuális Ft egyenlege. Ez a 'pénztárca'.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
        verbose_name="Felhasználó"
    )
    balance_ft = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="Aktuális egyenleg (Ft)"
    )

    class Meta:
        verbose_name = "Felhasználói Pénztárca"
        verbose_name_plural = "Felhasználói Pénztárcák"

    def __str__(self):
        return f"{self.user.username}: {self.balance_ft} Ft"

# ----------------------------------------------------------------------
# ÚJ: 7. Pénzügyi Tranzakciók (FinancialTransaction)
# ----------------------------------------------------------------------

class FinancialTransaction(models.Model):
    """
    Naplózza az összes Ft-mozgást: feltöltést és fogyasztást is.
    """
    TRANSACTION_TYPES = (
        ('TOPUP', 'Feltöltés számla alapján (Bevétel)'),
        ('DIAGNOSTICS_RUN', 'Diagnosztikai futtatás (Kiadás)'),
        ('ML_PREDICTION', 'ML Előrejelzés (Kiadás)'),
        ('ADMIN_ADJUSTMENT', 'Adminisztrátori korrekció'),
    )
    
    TRANSACTION_STATUS_CHOICES = (
        ('COMPLETED', 'Befejezett'),
        ('PENDING', 'Függőben (Foglalás)'),  # Foglalás státusz
        ('REFUNDED', 'Visszatérítve'),
        ('FAILED', 'Sikertelen'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name="Felhasználó"
    )
    amount_ft = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Összeg (Ft)")
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES, verbose_name="Típus")
    
    source_invoice = models.ForeignKey(
        'InvoiceRequest',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Forrás számla igénylés"
    )
    
    # ❗️ Fontos: Kapcsolat a DiagnosticJob-hoz (csak KIADÁS-nál releváns)
    # Figyelni kell az app név elérést: 'diagnostics_jobs.DiagnosticJob'
    related_job = models.ForeignKey(
        'diagnostics_jobs.DiagnosticJob', 
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Kapcsolódó Job"
    )

    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Időpont")
    is_consumption = models.BooleanField(default=False, verbose_name="Fogyasztás/Kiadás-e")
    transaction_status = models.CharField(
        max_length=10, 
        choices=TRANSACTION_STATUS_CHOICES, 
        default='COMPLETED', 
        verbose_name="Tranzakció Státusz"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Megjegyzés")

    class Meta:
        verbose_name = "Pénzügyi Tranzakció"
        verbose_name_plural = "Pénzügyi Tranzakciók"
        ordering = ['-timestamp']

    def __str__(self):
        sign = "-" if self.is_consumption else "+"
        return f"{self.user.username}: {sign}{self.amount_ft} Ft ({self.get_transaction_type_display()})"

# ----------------------------------------------------------------------
# 8. Top Up / Előfizetési Számlaigénylés (Hírdetéshez)
# ----------------------------------------------------------------------

class TopUpInvoice(models.Model):
    """Számla rögzítése a feltöltéshez VAGY előfizetés igényléséhez."""

    class InvoiceType(models.TextChoices):
        CREDIT_TOPUP = 'CREDIT_TOPUP', 'Credit Feltöltés (Ft összeg)'
        AD_FREE_SUBSCRIPTION = 'AD_FREE_SUBSCRIPTION', 'Hirdetésmentes Előfizetés'
        ANALYSIS_PACKAGE = 'ANALYSIS_PACKAGE', 'Elemzési Csomag' # ⬅️ ÚJ!

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Függőben'
        SENT = 'SENT', 'Elküldve'
        CANCELLED = 'CANCELLED', 'Törölve'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='topup_requested_invoices',
        verbose_name="Igénylő felhasználó"
    )
    
    amount_ft = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Fizetendő Összeg (Ft)"
    )
    
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='topup_credit_target_invoices',
        verbose_name="Jóváírás Személye"
    )

    invoice_type = models.CharField(
        max_length=30,
        choices=InvoiceType.choices,
        default=InvoiceType.ANALYSIS_PACKAGE,
        verbose_name="Számla típusa"
    )
    
    subscription_plan = models.ForeignKey(
        'SubscriptionPlan', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Előfizetési csomag"
    )
    
    # 💥 ÚJ MEZŐ: Kapcsolat az Elemzési Csomaghoz
    related_analysis_package = models.ForeignKey(
        # ✅ Helyes hivatkozás, mivel a JobPrice ugyanabban az appban (billing) van
        'JobPrice', 
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Kapcsolódó elemzési csomag"
    )

    # Számlázási adatok
    billing_name = models.CharField(max_length=255, verbose_name="Számlázási Név")
    billing_address = models.TextField(verbose_name="Számlázási Cím")
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Adószám")
    billing_email = models.EmailField(verbose_name="Számlázási E-mail cím", default="")
    
    request_date = models.DateTimeField(default=timezone.now, verbose_name="Igénylés dátuma")
    
    status = models.CharField(
        max_length=10, 
        choices=Status.choices,
        default=Status.PENDING, 
        verbose_name="Státusz"
    )
 
    class Meta:
        verbose_name = "Számlaigénylés (Feltöltés/Előfizetés)"
        verbose_name_plural = "Számlaigénylések (Feltöltés/Előfizetés)"
        ordering = ['-request_date']
        
    def __str__(self):
        if self.invoice_type == self.InvoiceType.AD_FREE_SUBSCRIPTION and self.subscription_plan:
            type_display = f"Előfizetés: {self.subscription_plan.name}"
        elif self.invoice_type == self.InvoiceType.ANALYSIS_PACKAGE and self.related_analysis_package:
            type_display = f"Csomag: {self.related_analysis_package.name} ({self.related_analysis_package.analysis_count} db)"
        else:
            type_display = self.get_invoice_type_display()
            
        return f"[{self.get_status_display()}] {type_display} - {self.amount_ft} Ft (Igénylő: {self.user.username})"

# ----------------------------------------------------------------------
# SIGNAL: Automatikus Pénztárca Létrehozása
# ----------------------------------------------------------------------

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Automatikusan létrehozza a UserWallet-et, amikor egy User létrejön."""
    if created:
        UserWallet.objects.create(user=instance)


# ----------------------------------------------------------------------
# 9. Elemzési Kredit Egyenleg (Darabszám alapú rendszer)
# ----------------------------------------------------------------------

class UserAnalysisBalance(models.Model):
    """Felhasználó elemzési egyenlege (darabszám alapú kredit rendszer)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='analysis_balance')
    analysis_count = models.IntegerField(default=0, verbose_name="Elérhető elemzések száma")

    class Meta:
        verbose_name = "Elemzési Egyenleg"
        verbose_name_plural = "Elemzési Egyenlegek"

    def __str__(self):
        return f"{self.user.username}: {self.analysis_count} elemzés"

    def add_credits(self, count: int, description="Vásárlás vagy jutalom", transaction_type="PURCHASE"):
        """Hozzáad elemzési krediteket az egyenleghez."""
        self.analysis_count += count
        self.save()
        AnalysisTransaction.objects.create(
            user=self.user,
            amount=count,
            transaction_type=transaction_type,
            description=description
        )

    def use_credits(self, amount: int, related_job=None, description="Elemzés indítása"):
        """
        Levon elemzési krediteket az egyenlegből.
        
        Args:
            amount: Levonandó kreditek száma
            related_job: Kapcsolódó DiagnosticJob (opcionális)
            description: Tranzakció leírása
            
        Returns:
            bool: True ha sikeres, False ha nincs elég kredit
        """
        if self.analysis_count < amount:
            return False
        
        self.analysis_count -= amount
        self.save()
        
        AnalysisTransaction.objects.create(
            user=self.user,
            amount=-amount,
            transaction_type="USAGE",
            related_job=related_job,
            description=description
        )
        
        return True

# ----------------------------------------------------------------------
# 10. Elemzési Tranzakciók (minden kreditmozgás naplózása)
# ----------------------------------------------------------------------

class AnalysisTransaction(models.Model):
    """Elemzési tranzakciók követése (vásárlás/felhasználás/jutalom)."""
    TRANSACTION_TYPES = (
        ('PURCHASE', 'Vásárlás'),
        ('USAGE', 'Felhasználás'),
        ('AD_REWARD', 'Hirdetésnézési jutalom'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analysis_transactions')
    amount = models.IntegerField(verbose_name="Darabszám változás (+/-)")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    related_job = models.ForeignKey('diagnostics_jobs.DiagnosticJob', null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Elemzési Tranzakció"
        verbose_name_plural = "Elemzési Tranzakciók"
        ordering = ['-timestamp']

    def __str__(self):
        sign = "+" if self.amount > 0 else "-"
        return f"{self.user.username}: {sign}{abs(self.amount)} ({self.get_transaction_type_display()})"


# ----------------------------------------------------------------------
# 11. Hirdetésnézési Sorozat (jutalom logika)
# ----------------------------------------------------------------------

class AdViewStreak(models.Model):
    """Hirdetésnézési sorozat követése, jutalommal minden 5. nap után."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ad_streak')
    current_streak = models.IntegerField(default=0, verbose_name="Jelenlegi sorozat (napok)")
    last_view_date = models.DateField(null=True, blank=True, verbose_name="Utolsó megtekintés dátuma")
    total_rewards_earned = models.IntegerField(default=0, verbose_name="Összes szerzett jutalom (db elemzés)")

    class Meta:
        verbose_name = "Hirdetésnézési Sorozat"
        verbose_name_plural = "Hirdetésnézési Sorozatok"

    def __str__(self):
        return f"{self.user.username}: {self.current_streak} nap streak"

    def register_view(self, today=None):
        """Hívható minden hirdetés megtekintés után."""
        from datetime import date, timedelta
        today = today or date.today()

        if self.last_view_date == today:
            return  # már ma megvolt a hirdetés

        if self.last_view_date == today - timedelta(days=1):
            self.current_streak += 1
        else:
            self.current_streak = 1

        self.last_view_date = today
        self.save()

        # 💥 5 nap után jutalom: 1 elemzés kredit
        if self.current_streak > 0 and self.current_streak % 5 == 0:
            balance, _ = UserAnalysisBalance.objects.get_or_create(user=self.user)
            balance.add_credits(1, description="5 napos hirdetésnézési sorozat jutalma", transaction_type="AD_REWARD")
            self.total_rewards_earned += 1
            self.save()