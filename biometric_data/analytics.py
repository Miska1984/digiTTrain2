# biometric_data/analytics.py

from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Avg, Max, Min 

# --------------------------------------------------------------------------------------
# SEGÉDFÜGGVÉNYEK A LOGIKÁHOZ
# --------------------------------------------------------------------------------------

# A. Súly visszajelzés
def generate_weight_feedback(weight_data_queryset):
    """Elemzi a testsúly adatokat és szöveges visszajelzést generál."""
    
    # 0. Előzetes ellenőrzés
    if not weight_data_queryset.exists():
        return "<p class='alert alert-info'>Nincsenek testsúlyadatok rögzítve. Kérlek, rögzítsd az első mérést a pontos elemzéshez!</p>"

    latest_entry = weight_data_queryset.first()
    latest_weight = latest_entry.morning_weight
    
    feedback = []
    feedback.append(f"<p><strong>Legfrissebb Reggeli Súly:</strong> <strong>{latest_weight} kg</strong> ({latest_entry.workout_date})</p>")

    # 1. Testsúly Trend Elemzés (7 napos átlag)
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=7)
    fourteen_days_ago = today - timedelta(days=14)

    last_week_data = weight_data_queryset.filter(workout_date__gte=seven_days_ago)
    prev_week_data = weight_data_queryset.filter(workout_date__range=[fourteen_days_ago, seven_days_ago - timedelta(days=1)])

    if last_week_data.exists() and prev_week_data.exists():
        last_week_avg = last_week_data.aggregate(Avg('morning_weight'))['morning_weight__avg']
        prev_week_avg = prev_week_data.aggregate(Avg('morning_weight'))['morning_weight__avg']
        
        change = round((last_week_avg - prev_week_avg) if last_week_avg and prev_week_avg else 0, 2)
        
        if change > 0.3:
            trend_text = "Emelkedő trendet"
            trend_dir = "nőttél"
            trend_class = "alert-warning"
        elif change < -0.3:
            trend_text = "Csökkenő trendet"
            trend_dir = "fogytál"
            trend_class = "alert-success"
        else:
            trend_text = "Stabil testsúlyt"
            trend_dir = "stabil"
            trend_class = "alert-info"
            
        feedback.append(
            f"<p class='mt-2 {trend_class} p-2 rounded'><strong>7 napos Trend:</strong> {trend_text} jeleznek az adatok. Átlagosan **{abs(change)} kg-ot** {(trend_dir)} az előző 7 naphoz képest. Ez a változás **megfontolt figyelmet** igényel.</p>"
        )

    # 2. Testösszetétel (legfrissebb)
    latest_bf = latest_entry.body_fat_percentage
    latest_muscle = latest_entry.muscle_percentage
    
    if latest_bf and latest_muscle:
        feedback.append(
            f"<p><strong>Testösszetétel:</strong> Testzsír: **{latest_bf}%**, Izomtömeg: **{latest_muscle}%**.</p>"
        )

    # 3. Folyadékveszteség (nettó súlyveszteség edzés után)
    if latest_entry.pre_workout_weight and latest_entry.post_workout_weight:
        fluid_loss_gross = latest_entry.pre_workout_weight - latest_entry.post_workout_weight
        fluid_intake = latest_entry.fluid_intake if latest_entry.fluid_intake else 0
        net_loss = round(fluid_loss_gross - fluid_intake, 2)
        
        if net_loss > 1.5:
            loss_class = "alert-danger"
            loss_message = "Kritikus folyadékveszteség! Ez a teljesítményt és a regenerációt drámaian rontja. Fókuszálj a rehidratációra!"
        elif net_loss > 0.5:
            loss_class = "alert-warning"
            loss_message = "Mérsékelt folyadékveszteség észlelhető. Ügyelj a hatékony rehidratációra!"
        else:
            loss_class = "alert-success"
            loss_message = "A folyadékháztartás stabil, a hidratációs protokollod jól működik."
            
        feedback.append(
            f"<p class='mt-2 {loss_class} p-2 rounded'><strong>Edzés Folyadékveszteség (Nettó):</strong> **{net_loss} kg** volt. {loss_message}</p>"
        )

    return " ".join(feedback)

