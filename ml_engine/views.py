# ml_engine/views.py

import logging
from datetime import date, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

# Modulok és Modellek
from ml_engine.training_service import TrainingService
from ml_engine.models import UserFeatureSnapshot
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
    - Aktuális és várható formaindex
    - Sérüléskockázat előrejelzés
    - Biometrikus trendek
    A @subscription_required dekorátor védi az illetéktelenektől.
    """
    user = request.user
    today = date.today()
    two_weeks_ago = today - timedelta(days=14)

    # Előfizetés lekérése a sablonban való megjelenítéshez (pl. lejárati dátum)
    active_sub = UserSubscription.objects.filter(
        user=user, 
        sub_type='ML_ACCESS', 
        expiry_date__gt=timezone.now()
    ).first()

    # Biometrikus adatok gyűjtése a grafikonokhoz
    weight_data = WeightData.objects.filter(user=user, workout_date__gte=two_weeks_ago).order_by("workout_date")
    hrv_data = HRVandSleepData.objects.filter(user=user, recorded_at__gte=two_weeks_ago).order_by("recorded_at")
    feedback_data = WorkoutFeedback.objects.filter(user=user, workout_date__gte=two_weeks_ago).order_by("workout_date")

    current_form_index = None
    predicted_form_index = None
    injury_risk_index = None
    prediction_status = "✅ Adatok betöltve"
    evaluation_text = None
    evaluation_color = "gray"

    # --- Adatok kinyerése a Snapshotból ---
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).order_by("-generated_at").first()
        if latest_snapshot:
            current_form_index = latest_snapshot.features.get("target_form_index") or latest_snapshot.features.get("form_score")
            injury_risk_index = latest_snapshot.features.get("injury_risk_index")
    except Exception as e:
        logger.warning(f"Snapshot hiba: {e}")
        prediction_status = "⚠️ Nincs formaindex adat."

    # --- Predikció futtatása ---
    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_form_index = ml_service.predict_form(user)
        except Exception as e:
            logger.error(f"ML hiba: {e}")
            prediction_status = "❌ Predikciós hiba történt."

    # --- Formaindex értékelés szövegezése ---
    if current_form_index is not None:
        ci = float(current_form_index)
        if ci < 20: evaluation_text, evaluation_color = "Gyenge forma", "red"
        elif ci < 30: evaluation_text, evaluation_color = "Közepes forma", "orange"
        elif ci < 40: evaluation_text, evaluation_color = "Jó forma", "green"
        else: evaluation_text, evaluation_color = "Kiemelkedő forma", "blue"

    # --- Chart.js adatok előkészítése ---
    chart_data = {
        "dates": [str(w.workout_date) for w in weight_data],
        "weights": [float(w.morning_weight) for w in weight_data],
        "hrv": [float(h.hrv or 0) for h in hrv_data],
        "sleep_quality": [h.sleep_quality or 0 for h in hrv_data],
        "intensity": [f.workout_intensity or 0 for f in feedback_data],
    }

    # Trend görbe (Snapshotok alapján)
    snapshots = UserFeatureSnapshot.objects.filter(user=user).order_by("generated_at")
    chart_data["trend_dates"] = [s.generated_at.strftime("%Y-%m-%d") for s in snapshots]
    chart_data["trend_values"] = [s.features.get("form_score", 0) for s in snapshots]

    if predicted_form_index:
        chart_data["trend_dates"].append((today + timedelta(days=1)).strftime("%Y-%m-%d"))
        chart_data["trend_values"].append(predicted_form_index)

    context = {
        "has_subscription": True,
        "active_sub": active_sub,
        "today": today,
        "current_form_index": f"{current_form_index:.2f}" if current_form_index else "N/A",
        "predicted_form_index": f"{predicted_form_index:.2f}" if predicted_form_index else "N/A",
        "injury_risk_index": f"{injury_risk_index:.2f}" if injury_risk_index else "N/A",
        "prediction_status": prediction_status,
        "evaluation_text": evaluation_text,
        "evaluation_color": evaluation_color,
        "chart_data": chart_data,
    }

    return render(request, "ml_engine/dashboard.html", context)