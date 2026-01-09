import pandas as pd
from django.db import models
from django.conf import settings
from django.utils import timezone

class UserFeatureSnapshot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    features = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)
    # Új mező az egyediség biztosításához (opcionális, de stabilabb így)
    snapshot_date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ["-generated_at"]
        # Ezzel biztosítjuk, hogy egy usernek egy napra csak egy snapshotja legyen:
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