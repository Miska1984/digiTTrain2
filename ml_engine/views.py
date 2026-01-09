# ml_engine/views.py

import logging
from datetime import date, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

# Modulok és Modellek
from ml_engine.training_service import TrainingService
from ml_engine.models import UserFeatureSnapshot, UserPredictionResult
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback
from billing.models import UserSubscription
from billing.decorators import subscription_required

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
#  Formaindex predikció (külön oldal)
# ------------------------------------------------------------
@login_required
@subscription_required
def form_prediction_view(request):
    """
    Kiszámítja a sportoló aktuális és várható formaindexét.
    Csak aktív ML előfizetéssel érhető el.
    """
    user = request.user

    context = {
        'current_form_index': 'N/A',
        'predicted_form_index': 'Nincs adat',
        'prediction_status': 'A modellt még nem futtattuk vagy nincs elég adat.',
        'today_date': date.today().strftime('%Y-%m-%d'),
    }

    # 1. Aktuális formaindex lekérése a snapshotból
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        current_form_index = (
            latest_snapshot.features.get('target_form_index')
            or latest_snapshot.features.get('form_score')
        )

        if current_form_index is not None:
            context['current_form_index'] = f"{float(current_form_index):.2f}"
            context['prediction_status'] = "✅ Aktuális formaindex sikeresen lekérdezve."
    except UserFeatureSnapshot.DoesNotExist:
        context['prediction_status'] = "⚠️ Nincs elérhető aktuális adat (snapshot)."

    # 2. Várható formaindex (ML modell predikció)
    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_index = ml_service.predict_form(user)
            if predicted_index is not None:
                context['predicted_form_index'] = f"{predicted_index:.2f}"
                context['prediction_status'] = "✅ Adatok sikeresen kiszámítva."
        except Exception as e:
            logger.error(f"❌ Predikciós hiba: {e}", exc_info=True)
            context['predicted_form_index'] = 'Hiba'
            context['prediction_status'] = f"❌ Hiba történt: {e}"
    
    return render(request, 'ml_engine/form_prediction.html', context)


# ------------------------------------------------------------
#  Teljesítmény Dashboard
# ------------------------------------------------------------

