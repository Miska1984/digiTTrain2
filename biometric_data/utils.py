# /app/biometric_data/utils.py

from datetime import timedelta
from django.utils import timezone
import json # Kelleni fog a JSON adatokhoz

# Feltételezett importok a modellekre:
# (Ezeket a te kódodban lévő modelleket kell importálnod)
from .models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance

# --- Konfiguráció ---
# Az adathiány jelzéséhez használt küszöb (pl. 3 napnál régebbi adatot hiányzónak jelez)
DATA_MISSING_THRESHOLD_DAYS = 3 

def get_last_entry_info(athlete):
    """
    Megkeresi a négy fő modell utolsó bejegyzésének dátumát.
    """
    today = timezone.localdate()
    
    # 1. Lekérdezési lista
    data_sources = [
        {"model": WeightData, "date_field": "workout_date", "name": "Testsúly"},
        {"model": HRVandSleepData, "date_field": "recorded_at", "name": "HRV/Alvás"},
        {"model": WorkoutFeedback, "date_field": "workout_date", "name": "Edzés Visszajelzés"},
        {"model": RunningPerformance, "date_field": "run_date", "name": "Futóteljesítmény"},
    ]
    
    last_entries_data = []
    missing_data_messages = []
    
    # 2. Iteráció és lekérdezés
    for source in data_sources:
        latest_entry = source["model"].objects.filter(user=athlete).order_by(f'-{source["date_field"]}').first()
        
        entry_name = source["name"]
        
        if latest_entry:
            # Dátum mező lekérése
            last_date_raw = getattr(latest_entry, source["date_field"])
            
            # BIZTONSÁGOS JAVÍTÁS: Kezeli a date és a datetime típusokat is.
            # Ha datetime.datetime (van .date() metódusa), konvertáljuk dátummá.
            if hasattr(last_date_raw, 'date'):
                last_date = last_date_raw.date()
            # Ha datetime.date (csak dátum), közvetlenül használjuk.
            else:
                last_date = last_date_raw
                
            days_since = (today - last_date).days
            
            status_class = "text-success"
            if days_since >= 3: # Feltételezett küszöb
                status_class = "text-warning"
                missing_data_messages.append(f"Figyelem! {entry_name} adat {days_since} napja hiányzik.")
            elif days_since > 7:
                status_class = "text-danger"
                missing_data_messages.append(f"Kritikus! {entry_name} adat több mint egy hete hiányzik!")
                
            last_entries_data.append({
                "name": entry_name,
                "last_date": last_date.strftime("%Y. %m. %d."),
                "days_since": days_since,
                "status_class": status_class
            })
        else:
            # ... (A korábbi else ág)
            last_entries_data.append({
                "name": entry_name,
                "last_date": "Nincs rögzítve",
                "days_since": -1,
                "status_class": "text-danger"
            })
            missing_data_messages.append(f"Nincs rögzített {entry_name} adat a sportolóhoz.")

    return last_entries_data, missing_data_messages


# --- Későbbi fejlesztésekhez: Testsúly, HRV, Fáradtság ---

### 2. **Testsúly Adatok és Trend Értékelése**


def get_weight_data_and_feedback(athlete, start_date):
    """
    Lekéri a testsúly adatokat és kiszámítja a trendet a megadott dátumtól.
    """
    weight_entries = WeightData.objects.filter(
        user=athlete,
        workout_date__gte=start_date
    ).order_by("workout_date")
    
    data = list(weight_entries.values_list('morning_weight', flat=True))
    dates = [entry.workout_date.strftime("%Y-%m-%d") for entry in weight_entries]
    
    # 1. Grafikon adatok
    chart_data = {
        "labels": dates,
        "weights": [float(w) for w in data],
    }
    
    feedback = "Nincs elegendő adat az értékeléshez a választott időszakban."
    
    # 2. Trend számítás (egyszerű lineáris trend vagy átlagos változás)
    if len(data) >= 3:
        start_weight = data[0]
        end_weight = data[-1]
        change = end_weight - start_weight
        
        trend_class = "text-info"
        trend_direction = "stabil"
        
        if abs(change) > 0.5: # Pl. 500g változás a trendjelzéshez
            if change > 0:
                trend_direction = "növekvő"
                trend_class = "text-warning"
            else:
                trend_direction = "csökkenő"
                trend_class = "text-warning"
        
        feedback = (f"A testsúly **{len(dates)} napos** trendje **{trend_direction}**. "
                    f"Összes változás: <span class='fw-bold {trend_class}'>{change:+.2f} kg</span>.")
    
    return chart_data, feedback

### 3. **HRV/Regenerációs Index**


def get_hrv_regeneration_index(athlete, start_date):
    """
    Színkódolt regenerációs index az elmúlt 3 nap HRV adatai alapján.
    """
    recent_hrv = HRVandSleepData.objects.filter(
        user=athlete,
        recorded_at__gte=start_date
    ).order_by('-recorded_at')[:3]
    
    if not recent_hrv:
        return {"status": "N/A", "message": "Nincs friss HRV adat.", "class": "text-muted"}
    
    # A regenerációt a Sleep Score-ra alapozzuk, ha van, különben HRV-re. 
    # (Feltételezve, hogy a Sleep Score 0-100 között mozog)
    # A logikát a te modelledhez kell igazítani!
    
    sleep_scores = [float(entry.sleep_score) for entry in recent_hrv if hasattr(entry, 'sleep_score')] # VAGY HRV mező
    
    if not sleep_scores:
        return {"status": "N/A", "message": "Nem értelmezhető alvási/HRV adatok.", "class": "text-muted"}

    avg_score = sum(sleep_scores) / len(sleep_scores)
    
    if avg_score >= 80:
        return {"status": "Kiváló", "message": "A regeneráció kiváló.", "class": "text-success"}
    elif avg_score >= 60:
        return {"status": "Jó", "message": "A regeneráció a normál tartományban van.", "class": "text-primary"}
    elif avg_score >= 40:
        return {"status": "Közepes", "message": "Enyhe fáradtság jelei.", "class": "text-warning"}
    else:
        return {"status": "Rossz", "message": "Jelentős regenerációs elmaradás!", "class": "text-danger"}

def get_latest_fatigue_status(athlete):
    """
    A legutóbbi edzés visszajelzés (RPE vagy Fáradtság érték) alapján ad jelzést.
    (Feltételezve, hogy a WorkoutFeedback-ben van egy 'fatigue_rpe' mező 1-10 skálán)
    """
    latest_feedback = WorkoutFeedback.objects.filter(user=athlete).order_by('-workout_date').first()
    
    if not latest_feedback or not hasattr(latest_feedback, 'fatigue_rpe'):
        return {"status": "N/A", "message": "Nincs rögzített edzés visszajelzés.", "class": "text-muted"}

    fatigue_level = getattr(latest_feedback, 'fatigue_rpe') 
    
    if fatigue_level >= 7:
        return {"status": "Magas", "message": f"Utolsó edzés utáni fáradtsági szint (RPE): {fatigue_level}.", "class": "text-danger"}
    elif fatigue_level >= 5:
        return {"status": "Közepes", "message": f"Utolsó edzés utáni fáradtsági szint (RPE): {fatigue_level}.", "class": "text-warning"}
    else:
        return {"status": "Alacsony", "message": f"Utolsó edzés utáni fáradtsági szint (RPE): {fatigue_level}.", "class": "text-success"}
    
