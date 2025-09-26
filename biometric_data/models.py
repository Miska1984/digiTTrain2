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
    # A hiányzó CHOICES konstansok hozzáadása
    SLEEP_QUALITY_CHOICES = [
        (None, '--- Válassz minőséget (opcionális) ---'),
        (1, '1 - Nagyon rossz minőségű'),
        (2, '2 - Rossz, gyakori ébredéssel'),
        (3, '3 - Átlag alatti, nem pihentető'),
        (4, '4 - Átlagos, kielégítő'),
        (5, '5 - Jó, gyors elalvással'),
        (6, '6 - Nagyon jó, mély alvással'),
        (7, '7 - Kipihent, regeneráló'),
        (8, '8 - Kiváló, ébredés nélkül'),
        (9, '9 - Szinte tökéletes'),
        (10, '10 - Tökéletes alvás'),
    ]

    ALERTNESS_CHOICES = [
        (None, '--- Válassz közérzetet (opcionális) ---'),
        (1, '1 - Extrém fáradtság, kimerültség'),
        (2, '2 - Nagyon fáradt, nehéz koncentrálni'),
        (3, '3 - Fáradt, de működőképes'),
        (4, '4 - Átlagos, pici kávé kell'),
        (5, '5 - Éber, fókuszált'),
        (6, '6 - Nagyon éber, energikus'),
        (7, '7 - Magas energia szint'),
        (8, '8 - Kiegyensúlyozottan motivált'),
        (9, '9 - Mentálisan a csúcson'),
        (10, '10 - Tökéletes közérzet'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    hrv = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="HRV (ms)")
    sleep_quality = models.IntegerField(choices=SLEEP_QUALITY_CHOICES[1:], null=True, blank=True, verbose_name="Alvás Minősége")
    alertness = models.IntegerField(choices=ALERTNESS_CHOICES[1:], null=True, blank=True, verbose_name="Éberség / Közérzet")
    recorded_at = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "HRV és Alvás Adat"
        verbose_name_plural = "HRV és Alvás Adatok"
        ordering = ['-recorded_at']
        # Kiegészítés: A DateField-re már van a modellben egy unique_together/index_together,
        # különben engedi ugyanarra a napra rögzíteni. 
        # Példa: unique_together = (("user", "recorded_at"),)

    def __str__(self):
        return f"{self.user.username} - {self.recorded_at} HRV/Sleep"

class WorkoutFeedback(models.Model):
    INTENSITY_CHOICES = [
        (None, '--- Válassz intenzitást (opcionális) ---'),
        (1, '1 - Nagyon könnyű (Bemelegítés, regeneráló)'),
        (2, '2 - Könnyű (Szinte nincs terhelés)'),
        (3, '3 - Közepes (Kényelmes, hosszan tartható)'),
        (4, '4 - Kicsit kemény (Megéri az erőlködés)'),
        (5, '5 - Mérsékelt (Kellemesen nehéz)'),
        (6, '6 - Elég kemény (Kicsit nehezebb, mint a komfortzóna)'),
        (7, '7 - Kemény (Komfortzónán kívül, még kontrollálható)'),
        (8, '8 - Nagyon kemény (Nehéz fenntartani)'),
        (9, '9 - Extrém (Csak rövidebb ideig tartható)'),
        (10, '10 - Maximális (Minden erőfeszítés)'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    right_grip_strength = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Jobb marokerő (kg)")
    left_grip_strength = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Bal marokerő (kg)")
    workout_intensity = models.IntegerField(
        choices=INTENSITY_CHOICES[1:], # A [1:] kizárja a 'Válassz' sort a mentésből
        null=True, 
        blank=True, 
        verbose_name="Edzésintenzitás", 
        help_text="1-10 közötti skálán"
    )
    # 
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