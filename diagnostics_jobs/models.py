from django.db import models
from django.conf import settings
from django.utils import timezone
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback


class DiagnosticJob(models.Model):
    class JobStatus(models.TextChoices):
        PENDING = 'PENDING', 'Feldolgozásra vár'
        QUEUED = 'QUEUED', 'Ütemezve'
        PROCESSING = 'PROCESSING', 'Feldolgozás alatt'
        COMPLETED = 'COMPLETED', 'Befejezve'
        FAILED = 'FAILED', 'Hiba történt'

    class JobType(models.TextChoices):
        GENERAL = 'GENERAL', ('Általános (Régi)')
        MOVEMENT_ASSESSMENT = 'MOVEMENT_ASSESSMENT', ('Általános mozgáselemzés (MediaPipe)')
        WRESTLING = 'WRESTLING', ('Birkózás Specifikus Elemzés')
        SQUAT_ASSESSMENT = 'SQUAT_ASSESSMENT', ('Guggolás Biomechanikai Elemzés')
        POSTURE_ASSESSMENT = 'POSTURE_ASSESSMENT', ('Testtartás Statikus/Dinamikus Elemzés')
        ANTHROPOMETRY_CALIBRATION = 'ANTHROPOMETRY_CALIBRATION', ('Antropometria Kalibráció Két Képpel')
        SHOULDER_CIRCUMDUCTION = "SHOULDER_CIRCUMDUCTION", ("Vállkörzés elemzés")
        VERTICAL_JUMP = "VERTICAL_JUMP", ("Helyből Magassági Ugrás Elemzés")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sport_type = models.CharField(max_length=50, verbose_name="Sportág")
    job_type = models.CharField(max_length=50, choices=JobType.choices, default=JobType.MOVEMENT_ASSESSMENT)
    video_url = models.URLField(verbose_name="Videó elérési út (Cloud Storage)", null=True, blank=True) # Videó nem kell a kalibrációhoz
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING)
    
    # ----------------------------------------------------------------------
    # 🆕 ÚJ MEZŐK A KÉT KÉP ALAPJÁN TÖRTÉNŐ ANTROPOMETRIAI KALIBRÁCIÓHOZ
    # ----------------------------------------------------------------------
    
    # 1. A felhasználó által megadott valós magasság (Gold Standard)
    user_stated_height_m = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name="Felhasználó által megadott valós magasság (m)",
        help_text="A kalibráció alapja, méterben (pl. 1.77)."
    )

    user_stated_thigh_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Combhossz (cm)",
        help_text="Felhasználó által megadott combhossz a kalibrációhoz (cm)."
    )

    user_stated_shin_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Lábszárhossz (cm)",
        help_text="Felhasználó által megadott lábszárhossz a kalibrációhoz (cm)."
    )

    # 2. Szemből készült fotó URL-je
    anthropometry_photo_url_front = models.URLField(
        max_length=2048, 
        null=True, 
        blank=True, 
        verbose_name="Antropometria Kalibrációs Fotó URL (Szemből)",
        help_text="A statikus szemből készült fotó GCS elérési útja."
    )
    
    # 3. Oldalról készült fotó URL-je
    anthropometry_photo_url_side = models.URLField(
        max_length=2048, 
        null=True, 
        blank=True, 
        verbose_name="Antropometria Kalibrációs Fotó URL (Oldalról)",
        help_text="A statikus oldalról készült fotó GCS elérési útja."
    )
    
    # 4. Kalibrációs tényező (Ezt számolja ki a service)
    calibration_factor = models.DecimalField(
        max_digits=10, 
        decimal_places=5, 
        null=True, 
        blank=True, 
        verbose_name="MediaPipe Kalibrációs Faktor",
        help_text="A videók 3D-s koordinátáinak skálázásához használt arány (Valós Magasság / Becsült Magasság)."
    )

    leg_calibration_factor = models.DecimalField(
    max_digits=10,
    decimal_places=5,
    null=True,
    blank=True,
    verbose_name="Láb-specifikus kalibrációs faktor",
    help_text="A comb és lábszár hossz alapján számolt korrekciós tényező."
    )

    # ----------------------------------------------------------------------
    
    priority = models.PositiveIntegerField(default=1, help_text="Magasabb érték = előbbi feldolgozás")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True, help_text="Diagnosztikai eredmények (JSON)")

    weight_snapshot = models.ForeignKey(
        WeightData, null=True, blank=True, on_delete=models.SET_NULL, related_name="diagnostic_jobs"
    )
    hrv_snapshot = models.ForeignKey(
        HRVandSleepData, null=True, blank=True, on_delete=models.SET_NULL, related_name="diagnostic_jobs"
    )
    workout_feedback_snapshot = models.ForeignKey(
        WorkoutFeedback, null=True, blank=True, on_delete=models.SET_NULL, related_name="diagnostic_jobs"
    )

    error_message = models.TextField(null=True, blank=True)

    # 🧾 JAVÍTOTT MEZŐ — nagyobb méret (akár 2048 karakter)
    pdf_path = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        verbose_name="Eredmény PDF URL",
        help_text="A generált riport Cloud Storage URL-je"
    )

    class Meta:
        verbose_name = "Diagnosztikai feladat"
        verbose_name_plural = "Diagnosztikai feladatok"
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} - {self.user.username} ({self.get_status_display()})"

    def mark_as_processing(self):
        """A feladat státuszát feldolgozás alattira állítja."""
        self.status = self.JobStatus.PROCESSING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_as_completed(self, result_data: dict, pdf_path: str = None):
        """A feladat sikeres befejezése."""
        self.status = self.JobStatus.COMPLETED
        self.result = result_data
        self.completed_at = timezone.now()

        if pdf_path:
            self.pdf_path = pdf_path

        self.save(update_fields=['status', 'result', 'completed_at', 'pdf_path'])
    
    def mark_as_queued(self):
        """Beállítja a job státuszát QUEUED-ra."""
        self.status = self.JobStatus.QUEUED
        self.save()

    def mark_as_failed(self, error: str):
        """A feladat hibás állapotba állítása."""
        self.status = self.JobStatus.FAILED
        self.error_message = error
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])

