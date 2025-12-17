# ml_engine/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ml_engine.training_service import TrainingService
from ml_engine.models import UserFeatureSnapshot
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback
from django.db.models import Max
from datetime import date, timedelta
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
#  Formaindex predikció (külön oldal)
# ------------------------------------------------------------
@login_required
def form_prediction_view(request):
    """
    Kiszámítja a sportoló aktuális és várható formaindexét,
    majd megjeleníti azt egy dashboardon.
    """
    user = request.user

    context = {
        'current_form_index': 'N/A',
        'predicted_form_index': 'Nincs adat',
        'prediction_status': 'A modellt még nem futtattuk vagy nincs elég adat.',
        'today_date': date.today().strftime('%Y-%m-%d'),
    }

    # 1️⃣ Aktuális formaindex lekérése
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        current_form_index = (
            latest_snapshot.features.get('target_form_index')
            or latest_snapshot.features.get('form_score')
        )

        if current_form_index is not None:
            context['current_form_index'] = f"{float(current_form_index):.2f}"
            context['prediction_status'] = "✅ Aktuális formaindex sikeresen lekérdezve."
        else:
            context['prediction_status'] = "⚠️ Snapshot létezik, de nincs benne formaindex adat."

    except UserFeatureSnapshot.DoesNotExist:
        context['prediction_status'] = "⚠️ Nincs elérhető aktuális feature snapshot."

    # 2️⃣ Várható formaindex (modell predikció)
    ml_service = TrainingService()

    if ml_service.model:
        try:
            generated_at, predicted_index = ml_service.predict_form(user)
            if predicted_index is not None:
                context['predicted_form_index'] = f"{predicted_index:.2f}"
                context['prediction_status'] = "✅ Aktuális és várható formaindex sikeresen kiszámítva."
            else:
                context['prediction_status'] = "⚠️ Modell betöltve, de nincs elég adat a predikcióhoz."
        except Exception as e:
            logger.error(f"❌ Predikciós hiba: {e}", exc_info=True)
            context['predicted_form_index'] = 'Hiba'
            context['prediction_status'] = f"❌ Hiba történt a predikció során: {e}"
    else:
        context['prediction_status'] = "⚠️ A modell még nincs betanítva."

    return render(request, 'ml_engine/form_prediction.html', context)


