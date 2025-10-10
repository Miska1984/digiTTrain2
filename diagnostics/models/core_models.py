# DiagnosticSession, DiagnosticMetric
# diagnostics/models/core_models.py
from django.db import models
from django.conf import settings

class DiagnosticSession(models.Model):
    """
    Egy diagnosztikai elemzés futása (videó- vagy adat-alapú).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="diagnostic_sessions",
        verbose_name="Sportoló"
    )

    sport = models.CharField(
        max_length=50,
        verbose_name="Sportág",
        help_text="pl. wrestling, running, swimming"
    )

    source_type = models.CharField(
        max_length=30,
        choices=[
            ("video", "Videó elemzés"),
            ("biometric", "Biometrikus elemzés"),
            ("combined", "Kombinált")
        ],
        default="combined",
        verbose_name="Forrástípus"
    )

    video_file_url = models.URLField(
        blank=True, null=True,
        verbose_name="Videó fájl URL-je (Cloud Storage)"
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Folyamatban"),
            ("processing", "Feldolgozás alatt"),
            ("done", "Kész"),
            ("error", "Hiba")
        ],
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.sport} ({self.created_at.strftime('%Y-%m-%d')})"

    class Meta:
        verbose_name = "Diagnosztikai futás"
        verbose_name_plural = "Diagnosztikai futások"
        ordering = ['-created_at']


class DiagnosticMetric(models.Model):
    """
    Egy adott diagnosztikai metrika eredménye.
    """
    session = models.ForeignKey(
        DiagnosticSession,
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name="Kapcsolódó diagnosztikai futás"
    )

    category = models.CharField(
        max_length=50,
        verbose_name="Metrika kategória",
        help_text="pl. general, wrestling"
    )

    name = models.CharField(
        max_length=100,
        verbose_name="Metrika neve",
        help_text="pl. HydrationEfficiency vagy TechniqueExecutionScore"
    )

    value = models.FloatField(verbose_name="Érték")
    unit = models.CharField(max_length=20, blank=True, null=True, verbose_name="Mértékegység")
    score = models.FloatField(blank=True, null=True, verbose_name="Pontszám (0-100 skálán)")
    interpretation = models.TextField(blank=True, null=True, verbose_name="Szöveges értelmezés")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Diagnosztikai metrika"
        verbose_name_plural = "Diagnosztikai metrikák"
        indexes = [
            models.Index(fields=["category", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.value}{self.unit or ''})"
