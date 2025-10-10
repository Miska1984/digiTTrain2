# sportág-specifikus metrikák (wrestling, running, stb.)
# diagnostics/models/sport_specific.py
from django.db import models
from .core_models import DiagnosticSession


class WrestlingSpecificMetric(models.Model):
    """
    Birkózó-specifikus metrikák, a videóelemzésből származtatva.
    """
    session = models.OneToOneField(
        DiagnosticSession,
        on_delete=models.CASCADE,
        related_name="wrestling_metrics",
        verbose_name="Kapcsolódó diagnosztikai futás"
    )

    technique_execution_score = models.FloatField(blank=True, null=True, verbose_name="Technikai pontosság (%)")
    balance_stability = models.FloatField(blank=True, null=True, verbose_name="Egyensúly stabilitás (%)")
    explosiveness_index = models.FloatField(blank=True, null=True, verbose_name="Robbanékonysági index")
    joint_symmetry_score = models.FloatField(blank=True, null=True, verbose_name="Ízületi szimmetria (%)")
    core_engagement_level = models.FloatField(blank=True, null=True, verbose_name="Törzs aktivitás (%)")
    endurance_estimate = models.FloatField(blank=True, null=True, verbose_name="Állóképesség becslés (%)")
    injury_risk_score = models.FloatField(blank=True, null=True, verbose_name="Sérüléskockázati index")
    movement_efficiency = models.FloatField(blank=True, null=True, verbose_name="Mozgáshatékonyság (%)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Birkózó diagnosztikai metrika"
        verbose_name_plural = "Birkózó diagnosztikai metrikák"

    def __str__(self):
        return f"Wrestling metrics for session {self.session.id}"
