from django.db import models
from django.conf import settings
# Fontos: A DiagnosticJob-ot most a diagnostics_jobs appból importáljuk!
from diagnostics_jobs.models import DiagnosticJob 


class PostureAssessmentResult(models.Model):
    """ Statikus/Dinamikus testtartás elemzés strukturált eredményei. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # OneToOne kapcsolat a jobhoz - a job eredménye csak egyszer tárolható
    job = models.OneToOneField(DiagnosticJob, on_delete=models.CASCADE, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Testtartás metrikák
    posture_score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Összpontszám", null=True)
    avg_shoulder_tilt = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Átl. Váll dőlés (°)", null=True)
    avg_hip_tilt = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Átl. Csípő dőlés (°)", null=True)
    
    # A teljes JSON eredmény másolata, ha valami egyedi adatra van szükség
    raw_json_metrics = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Testtartás Eredmény"

class SquatAssessmentResult(models.Model):
    """ Guggolás biomechanikai elemzés strukturált eredményei. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    job = models.OneToOneField(DiagnosticJob, on_delete=models.CASCADE, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Guggolás metrikák
    overall_squat_score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Összpontszám", null=True)
    min_knee_angle = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Minimális térdszög (°)", null=True)
    max_trunk_lean = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Maximális törzsdőlés (°)", null=True)

    raw_json_metrics = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Guggolás Eredmény"

class ShoulderCircumductionResult(models.Model):
    """
    Eredménytábla a Vállkörzés Biomechanikai Elemzéshez.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    job = models.OneToOneField(DiagnosticJob, on_delete=models.CASCADE, related_name='shoulder_circumduction_result')
    created_at = models.DateTimeField()
    
    # 📌 Fő metrikák (dedikált mezők)
    overall_score = models.DecimalField(max_digits=4, decimal_places=1, verbose_name="Összpontszám (%)")
    max_rom_left = models.DecimalField(max_digits=5, decimal_places=1, verbose_name="Max. Eleváció Bal (°)")
    max_rom_right = models.DecimalField(max_digits=5, decimal_places=1, verbose_name="Max. Eleváció Jobb (°)")
    
    # 💾 Minden további elemzési adat (JSONField)
    raw_json_metrics = models.JSONField(verbose_name="Minden metrika és visszajelzés")

    class Meta:
        verbose_name = "Vállkörzés Eredmény"
        verbose_name_plural = "Vállkörzés Eredmények"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Vállkörzés Job #{self.job.id} - {self.user.username}"

class VerticalJumpAssessmentResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    job = models.OneToOneField(DiagnosticJob, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    
    # A Service által bementett fő metrikák
    overall_jump_score = models.DecimalField(max_digits=5, decimal_places=1, verbose_name="Összesített Pontszám")
    jump_height_cm = models.DecimalField(max_digits=5, decimal_places=1, verbose_name="Ugrásmagasság (cm)")
    max_valgus_angle = models.DecimalField(max_digits=5, decimal_places=1, verbose_name="Max. Valgus Szög (°)")
    
    # A teljes JSON output (tartalmazza a többi metrikát)
    raw_json_metrics = models.JSONField(verbose_name="Nyers Elemzési Metrikák")

    class Meta:
        verbose_name = "Helyből Magassági Ugrás Eredmény"
        verbose_name_plural = "Helyből Magassági Ugrás Eredmények"
        ordering = ['-created_at']

        