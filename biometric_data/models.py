# biometric_data/models.py
from django.db import models
from django.conf import settings

class WeightData(models.Model):
    # A te általad megadott kód ide
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    morning_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Reggeli súly (kg)")
    pre_workout_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Edzés előtti súly (kg)", blank=True, null=True)
    post_workout_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Edzés utáni súly (kg)", blank=True, null=True)
    fluid_intake = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Edzés közbeni folyadékfogyasztás (l)", blank=True, null=True)
    body_fat_percentage = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name="Testzsír (%)")
    muscle_percentage = models.DecimalField( max_digits=4, decimal_places=1, null=True, blank=True, verbose_name="Izom (%)")
    bone_mass_kg = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name="Csonttömeg (kg)")
    workout_date = models.DateField(auto_now_add=True, verbose_name="Edzés napja")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-workout_date', '-created_at']
        verbose_name = "Súlykontroll adat"
        verbose_name_plural = "Súlykontroll adatok"

    def __str__(self):
        return f"{self.user.username} - {self.morning_weight} kg ({self.workout_date})"