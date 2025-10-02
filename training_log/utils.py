# /app/training_log/utils.py

from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta, date
import pandas as pd
import numpy as np
from .models import TrainingSession, Attendance,  TrainingSchedule, AbsenceSchedule
from assessment.models import PlaceholderAthlete # Szükséges a PH sportolókhoz

# --- Időintervallum definíciók (a Dashboardhoz) ---
TIME_PERIODS = {
    '3D': 3,
    '7D': 7,
    '14D': 14,
    '1M': 30,
    '2M': 60,
    '3M': 90
}


def get_attendance_summary(athlete, days):
    """
    Kiszámítja az edzéslátogatás arányát és a töltött időt a megadott napon belül.
    A funkció kezeli a regisztrált (User) és a nem regisztrált (PlaceholderAthlete) sportolókat is.
    """
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days)

    # 1. Keresés a megfelelő Athlete ID alapján
    if hasattr(athlete, 'is_authenticated') and athlete.is_authenticated:
        # Regisztrált sportoló
        registered_id = athlete.id
        placeholder_id = None
        # Lekérjük a sportolóhoz manuálisan kapcsolt Placeholder rekordot is
        try:
            placeholder_record = PlaceholderAthlete.objects.get(registered_user=athlete)
            placeholder_id = placeholder_record.id
        except PlaceholderAthlete.DoesNotExist:
            pass
    else:
        # Nem regisztrált (Placeholder) sportoló
        placeholder_id = athlete.id
        registered_id = None

    # 2. Lekérdezési feltétel (OR logika a két ID-vel)
    q_filter = Q(session__session_date__range=(start_date, end_date)) & (
        Q(registered_athlete__id=registered_id) | Q(placeholder_athlete__id=placeholder_id)
    )

    # Összes edzés lekérdezése az időszakban (szűrés a Q feltétellel)
    all_sessions_in_period = TrainingSession.objects.filter(session_date__range=(start_date, end_date)).count()
    
    if all_sessions_in_period == 0:
        return {
            'period_days': days,
            'sessions_attended': 0,
            'total_sessions': 0,
            'attendance_rate': 0.0,
            'time_spent_minutes': 0,
        }

    # Jelenléti rekordok lekérdezése
    attendance_records = Attendance.objects.filter(q_filter).select_related('session')

    sessions_attended = attendance_records.filter(is_present=True).count()
    
    # Kiszámítjuk az edzéssel töltött összes percet
    time_spent_minutes = attendance_records.filter(is_present=True).aggregate(
        total_duration=Sum('session__duration_minutes')
    )['total_duration'] or 0

    attendance_rate = (sessions_attended / all_sessions_in_period) * 100 if all_sessions_in_period > 0 else 0.0

    return {
        'period_days': days,
        'sessions_attended': sessions_attended,
        'total_sessions': all_sessions_in_period,
        'attendance_rate': round(attendance_rate, 1),
        'time_spent_minutes': time_spent_minutes,
    }

# --- B. Segédfüggvény: Mozgóátlag és Trend Analízis ---

def calculate_rolling_avg_and_trend(model, athlete, date_field, value_field, days_window):
    """
    Kiszámítja az adatok mozgóátlagát egy adott ablakban (days_window) és
    egy egyszerű lineáris regressziós trendet az utolsó 3 hónapra.
    """
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=90) # Trendet mindig 3 hónapon nézzük

    # 1. Lekérdezés
    # A lekérdezést az User ID alapján végezzük
    data = model.objects.filter(
        user=athlete,
        **{f'{date_field}__range': (start_date, end_date)}
    ).order_by(date_field).values(date_field, value_field)

    if not data:
        return {'chart_data': [], 'trend_text': "Nincs elegendő adat a trend elemzéshez.", 'current_avg': None}

    # 2. Pandas DataFrame előkészítése
    df = pd.DataFrame(list(data))
    df['date'] = df[date_field]
    df.set_index('date', inplace=True)
    df = df[[value_field]].astype(float)

    # 3. Mozgóátlag (Rolling Average) számítás
    rolling_avg = df[value_field].rolling(window=days_window, min_periods=1).mean().round(2)

    # 4. Lineáris Trend (egyszerű regresszió)
    # A napok számát használjuk X-tengelyként
    df['days'] = (df.index - df.index.min()).days
    
    # Lineáris regresszió illesztése
    try:
        slope, intercept = np.polyfit(df['days'], df[value_field], 1)
    except np.linalg.LinAlgError:
         slope = 0 # Ha hiba van a számításban, feltételezzük a 0 dőlésszöget
    
    # 5. Trend Értékelés
    if slope > 0.05:
        trend_text = "Emelkedő trend (pozitív változás)"
    elif slope < -0.05:
        trend_text = "Csökkenő trend (negatív változás)"
    else:
        trend_text = "Stagnáló/Stabil tendencia"
        
    # 6. Összesítés a Chart.js számára
    chart_data = {
        'labels': df.index.strftime('%Y-%m-%d').tolist(),
        'values': df[value_field].tolist(),
        'rolling_avg': rolling_avg.tolist()
    }

    return {
        'chart_data': chart_data,
        'trend_text': trend_text,
        'current_avg': round(rolling_avg.iloc[-1], 2) if not rolling_avg.empty else None
    }