class UserAnthropometryProfile(models.Model):
    """
    A felhasználó statikus testméreteit és kalibrációs adatait tárolja.
    Ezek az adatok szolgálnak a MediaPipe által becsült 3D testpontok
    skálázásához és a biomechanikai erőkarok számításához.
    """

    # 🔗 Egy felhasználónak pontosan egy antropometriai profilja van
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Felhasználó",
        primary_key=True,
    )

    # 📏 Általános antropometriai adatok
    height_cm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Testmagasság (cm)"
    )
    weight_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Testsúly (kg)"
    )
    date_of_birth = models.DateField(
        null=True, blank=True, verbose_name="Születési dátum"
    )

    # ⚙️ Kalibrációs és metaadatok
    reference_job = models.ForeignKey(
        'DiagnosticJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Utolsó kalibrációs feladat",
        help_text="Annak a diagnosztikai jobnak az azonosítója, amellyel ez a profil készült."
    )

    calibration_factor = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        verbose_name="Kalibrációs faktor",
        help_text="Valós magasság / MediaPipe becsült magasság arány, a skálázáshoz."
    )

    calibration_factor = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        verbose_name="Kalibrációs faktor",
        help_text="Valós magasság / MediaPipe becsült magasság arány, a skálázáshoz."
    )

    leg_calibration_factor = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        verbose_name="Láb-specifikus kalibrációs faktor",
        help_text="Combhossz + lábszárhossz alapján számított korrekciós tényező."
    )

    updated_at = models.DateTimeField(auto_now=True)

    # 🖼 Annotált kép (kalibrációs vizualizáció)
    annotated_image_url = models.URLField(
        max_length=2048,
        null=True,
        blank=True,
        verbose_name="Annotált antropometriai kép URL",
        help_text="A MediaPipe által generált kalibrált, feliratozott kép URL-je."
    )

    # 📐 Törzs és szélességi méretek
    trunk_height_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Törzshossz (cm)"
    )
    shoulder_width_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Vállszélesség (cm)"
    )
    pelvis_width_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Csípőszélesség (cm)"
    )

    # 🦾 Felső végtagok (bal/jobb)
    left_upper_arm_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Bal felkar hossza (cm)"
    )
    right_upper_arm_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Jobb felkar hossza (cm)"
    )
    left_forearm_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Bal alkar hossza (cm)"
    )
    right_forearm_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Jobb alkar hossza (cm)"
    )

    # 🦵 Alsó végtagok (bal/jobb)
    left_thigh_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Bal comb hossza (cm)"
    )
    right_thigh_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Jobb comb hossza (cm)"
    )
    left_shin_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Bal sípcsont hossza (cm)"
    )
    right_shin_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Jobb sípcsont hossza (cm)"
    )

    # 🧍‍♂️ Manuálisan megadott korrekciós értékek
    manual_thigh_cm = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Combhossz (kézi megadás, cm)",
        help_text="Ha megadod, a rendszer ezt használja a MediaPipe becslés helyett."
    )

    manual_shin_cm = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Lábszárhossz (kézi megadás, cm)",
        help_text="Ha megadod, a rendszer ezt használja a MediaPipe becslés helyett."
    )

    class Meta:
        verbose_name = "Antropometriai profil"
        verbose_name_plural = "Antropometriai profilok"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Antropometria: {self.user.username} – {self.height_cm or '?'} cm"

    @property
    def is_calibrated(self) -> bool:
        """Gyors ellenőrzés, hogy történt-e kalibráció."""
        return self.calibration_factor is not None and self.calibration_factor > 0 
    
    @property
    def has_leg_calibration(self) -> bool:
        return self.leg_calibration_factor is not None and self.leg_calibration_factor > 0