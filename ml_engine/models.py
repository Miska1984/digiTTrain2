# ml_engine/models.py

import pandas as pd
from django.db import models
from django.conf import settings

class UserFeatureSnapshot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    features = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.user.username} - {self.generated_at.strftime('%Y-%m-%d %H:%M')}"

    @staticmethod
    def to_training_dataframe():
        """JSON feature snapshotok pandas DataFrame-be alakítása"""
        data = list(UserFeatureSnapshot.objects.all().values_list("features", flat=True))
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.dropna(axis=1, how="all")  # üres oszlopok eldobása
        return df

class PredictedForm(models.Model):
    """
    Az ML modell által előrejelzett form score értékek tárolása.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    predicted_at = models.DateTimeField(auto_now_add=True)
    form_score = models.FloatField()

    class Meta:
        ordering = ["-predicted_at"]

    def __str__(self):
        return f"{self.user.username} - {self.form_score:.2f} ({self.predicted_at:%Y-%m-%d %H:%M})"


