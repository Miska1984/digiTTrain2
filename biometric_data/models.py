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

class HRVandSleepData(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    hrv = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="HRV (ms)")
    sleep_quality = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name="Alvásminőség", 
        help_text="1-10 közötti skálán"
    )
    recorded_at = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "HRV és alvás adat"
        verbose_name_plural = "HRV és alvás adatok"
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.user.username} - {self.recorded_at} HRV: {self.hrv}, Alvás: {self.sleep_quality}"

class WorkoutFeedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    right_grip_strength = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Jobb marokerő (kg)")
    left_grip_strength = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Bal marokerő (kg)")
    workout_intensity = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name="Edzésintenzitás", 
        help_text="1-10 közötti skálán"
    )
    workout_date = models.DateField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Edzésvisszajelzés"
        verbose_name_plural = "Edzésvisszajelzések"
        ordering = ['-workout_date']

    def __str__(self):
        return f"{self.user.username} - {self.workout_date} Feedback"
    
class RunningPerformance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    run_distance_km = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Táv (km)")
    run_duration = models.DurationField(verbose_name="Idő")
    run_min_hr = models.IntegerField(null=True, blank=True, verbose_name="Minimum pulzus (bpm)")
    run_max_hr = models.IntegerField(null=True, blank=True, verbose_name="Maximum pulzus (bpm)")
    run_avg_hr = models.IntegerField(null=True, blank=True, verbose_name="Átlagos pulzus (bpm)") # Opcionális
    
    # Kiegészítő mező az időponthoz
    run_date = models.DateField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Futó teljesítmény"
        verbose_name_plural = "Futó teljesítmények"
        ordering = ['-run_date']

    def __str__(self):
        return f"{self.user.username} - {self.run_distance_km} km ({self.run_date})"