@login_required
@subscription_required
def dashboard_view(request):
    """
    Prémium (előfizetéses) ML dashboard:
    - Aktuális és várható formaindex statisztikákkal
    - Sérüléskockázat elemzés
    - Biometrikus trendek és interaktív grafikonok
    """
    user = request.user
    today = date.today()
    two_weeks_ago = today - timedelta(days=14)

    # Előfizetés adatainak lekérése
    active_sub = UserSubscription.objects.filter(
        user=user, 
        sub_type='ML_ACCESS', 
        expiry_date__gt=timezone.now()
    ).first()

    # Nyers biometrikus adatok a trendekhez
    weight_data = WeightData.objects.filter(user=user, workout_date__gte=two_weeks_ago).order_by("workout_date")
    hrv_data = HRVandSleepData.objects.filter(user=user, recorded_at__gte=two_weeks_ago).order_by("recorded_at")
    feedback_data = WorkoutFeedback.objects.filter(user=user, workout_date__gte=two_weeks_ago).order_by("workout_date")

    current_form_index = None
    predicted_form_index = None
    injury_risk_index = None
    prediction_status = "✅ Adatok betöltve a központi agyból."
    evaluation_text, evaluation_color = "Nincs adat", "gray"

    # --- Adatok kinyerése a Snapshotból ---
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).order_by("-snapshot_date").first()
        if latest_snapshot:
            f = latest_snapshot.features
            
            if isinstance(f, dict):
                current_form_index = f.get("form_score") or f.get("avg_hrv") or 0
                injury_risk_index = f.get("injury_risk_index") or f.get("dehydration_index") or 0
            elif isinstance(f, list):
                current_form_index = f[0] if len(f) > 0 else 0
                injury_risk_index = 0
            else:
                current_form_index = 0
                injury_risk_index = 0
        else:
            current_form_index = 0
            injury_risk_index = 0
            
    except Exception as e:
        logger.warning(f"⚠️ Snapshot hiba: {e}")
        current_form_index = 0

    # --- Predikció futtatása a holnapi napra ---
    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_form_index = ml_service.predict_form(user)
        except Exception as e:
            logger.error(f"❌ ML hiba: {e}")
            prediction_status = "❌ A jövőbelátó áramkörök meghibásodtak (Predikciós hiba)."

    # --- Értékelés és színek ---
    # Biztonsági átalakítás számmá
    try:
        if isinstance(current_form_index, dict):
            ci = float(current_form_index.get("form_score", 0))
        else:
            ci = float(current_form_index or 0)
    except (TypeError, ValueError):
        ci = 0.0

    # Szöveges értékelés a kiszámolt 'ci' alapján
    if ci < 20: 
        evaluation_text, evaluation_color = "Gyenge forma - Regeneráció kötelező!", "#e74c3c"
    elif ci < 30: 
        evaluation_text, evaluation_color = "Közepes forma - Csak óvatosan!", "#f39c12"
    elif ci < 40: 
        evaluation_text, evaluation_color = "Jó forma - Mehet az edzés!", "#27ae60"
    else: 
        evaluation_text, evaluation_color = "Kiemelkedő forma - Ma döntsd meg a csúcsot!", "#2980b9"

    # --- Chart.js adatok összeállítása ---
    snapshots = UserFeatureSnapshot.objects.filter(user=user).order_by("snapshot_date")[:14]
    trend_dates = [s.snapshot_date.strftime("%Y-%m-%d") for s in snapshots]
    trend_values = []

    for s in snapshots:
        f = s.features
        # Biztonságos kinyerés: ha dict, keressük a kulcsot, ha nem találjuk, 0
        if isinstance(f, dict):
            val = f.get("form_score") or f.get("avg_hrv") or 0
        else:
            val = 0
        trend_values.append(float(val))

    # Ha van jóslat, adjuk hozzá a grafikon végéhez
    if predicted_form_index:
        tomorrow = today + timedelta(days=1)
        trend_dates.append(tomorrow.strftime("%Y-%m-%d"))
        trend_values.append(float(predicted_form_index))

    # Statisztikák
    avg_form = sum(trend_values) / len(trend_values) if trend_values else 0
    best_form = max(trend_values) if trend_values else 0
    worst_form = min(trend_values) if trend_values else 0

    # Trend üzenet
    trend_message = "Stagnáló állapot."
    if len(trend_values) > 1:
        if trend_values[-1] > trend_values[-2]:
            trend_message = "📈 <span class='text-success'>Felfelé ívelő teljesítmény!</span>"
        elif trend_values[-1] < trend_values[-2]:
            trend_message = "📉 <span class='text-danger'>Vigyázz, fáradsz! Pihenj többet.</span>"
    
    # --- AI Coach tanács lekérése a legutóbbi predikcióból ---
    latest_prediction = UserPredictionResult.objects.filter(user=user).order_by("-predicted_at").first()

    chart_data = {
        "dates": [str(w.workout_date) for w in weight_data],
        "weights": [float(w.morning_weight) for w in weight_data],
        "hrv": [float(h.hrv or 0) for h in hrv_data],
        "sleep_quality": [h.sleep_quality or 0 for h in hrv_data],
        "intensity": [f.workout_intensity or 0 for f in feedback_data],
        "trend_dates": trend_dates,
        "trend_values": trend_values,
        "injury_risk": [float(injury_risk_index or 0)] * len(trend_dates)
    }

    context = {
        "active_sub": active_sub,
        "latest_prediction": latest_prediction,
        "current_form_index": f"{ci:.2f}" if ci is not None else "N/A",
        "predicted_form_index": f"{predicted_form_index:.2f}" if (predicted_form_index is not None and isinstance(predicted_form_index, (int, float))) else "N/A",
        "injury_risk": f"{injury_risk_index:.1f}" if injury_risk_index is not None else None,
        "prediction_status": prediction_status,
        "evaluation_text": evaluation_text,
        "evaluation_color": evaluation_color,
        "trend_message": trend_message,
        "avg_form": f"{avg_form:.1f}",
        "best_form": f"{best_form:.1f}",
        "worst_form": f"{worst_form:.1f}",
        "chart_data": chart_data,
    }

    return render(request, "ml_engine/dashboard.html", context)