# ------------------------------------------------------------
#  Teljesítmény Dashboard
# ------------------------------------------------------------
@login_required
def dashboard_view(request):
    user = request.user
    today = date.today()
    week_ago = today - timedelta(days=14)

    # --- Adatok lekérése ---
    weight_data = WeightData.objects.filter(user=user, workout_date__gte=week_ago).order_by('workout_date')
    hrv_data = HRVandSleepData.objects.filter(user=user, recorded_at__gte=week_ago).order_by('recorded_at')
    feedback_data = WorkoutFeedback.objects.filter(user=user, workout_date__gte=week_ago).order_by('workout_date')

    current_form_index = None
    predicted_form_index = None
    prediction_status = None
    trend_message = None
    evaluation_text = None
    evaluation_color = "gray"
    injury_risk = None

    # --- Aktuális formaindex ---
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        current_form_index = (
            latest_snapshot.features.get('target_form_index')
            or latest_snapshot.features.get('form_score')
        )
    except UserFeatureSnapshot.DoesNotExist:
        prediction_status = "⚠️ Nincs elérhető formaindex adat."

    # --- Predikció ---
    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_index = ml_service.predict_form(user)
            predicted_form_index = predicted_index
        except Exception as e:
            prediction_status = f"❌ Predikciós hiba: {e}"
    else:
        prediction_status = "⚠️ Modell még nincs betanítva."

    # --- Formaértékelés ---
    if current_form_index is not None:
        ci = float(current_form_index)

        if ci < 20:
            evaluation_text = "Gyenge forma – regeneráció javasolt"
            evaluation_color = "red"
        elif ci < 30:
            evaluation_text = "Közepes forma – javuló tendencia"
            evaluation_color = "orange"
        elif ci < 40:
            evaluation_text = "Jó forma – fenntartó edzések ajánlottak"
            evaluation_color = "green"
        else:
            evaluation_text = "Kiemelkedő forma – teljesítmény csúcson"
            evaluation_color = "blue"

    # --- Trend előrejelzés ---
    if predicted_form_index is not None and current_form_index is not None:
        diff = predicted_form_index - current_form_index
        if diff > 0.5:
            trend_message = f"📈 A várható formaindex {diff:.2f}-tel javul."
        elif diff < -0.5:
            trend_message = f"📉 A várható formaindex {abs(diff):.2f}-tel csökken."
        else:
            trend_message = "➖ A várható formaindex stabil, nem változik jelentősen."
    else:
        trend_message = "❔ Még nem áll rendelkezésre elég adat a trend becsléséhez."

    # --- Intelligens sérüléskockázat ---
    try:
        if len(feedback_data) > 3 and len(hrv_data) > 3:
            df = pd.DataFrame({
                "intensity": [f.workout_intensity or 0 for f in feedback_data],
                "hrv": [float(h.hrv or 0) for h in hrv_data[:len(feedback_data)]],
                "sleep": [float(h.sleep_quality or 0) for h in hrv_data[:len(feedback_data)]],
            })

            # Normalizálás (Z-score)
            df = (df - df.mean()) / df.std(ddof=0)

            # Stressz index
            df["stress_index"] = df["intensity"] - df["hrv"] - df["sleep"]

            # Mozgóátlag és exponenciális súlyozás
            df["smoothed"] = df["stress_index"].ewm(span=5, adjust=False).mean()

            # Skálázás 0–100 közé
            injury_risk = np.interp(df["smoothed"].iloc[-1], [-2, 2], [0, 100])
            injury_risk = float(np.clip(injury_risk, 0, 100))

        else:
            injury_risk = None
    except Exception as e:
        logger.error(f"⚠️ Sérüléskockázat számítási hiba: {e}")
        injury_risk = None

    # --- Chart adatok ---
    chart_data = {
        "dates": [str(w.workout_date) for w in weight_data],
        "weights": [float(w.morning_weight or 0) for w in weight_data],
        "hrv": [float(h.hrv or 0) for h in hrv_data],
        "sleep_quality": [h.sleep_quality or 0 for h in hrv_data],
        "intensity": [f.workout_intensity or 0 for f in feedback_data],
        "injury_risk": [min(100, max(0, (i or 0))) for i in np.linspace(10, injury_risk or 0, len(weight_data))],
    }

    # --- Formaindex trend ---
    snapshots = UserFeatureSnapshot.objects.filter(user=user).order_by("generated_at")
    trend_dates = [s.generated_at.strftime("%Y-%m-%d") for s in snapshots]
    trend_values = [s.features.get("form_score", 0) for s in snapshots]

    if predicted_form_index:
        tomorrow = today + timedelta(days=1)
        trend_dates.append(tomorrow.strftime("%Y-%m-%d"))
        trend_values.append(predicted_form_index)

    chart_data["trend_dates"] = trend_dates
    chart_data["trend_values"] = trend_values

    context = {
        "today": today,
        "current_form_index": f"{current_form_index:.2f}" if current_form_index else "N/A",
        "predicted_form_index": f"{predicted_form_index:.2f}" if predicted_form_index else "N/A",
        "prediction_status": prediction_status or "✅ Sikeres lekérdezés",
        "trend_message": trend_message,
        "evaluation_text": evaluation_text,
        "evaluation_color": evaluation_color,
        "injury_risk": f"{injury_risk:.1f}" if injury_risk is not None else None,
        "chart_data": chart_data,
    }

    return render(request, "ml_engine/dashboard.html", context)