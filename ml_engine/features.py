import logging
from datetime import timedelta
from django.utils import timezone
from django.db import models
# Importáljuk a biometriai modelleket
from biometric_data.models import WeightData, WorkoutFeedback, HRVandSleepData

logger = logging.getLogger(__name__)

class FeatureBuilder:
    """
    Összegyűjti és számszerűsíti a felhasználó biometriai adatait 
    az ML modell számára (Features).
    """

    def __init__(self, user):
        self.user = user

    def build(self):
        """
        Felépíti a feature vektort a felhasználó adataiból.
        Visszatérési érték: [dict] vagy None
        """
        # 1. Alapadatok lekérése az elmúlt 30 napból
        since_date = timezone.now().date() - timedelta(days=30)
        
        # Lekérések a különböző táblákból
        weights = WeightData.objects.filter(user=self.user, workout_date__gte=since_date).order_by('-workout_date')
        feedback = WorkoutFeedback.objects.filter(user=self.user, workout_date__gte=since_date).order_by('-workout_date')
        recovery = HRVandSleepData.objects.filter(user=self.user, recorded_at__gte=since_date).order_by('-recorded_at')

        # --- 2. HIDRATÁCIÓS MÉRLEG (WeightData-ból) ---
        latest_weight_entry = weights.first()
        weight_loss_delta = 0
        dehydration_index = 0

        if latest_weight_entry:
            w_pre = latest_weight_entry.pre_workout_weight
            w_post = latest_weight_entry.post_workout_weight
            # fluid_intake nálad l-ben van (pl. 0.5), a delta számításhoz float-ra váltunk
            fluid = latest_weight_entry.fluid_intake or 0

            if w_pre and w_post:
                # Képlet: (Előtte - Utána) + Bevitt folyadék
                weight_loss_delta = float(w_pre - w_post) + float(fluid)
                dehydration_index = weight_loss_delta / float(w_pre) if w_pre > 0 else 0

        # --- 3. REGENERÁCIÓS MUTATÓK (HRVandSleepData-ból) ---
        # Ha nincsenek adatok, biztonsági alapértelmezett értékeket adunk (50 ms HRV, 7.0 alvás)
        hrv_avg = float(recovery.aggregate(models.Avg('hrv'))['hrv__avg'] or 50.0)
        sleep_avg = float(recovery.aggregate(models.Avg('sleep_quality'))['sleep_quality__avg'] or 7.0)

        # --- 4. MAROKERŐ ÉS INTENZITÁS (WorkoutFeedback-ből) ---
        latest_f = feedback.first()
        # Ha nincs visszajelzés, 40 kg-os átlagos marokerőt feltételezünk
        grip_l = float(latest_f.left_grip_strength or 40.0) if latest_f else 40.0
        grip_r = float(latest_f.right_grip_strength or 40.0) if latest_f else 40.0

        # --- 5. FEATURE VEKTOR ÖSSZEÁLLÍTÁSA (A te struktúrádhoz igazítva) ---
        
        # Életkor lekérése a Profile-ból
        user_age = 30
        if hasattr(self.user, 'profile') and self.user.profile.date_of_birth:
            user_age = self.user.profile.age_years() or 30

        # Nem lekérése a Profile-ból
        user_gender = 1 # Alapértelmezett Férfi
        if hasattr(self.user, 'profile'):
            user_gender = 1 if self.user.profile.gender == 'M' else 0

        # Sport kategória lekérése a UserRole -> Sport útvonalon
        user_category = 'COMBAT' # Alapértelmezett
        latest_role = self.user.user_roles.select_related('sport').first()
        if latest_role and latest_role.sport:
            user_category = latest_role.sport.category

        features = {
            'age': user_age,
            'gender': user_gender,
            'category': user_category,
            'avg_hrv': round(hrv_avg, 2),
            'avg_sleep': round(sleep_avg, 1),
            'grip_right': round(grip_r, 1),
            'grip_left': round(grip_l, 1),
            'weight_loss_delta': round(weight_loss_delta, 3),
            'dehydration_index': round(dehydration_index, 4),
        }

        # Kiszámoljuk a pontszámokat, hogy a Dashboard kártyái lássák
        features['form_score'] = round((hrv_avg * 0.6) + (sleep_avg * 2), 2)
        features['injury_risk_index'] = round(1.0 + (dehydration_index * 5), 2)

        # FONTOS: Vedd le a szögletes zárójelet! Csak a szótárat adjuk vissza.
        return features