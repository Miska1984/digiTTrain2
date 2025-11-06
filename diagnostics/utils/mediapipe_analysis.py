# diagnostics/utils/mediapipe_analysis.py - TISZTÍTOTT, HELYREÁLLÍTOTT VÁLTOZAT

import cv2
import mediapipe as mp
import numpy as np  # Fontos az np.array és np.mean miatt
import os
from django.conf import settings
from typing import List, Dict, Any

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


# 💡 SEGÉDFÜGGVÉNY: Szög számítás (ELÉRHETŐVÉ TÉVE)
def calculate_angle(p1: Dict[str, float], p2: Dict[str, float], p3: Dict[str, float]) -> float:
    """Szög kiszámítása 3 kulcspont között fokban."""
    try:
        p1 = np.array([p1['x'], p1['y']])
        p2 = np.array([p2['x'], p2['y']])
        p3 = np.array([p3['x'], p3['y']])

        radians = np.arctan2(p3[1]-p2[1], p3[0]-p2[0]) - np.arctan2(p1[1]-p2[1], p1[0]-p2[0])
        angle = np.abs(radians*180.0/np.pi)

        if angle > 180.0:
            angle = 360 - angle
        return angle
    except:
        return 0.0


# 🆕 EXPORTÁLT FÜGGVÉNY: A PostureAssessmentService ezt fogja importálni!
def calculate_imbalance_metrics(raw_keypoints: List[Dict[str, Any]]) -> dict:
    """
    Kiszámolja a váll és a csípő aszimmetria metrikáit a nyers kulcspont adatokból.
    """
    shoulder_angles = []
    hip_angles = []
    
    for frame_data in raw_keypoints:
        landmarks = frame_data.get("landmarks", {})
        
        if not all(k in landmarks for k in ['RIGHT_SHOULDER', 'LEFT_SHOULDER', 'RIGHT_HIP', 'LEFT_HIP']):
            continue 

        # 1. VÁLL SZIMMETRIA:
        shoulder_diff = abs(landmarks['RIGHT_SHOULDER']['y'] - landmarks['LEFT_SHOULDER']['y'])
        shoulder_angles.append(shoulder_diff * 100) 

        # 2. CSÍPŐ SZIMMETRIA:
        hip_diff = abs(landmarks['RIGHT_HIP']['y'] - landmarks['LEFT_HIP']['y'])
        hip_angles.append(hip_diff * 100) 
    
    avg_shoulder_imbalance = np.mean(shoulder_angles) if shoulder_angles else 0
    avg_hip_imbalance = np.mean(hip_angles) if hip_angles else 0

    return {
        "avg_shoulder_imbalance": float(avg_shoulder_imbalance),
        "avg_hip_imbalance": float(avg_hip_imbalance),
    }

def calculate_squat_metrics(raw_keypoints: List[Dict[str, Any]]) -> dict:
    """
    Kiszámítja a guggolás fő metrikáit (mélység, térd-boka szög) a nyers kulcspont adatokból.
    
    FONTOS: A guggolás dinamikus elemzése komplex, itt egy egyszerűsített megközelítést használunk 
    a térd és csípő szögének átlagolására.
    """
    
    # A MediaPipe kulcspont indexek:
    # BAL TÉRD: 25, BAL BOKA: 27, BAL CSÍPŐ: 23
    # JOBB TÉRD: 26, JOBB BOKA: 28, JOBB CSÍPŐ: 24

    all_knee_angles = []
    all_hip_angles = []
    
    for frame_data in raw_keypoints:
        landmarks = frame_data.get("landmarks", {})
        
        # Ellenőrizzük, hogy minden szükséges pont létezik-e (itt csak a fő 6 pontot nézzük)
        required_keys = ['LEFT_HIP', 'LEFT_KNEE', 'LEFT_ANKLE', 'RIGHT_HIP', 'RIGHT_KNEE', 'RIGHT_ANKLE']
        if not all(k in landmarks for k in required_keys):
            continue
            
        # 1. TÉRD SZÖG: Bal (Csípő-Térd-Boka)
        left_knee_angle = calculate_angle(
            landmarks['LEFT_HIP'], landmarks['LEFT_KNEE'], landmarks['LEFT_ANKLE']
        )
        # 2. TÉRD SZÖG: Jobb
        right_knee_angle = calculate_angle(
            landmarks['RIGHT_HIP'], landmarks['RIGHT_KNEE'], landmarks['RIGHT_ANKLE']
        )
        
        # 3. CSÍPŐ SZÖG: Bal (Váll-Csípő-Térd - ami az előre dőlést mutatja)
        # Váll kulcspontok is kellenének ehhez, de a testtartás oldalsó felmérésre összpontosítunk:
        # A mostani Service oldalsó nézetet feltételez, így a BOKA-CSÍPŐ-VÁLL is jó lehet.
        # Itt most a Csípő-Vállat hagyjuk ki, csak a térd és boka közti szögeket számoljuk.
        
        # A guggolás mélységéhez: a csípő 'y' koordinátáját nézzük a térd 'y' koordinátájához képest
        # (alacsonyabb 'y' koordináta = mélyebb guggolás a normalizált koordinátákban)
        
        # Ha a csípő az alacsonyabb (mélyebb guggolás)
        # Itt egy egyszerűsített logikát használunk a szögek alapján: 
        if left_knee_angle > 0 and right_knee_angle > 0:
            all_knee_angles.append((left_knee_angle + right_knee_angle) / 2)
            
            # A guggolás "mélysége" egy becsült szög alapján (kb. 90 fokos térd)
            # A 180 fok a állás, 90 fok a mély guggolás. A "mélység" értéke itt a 180-szög (hogy 0-tól induljon)
            all_hip_angles.append(180 - all_knee_angles[-1])

    # 4. Metrikák aggregálása
    if not all_knee_angles:
        return {"error": "Nincs elegendő guggolási adat az elemzéshez."}

    # Átlagos maximális mélység (max 90 fok (180-90))
    avg_max_depth_angle = np.mean(all_hip_angles)
    
    # 5. Eredmény
    return {
        # Az átlagos max. mélység százalékban kifejezve (pl. 90 fokos eltérés a max, az 100%)
        "max_squat_depth_avg": round(min(100, (avg_max_depth_angle / 90) * 100), 1),
        "avg_knee_angle": round(np.mean(all_knee_angles), 1),
        # A valgus és más metrikák itt kapnának helyet a valós elemzésben.
        "feedback": ["A számítás az átlagos guggolási mélységet és térdszöget tartalmazza."],
    }

