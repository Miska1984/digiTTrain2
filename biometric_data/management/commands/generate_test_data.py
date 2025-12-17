import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance

class Command(BaseCommand):
    help = 'Generates 90 days of synthetic biometric data for specified users for testing ML algorithms.'

    def handle(self, *args, **options):
        
        # --- KONFIGURÁCIÓ ---
        # Felhasználói ID-k a fiktív felhasználókhoz (Zoárd=1, Rihárd=4, Péter=5, Fruzsina=6)
        USER_IDS = [1, 4, 5, 6] 
        DAYS_TO_GENERATE = 90

        # Alapértelmezett súlyok
        BASE_WEIGHTS = {
            1: 75.0,  # Zoárd
            4: 65.0,  # Rihárd
            5: 85.0,  # Péter
            6: 40.0,  # Fruzsina
        }
        
        User = get_user_model()
        today = date.today()

        self.stdout.write(self.style.NOTICE(f"--- Adatgenerálás indul {DAYS_TO_GENERATE} napra visszamenőleg ({today}-ig) ---"))

        for user_id in USER_IDS:
            try:
                user = User.objects.get(pk=user_id)
                base_weight = BASE_WEIGHTS.get(user_id, 70.0)
                self.stdout.write(self.style.SUCCESS(f"\n🚀 {user.username} (ID: {user_id}) adatainak generálása:"))
                
                # --- Generálás indítása ---
                
                for i in range(DAYS_TO_GENERATE):
                    current_date = today - timedelta(days=i)
                    
                    # 1. WEIGHT DATA
                    morning_weight = round(base_weight + random.uniform(-0.5, 0.5), 2)
                    
                    if i % 2 == 0: # Edzésnap
                        pre_weight = round(morning_weight + random.uniform(0.1, 0.3), 2)
                        post_weight = round(pre_weight - random.uniform(0.5, 1.5), 2)
                        fluid = round(random.uniform(1.0, 3.0), 2)
                    else: # Pihenőnap
                        pre_weight = None
                        post_weight = None
                        fluid = None
                        
                    WeightData.objects.create(
                        user=user,
                        morning_weight=morning_weight,
                        pre_workout_weight=pre_weight,
                        post_workout_weight=post_weight,
                        fluid_intake=fluid,
                        body_fat_percentage=round(random.uniform(10.0, 25.0), 1),
                        muscle_percentage=round(random.uniform(30.0, 50.0), 1),
                        bone_mass_kg=round(random.uniform(2.5, 4.0), 2),
                        workout_date=current_date
                    )
                    
                    # 2. HRV and SLEEP DATA
                    hrv_value = round(random.uniform(45.0, 85.0), 2)
                    sleep = random.randint(5, 8)
                    alertness = random.randint(4, 7)
                    
                    HRVandSleepData.objects.create(
                        user=user,
                        hrv=hrv_value,
                        sleep_quality=sleep,
                        alertness=alertness,
                        recorded_at=current_date
                    )
                    
                    # 3. WORKOUT FEEDBACK (Edzésnapokon)
                    if i % 2 == 0: 
                        right_grip = round(random.uniform(30.0, 70.0), 2)
                        left_grip = round(right_grip + random.uniform(-2.0, 2.0), 2)
                        intensity = random.randint(5, 8)
                        
                        WorkoutFeedback.objects.create(
                            user=user,
                            right_grip_strength=right_grip,
                            left_grip_strength=left_grip,
                            workout_intensity=intensity,
                            workout_date=current_date
                        )
                        
                    # 4. RUNNING PERFORMANCE (Minden harmadik nap)
                    if i % 3 == 0:
                        distance = round(random.uniform(5.0, 15.0), 2)
                        duration_minutes = random.randint(int(distance * 4), int(distance * 7)) 
                        run_duration = timedelta(minutes=duration_minutes)
                        avg_hr = random.randint(140, 180)
                        min_hr = avg_hr - random.randint(10, 20)
                        max_hr = avg_hr + random.randint(5, 15)
                        
                        RunningPerformance.objects.create(
                            user=user,
                            run_distance_km=distance,
                            run_duration=run_duration,
                            run_min_hr=min_hr,
                            run_max_hr=max_hr,
                            run_avg_hr=avg_hr,
                            run_date=current_date
                        )

                self.stdout.write(self.style.SUCCESS(f"  -> Sikeresen generálva {DAYS_TO_GENERATE} nap adatai."))

            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"⚠️ Hiba: A {user_id} ID-val rendelkező felhasználó nem található."))
            except IntegrityError as e:
                 self.stdout.write(self.style.ERROR(f"❌ Integritási hiba: A {user.username} adatoknál ütközés: {e}. (Lehetséges, hogy már léteznek adatok a táblában)"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Általános hiba történt {user.username} adatainak generálásakor: {e}"))

        self.stdout.write(self.style.NOTICE("\n--- Adatgenerálás befejezve! ---"))