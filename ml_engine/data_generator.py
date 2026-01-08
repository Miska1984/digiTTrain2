import random
import numpy as np
import pandas as pd

class SyntheticDataGenerator:
    """
    Kategória-specifikus sportolói adatokat generál a modell tanításához.
    """
    
    def __init__(self):
        self.categories = ['COMBAT', 'TEAM', 'ENDURANCE', 'POWER_TECH']

    def generate_batch(self, count_per_category=2500):
        all_data = []
        
        for cat in self.categories:
            for _ in range(count_per_category):
                data = self._generate_single_row(cat)
                all_data.append(data)
        
        return pd.DataFrame(all_data)

    def _generate_single_row(self, category):
        # 1. Demográfia
        age = random.randint(16, 55)
        gender = random.choice([0, 1]) # 0: Nő, 1: Férfi
        
        # 2. Alapértékek kategória szerint (Grip Strength kg-ban)
        if category == 'COMBAT' or category == 'POWER_TECH':
            base_grip = random.uniform(40, 65) if gender == 1 else random.uniform(25, 45)
        else:
            base_grip = random.uniform(30, 50) if gender == 1 else random.uniform(20, 35)

        # 3. Élettani állapot (HRV és Alvás)
        # Idősebbeknél picit alacsonyabb HRV-t generálunk
        age_factor = (60 - age) / 40
        hrv = random.uniform(40, 90) * age_factor + random.uniform(-5, 5)
        sleep_quality = random.uniform(4, 10)

        # 4. A TE LOGIKÁD: Súlyvesztés és Hidratáció
        # Normál esetben 0.5 - 2.5 kg közötti vesztés
        weight_before = random.uniform(60, 110)
        # Ha kemény az edzés (véletlenszerű), nagyobb a súlyvesztés
        intensity = random.uniform(3, 10)
        actual_loss = (intensity * 0.2) + random.uniform(0.1, 0.8)
        
        # Folyadékpótlás (0 és a veszteség 80%-a között)
        fluid_intake = actual_loss * random.uniform(0, 0.8) * 1000 
        
        # Kiszámolt dehidratációs index (mint a FeatureBuilderben)
        weight_after = weight_before - (actual_loss - (fluid_intake/1000))
        weight_loss_delta = (weight_before - weight_after) + (fluid_intake / 1000)
        dehydration_index = weight_loss_delta / weight_before

        # 5. FORMAINDEKS (Célváltozó) Kiszámítása - A FeatureBuilder logikáját másolva
        # Itt "tanítjuk meg" a modellnek az összefüggést
        hrv_score = np.clip(hrv, 0, 100)
        grip_score = base_grip * (0.9 if sleep_quality < 6 else 1.0) # Fáradtan gyengébb grip
        
        # Hidratációs büntetés
        hydro_penalty = 100 - (dehydration_index * 1000)
        
        # Súlyozás kategória szerint
        if category == 'COMBAT':
            form_score = (hrv_score * 0.25) + (grip_score * 0.45) + (hydro_penalty * 0.30)
        elif category == 'ENDURANCE':
            form_score = (hrv_score * 0.45) + (grip_score * 0.15) + (hydro_penalty * 0.40)
        else:
            form_score = (hrv_score * 0.35) + (grip_score * 0.35) + (hydro_penalty * 0.30)

        return {
            'age': age,
            'gender': gender,
            'category': category,
            'avg_hrv': round(hrv, 2),
            'avg_sleep': round(sleep_quality, 1),
            'grip_right': round(base_grip, 1),
            'grip_left': round(base_grip * random.uniform(0.9, 1.1), 1),
            'weight_loss_delta': round(weight_loss_delta, 3),
            'dehydration_index': round(dehydration_index, 4),
            'form_score': round(np.clip(form_score, 0, 100), 2)
        }