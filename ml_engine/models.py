import pandas as pd
from django.db import models
from django.conf import settings
from django.utils import timezone
from users.models import User

class UserFeatureSnapshot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    features = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)
    snapshot_date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ["-generated_at"]
        unique_together = ('user', 'snapshot_date')

    @staticmethod
    def to_training_dataframe():
        data = list(UserFeatureSnapshot.objects.all().values_list("features", flat=True))
        return pd.DataFrame(data) if data else pd.DataFrame()

class UserPredictionResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    predicted_at = models.DateTimeField(auto_now_add=True)
    form_score = models.FloatField()
    source_date = models.DateTimeField(null=True, blank=True)
    coach_advice = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-predicted_at"]

    def __str__(self):
        return f"{self.user.username} - {self.form_score:.2f}"

class DittaMissedQuery(models.Model):
    """
    Ha Ditta nem tud válaszolni, itt tároljuk a kontextust a későbbi fejlesztéshez.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="missed_queries")
    query = models.TextField()
    context_app = models.CharField(max_length=100) # Pl. 'biometric', 'diagnostic'
    context_snapshot = models.JSONField(null=True, blank=True) # Az alany neve, elérhető adatok listája
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ditta Hiányzó Ismeret"
        verbose_name_plural = "Ditta Hiányzó Ismeretek"

    def __str__(self):
        return f"Missed: {self.query[:30]}..."