# B. Marokerő/Testösszetétel időzítési visszajelzés
def generate_timing_feedback(last_weight, last_feedback):
    """
    Kiszámítja az utolsó testösszetétel vagy marokerő mérés dátumát,
    és visszajelzést ad a következő mérés ideális időpontjáról (14 napos ciklus).
    """
    today = date.today()
    latest_date = None
    
    # 1. Testsúly adat (body_fat_percentage)
    # Csak akkor vesszük figyelembe, ha van testzsír adat (ez az eseti mérés)
    if last_weight and last_weight.body_fat_percentage:
        latest_date = last_weight.workout_date
    
    # 2. Visszajelzés adat (marokerő)
    if last_feedback and (last_feedback.right_grip_strength or last_feedback.left_grip_strength):
        # Ha a feedback későbbi dátumú, mint a súlyadat (vagy nincs súlyadat), akkor azt tekintjük utolsó mérésnek
        if latest_date is None or last_feedback.workout_date > latest_date:
            latest_date = last_feedback.workout_date

    # 3. Visszajelzés generálása
    if latest_date:
        days_since = (today - latest_date).days
        days_until_target = 14 - days_since
        
        if days_since < 14:
            feedback_class = "text-success"
            message = f"Utolsó mérés: {days_since} napja. Kérlek, végezz új mérést **{days_until_target} nap múlva** (ideális esetben)!"
        else:
            feedback_class = "text-danger"
            message = f"Utolsó mérés: {days_since} napja. A 14 napos mérési ciklus lejárt! Kérlek, mielőbb rögzítsd az adataidat."
            
        return f"""
            <span class="fw-bold {feedback_class}">{message}</span>
        """
    
    return "Nincs rögzített **testösszetétel** vagy **marokerő** adat. Kérlek, végezz el egy mérést a visszajelzéshez."

# C. HRV és Alvás visszajelzés (PLACEHOLDER - EZT KELL MAJD BŐVÍTENÜNK)
def generate_hrv_sleep_feedback(data_queryset):
    """Elemzi a HRV és Alvás adatokat, és összehasonlítja a legfrissebb adatot a 7 napos átlaggal."""

    # 0. Előzetes ellenőrzés
    if not data_queryset.exists():
        return "<p class='alert alert-info'>Nincsenek rögzített **HRV** vagy **alvás** adatok. Kérlek, rögzíts adatot a visszajelzéshez!</p>"

    latest_entry = data_queryset.first()
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=7)

    # 1. 7 napos átlagok számítása
    # A hibaüzenet szerint a mezők: hrv, sleep_quality, alertness
    recent_data = data_queryset.filter(recorded_at__gte=seven_days_ago, hrv__isnull=False)

    if not recent_data.exists():
        return "<p class='alert alert-warning'>A legfrissebb adat rögzítve, de nincs elegendő (7 napos) HRV adat a trendszámításhoz.</p>"

    # CSAK A LÉTEZŐ MEZŐKET aggregate-eljük: hrv, sleep_quality, alertness
    averages = recent_data.aggregate(
        avg_hrv=Avg('hrv'),
        avg_sleep_quality=Avg('sleep_quality'),
        avg_alertness=Avg('alertness')
    )
    
    # 2. Összehasonlítás a legfrissebb adattal
    latest_hrv = latest_entry.hrv
    latest_sleep_quality = latest_entry.sleep_quality
    latest_alertness = latest_entry.alertness

    feedback = []

    # HRV Elemzés
    if latest_hrv and averages['avg_hrv']:
        avg_hrv = round(averages['avg_hrv'], 1)
        hrv_change = latest_hrv - avg_hrv
        
        if hrv_change > 5:
            hrv_message = "Kiváló HRV! Magas szintű **regenerációt** jelez. Készülj egy kemény edzésre. 💪"
            hrv_class = "alert-success"
        elif hrv_change > -5:
            hrv_message = "Stabil HRV. A regenerációd a szokásos szinten van. 🆗"
            hrv_class = "alert-info"
        else:
            hrv_message = "Alacsonyabb a HRV a 7 napos átlagnál! Enyhe **fáradtságot** vagy stresszt jelez. Fontold meg a tervezett edzés intenzitásának csökkentését. ⚠️"
            hrv_class = "alert-warning"
        
        feedback.append(f"<p class='mt-2 {hrv_class} p-2 rounded'><strong>HRV: {latest_hrv} (7 napos átlag: {avg_hrv})</strong>. {hrv_message}</p>")

    # Nyugalmi pulzus (Resting HR) Elemzés - ELTÁVOLÍTVA a mező hiánya miatt.
    # A HRV érték általában már magában hordozza a pulzusváltozás információját.

    # Alvás Minőség és Éberség Elemzés (Egyszerűsített)
    # Csak akkor fut le, ha mindkét mező rendelkezésre áll
    if latest_sleep_quality and averages['avg_sleep_quality'] and latest_alertness and averages['avg_alertness']:
        avg_sleep = round(averages['avg_sleep_quality'], 1)
        avg_alert = round(averages['avg_alertness'], 1)

        if latest_sleep_quality >= 8 and latest_alertness >= 8:
            combined_message = "Kiemelkedő alvás és éberség! A tested készen áll a maximális terhelésre. 🚀"
            combined_class = "alert-success"
        elif latest_sleep_quality < 5 or latest_alertness < 5:
            combined_message = "Gyenge alvásminőség és/vagy éberség. Csökkenteni kell a stresszt/terhelést a kiégés elkerülése érdekében. 🛑"
            combined_class = "alert-danger"
        else:
            combined_message = f"Az alvás és éberség a 7 napos átlag körül mozog (Alvás átlag: {avg_sleep}, Éberség átlag: {avg_alert})."
            combined_class = "alert-info"

        feedback.append(f"<p class='mt-2 {combined_class} p-2 rounded'><strong>Összefoglaló:</strong> {combined_message}</p>")


    return " ".join(feedback)