def calculate_next_training_sessions(schedule_id, club_id, future_limit=5, past_days=30):
    """
    Kiszámolja egy adott TrainingSchedule következő 'future_limit' számú edzésnapját
    ÉS az elmúlt 'past_days' nap összes edzését, figyelembe véve a szüneteket.
    A visszaadott lista növekvő sorrendben van rendezve (múltból a jövőbe).
    """
    try:
        schedule = TrainingSchedule.objects.get(id=schedule_id)
    except TrainingSchedule.DoesNotExist:
        return []

    # 1. Időkeret beállítása
    start_date_range = date.today() - timedelta(days=past_days)
    end_date_range = date.today() + timedelta(days=365) # Max 1 év a jövőben
    today = date.today()
    
    # 2. Lekérjük az összes aktív szünetet a releváns klubra/sportágra és az időkeretre
    absences = AbsenceSchedule.objects.filter( 
        Q(club__isnull=True) | Q(club_id=club_id),
        Q(end_date__gte=start_date_range) & Q(start_date__lte=end_date_range) 
    ).order_by('start_date')
    
    # Előkészítjük a szünetek listáját és az okokat
    absence_dates = set()
    absence_reasons = {}
    for absence in absences:
        for n in range((absence.end_date - absence.start_date).days + 1):
            d = absence.start_date + timedelta(n)
            if start_date_range <= d <= end_date_range:
                absence_dates.add(d)
                if d not in absence_reasons: 
                     absence_reasons[d] = absence.name
    
    training_days_of_week = [int(d) for d in schedule.days_of_week.split(',') if d]
    
    all_sessions_raw = []
    
    # 3. Napok generálása az időkereten belül (a múlttól a jövőig)
    current_date = start_date_range
    while current_date <= end_date_range:
        
        # Ne menjünk a schedule érvényességi tartományán kívülre
        if current_date < schedule.start_date:
            current_date += timedelta(days=1)
            continue
        if schedule.end_date and current_date > schedule.end_date:
            break

        # A hét napja: Pythonban 0=Hétfő, 6=Vasárnap. A modelben 1=Hétfő, 7=Vasárnap.
        day_of_week_model = current_date.weekday() + 1 

        if day_of_week_model in training_days_of_week:
            session_info = {
                'date': current_date,
                'is_absence': False,
                'absence_reason': None
            }
            
            # Ellenőrzés: Edzésszünet van-e ezen a napon?
            if current_date in absence_dates:
                session_info['is_absence'] = True
                session_info['absence_reason'] = absence_reasons.get(current_date, "Szünet")
            
            all_sessions_raw.append(session_info)
        
        current_date += timedelta(days=1)

    # 4. Filterezés a felhasználói élmény (UX) szerint:
    # Minden múltbéli alkalom + legfeljebb 5 jövőbeli EDZÉS (szünet nem számít bele a limitbe)
    
    final_sessions = []
    future_training_count = 0
    
    for session in all_sessions_raw:
        if session['date'] < today:
            # Minden múltbéli alkalom bekerül
            final_sessions.append(session)
        elif session['date'] >= today:
            # Minden jövőbeli szünet bekerül
            if session['is_absence']:
                final_sessions.append(session)
            # Csak 'future_limit' számú jövőbeli edzés (nem szünet) bekerül
            elif future_training_count < future_limit:
                final_sessions.append(session)
                future_training_count += 1
                
    return final_sessions