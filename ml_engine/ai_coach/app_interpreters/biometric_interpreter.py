# biometric_interpreter.py

from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback
from django.db.models import Avg
from datetime import timedelta
from django.utils import timezone

class BiometricInterpreter:
    def __init__(self, target_user):
        self.target_user = target_user
        self.now = timezone.now().date()
        self.start_date = self.now - timedelta(days=14) # Az utolsó 2 hét trendjeit nézzük

    def get_biometric_summary(self):
        last_7_days = timezone.now() - timedelta(days=7)
        
        # JAVÍTÁS: recorded_at használata a korábbi measured_at helyett
        hrv_data = HRVandSleepData.objects.filter(
            user=self.target_user, 
            recorded_at__gte=last_7_days
        ).order_by('-recorded_at')

        # Súly adatok - itt is ellenőrizd a mezőnevet, ha hiba jönne, 
        # de a log most csak a HRV-nél állt meg.
        weight_data = WeightData.objects.filter(
            user=self.target_user,
            workout_date__gte=last_7_days.date()
        ).order_by('-workout_date')

        if not hrv_data.exists() and not weight_data.exists():
            return "Nincsenek biometriai adatok az elmúlt 7 napból."

        summary = ["--- Biometriai Trendek (7 nap) ---"]

        if hrv_data.exists():
            # Figyelem: A log szerint a mező neve 'hrv' (nem hrv_rmssd)
            avg_hrv = sum(d.hrv for d in hrv_data if d.hrv) / hrv_data.count()
            summary.append(f"Átlagos HRV: {round(avg_hrv, 1)} ms")
            summary.append(f"Utolsó alvásminőség: {hrv_data.first().sleep_quality or '?'}/10")

        if weight_data.exists():
            latest_w = weight_data.first().morning_weight
            summary.append(f"Legutóbbi testsúly: {latest_w} kg")

        return "\n".join(summary)

    def _analyze_trends(self, hrv_data):
        if hrv_data.count() < 3:
            return "Kevés adat a trendelemzéshez."
        
        latest = hrv_data[0]
        prev = hrv_data[1]
        
        if latest.hrv and prev.hrv and latest.hrv < prev.hrv * 0.9:
            if latest.sleep_quality and latest.sleep_quality < 5:
                return "VIGYÁZAT: A HRV jelentősen csökkent a rossz alvásminőség mellett. Túlfáradás veszélye!"
        
        return "A biometriai értékek stabilak."