# D. Futóteljesítmény visszajelzés (PLACEHOLDER)
def generate_running_feedback(data_queryset):
    """
    Elemzi a futóteljesítmény adatokat (tempó és pulzus), 
    és összehasonlítja a legfrissebb futást az utolsó 5 futás átlagával.
    """
    
    # 0. Előzetes ellenőrzés
    if not data_queryset.exists():
        return "<p class='alert alert-info'>Nincsenek rögzített **futóteljesítmény** adatok. Kérlek, rögzítsd az első futásod!</p>"

    latest_run = data_queryset.first()
    
    # Csak az utolsó 5 futást vesszük alapul az összehasonlításhoz
    recent_runs = data_queryset[:5]

    # Szükséges mezők ellenőrzése
    if not (latest_run.run_distance_km and latest_run.run_duration):
        return "<p class='alert alert-warning'>A legfrissebb futás (vagy az utolsó 5 futás) nem tartalmazza a **távolság** és **időtartam** adatot a tempó számításához.</p>"

    # 1. Segédfüggvény: Tempó (pace) számítása mp/km-ben
    def calculate_pace_seconds(distance_km, duration):
        if not distance_km or not duration:
            return None
        # duration (DurationField) másodperceit osztjuk a távolsággal
        total_seconds = duration.total_seconds()
        pace_seconds = total_seconds / float(distance_km)
        return pace_seconds

    # 2. Tempó Elemzés
    
    # Tempó másodperc/km-ben minden futáshoz
    pace_seconds_list = [calculate_pace_seconds(run.run_distance_km, run.run_duration) for run in recent_runs if run.run_distance_km and run.run_duration]
    
    if not pace_seconds_list:
        return "<p class='alert alert-warning'>Nincs elegendő adat (távolság vagy időtartam hiányzik) a tempó trend elemzéséhez.</p>"

    latest_pace_seconds = calculate_pace_seconds(latest_run.run_distance_km, latest_run.run_duration)
    
    # Átlagos tempó (az utolsó 5 futás átlaga)
    avg_pace_seconds = sum(pace_seconds_list) / len(pace_seconds_list)
    
    # Változás (pozitív = lassulás, negatív = gyorsulás)
    pace_change = latest_pace_seconds - avg_pace_seconds
    
    # Tempó másodperceinek átalakítása "perc:másodperc/km" formátumra
    def format_pace(pace_seconds):
        minutes = int(pace_seconds // 60)
        seconds = int(pace_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}/km"
    
    latest_pace_formatted = format_pace(latest_pace_seconds)
    avg_pace_formatted = format_pace(avg_pace_seconds)
    
    # Visszajelzés generálása
    feedback = []
    
    if pace_change < -5:  # Gyorsulás > 5 másodperc/km
        pace_message = "Kiemelkedő futás! A tempód jelentősen **gyorsabb** az utolsó 5 futás átlagánál. Nagyszerű forma! 🚀"
        pace_class = "alert-success"
    elif pace_change > 5: # Lassulás > 5 másodperc/km
        pace_message = "Lassulás észlelhető. A tempód **lassúbb** lett. A fáradtság vagy a nagyobb táv/pulzus lehet az oka. ⚠️"
        pace_class = "alert-warning"
    else:
        pace_message = "Stabil teljesítmény. A tempód az átlagos szinten van. 🆗"
        pace_class = "alert-info"
        
    feedback.append(
        f"<p class='mt-2 {pace_class} p-2 rounded'><strong>Legfrissebb Tempó: {latest_pace_formatted}</strong> (átlag: {avg_pace_formatted}). {pace_message}</p>"
    )

    # 3. Pulzus Elemzés (Átlagos Pulzus)
    
    # Csak azokat a futásokat vesszük, ahol van átlagos pulzus
    recent_hr_data = [run.run_avg_hr for run in recent_runs if run.run_avg_hr is not None]

    if latest_run.run_avg_hr and recent_hr_data:
        latest_avg_hr = latest_run.run_avg_hr
        avg_hr_runs = sum(recent_hr_data) / len(recent_hr_data)
        
        hr_change = latest_avg_hr - avg_hr_runs
        
        if hr_change > 5:
            hr_message = "Magasabb átlagos pulzus! Ez nagyobb **megterhelést** vagy intenzitást jelentett a megszokotthoz képest. Ügyelj a regenerációra. 🔴"
            hr_class = "alert-warning"
        elif hr_change < -5:
            hr_message = "Alacsonyabb átlagos pulzus. Ez a futás viszonylag **könnyebb** volt számodra. Kiváló aerob fejlődés jele is lehet. 🟢"
            hr_class = "alert-success"
        else:
            hr_message = "Stabil pulzusszint. A terhelés a szokásos volt. 🆗"
            hr_class = "alert-info"
            
        feedback.append(
            f"<p class='mt-2 {hr_class} p-2 rounded'><strong>Legfrissebb Átlagos Pulzus: {latest_avg_hr} bpm</strong> (átlag: {round(avg_hr_runs)} bpm). {hr_message}</p>"
        )
        
    return " ".join(feedback)