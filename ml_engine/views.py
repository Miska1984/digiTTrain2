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
    """
    Fő dashboard nézet, amely:
      - megjeleníti az aktuális és várható formaindexet,
      - értékeli az edzettségi szintet,
      - megjeleníti a biometrikus trendeket és formaindex-grafikont.
    """
    user = request.user
    today = date.today()
    week_ago = today - timedelta(days=14)

    # Alap adatok lekérése (2 hét)
    weight_data = WeightData.objects.filter(user=user, workout_date__gte=week_ago).order_by('workout_date')
    hrv_data = HRVandSleepData.objects.filter(user=user, recorded_at__gte=week_ago).order_by('recorded_at')
    feedback_data = WorkoutFeedback.objects.filter(user=user, workout_date__gte=week_ago).order_by('workout_date')

    current_form_index = None
    predicted_form_index = None
    prediction_status = None
    trend_message = None
    evaluation_text = None
    evaluation_color = "gray"

    # --- 1️⃣ Aktuális formaindex ---
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        current_form_index = (
            latest_snapshot.features.get('target_form_index')
            or latest_snapshot.features.get('form_score')
        )
    except UserFeatureSnapshot.DoesNotExist:
        prediction_status = "⚠️ Nincs elérhető formaindex adat."

    # --- 2️⃣ Predikció ---
    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_index = ml_service.predict_form(user)
            predicted_form_index = predicted_index
        except Exception as e:
            prediction_status = f"❌ Predikciós hiba: {e}"
            logger.error(f"❌ Predikciós hiba: {e}", exc_info=True)
    else:
        prediction_status = "⚠️ Modell még nincs betanítva."

    # --- 3️⃣ Formaértékelés (aktuális forma) ---
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

    # --- 4️⃣ Trend előrejelzés (aktuális vs. várható forma) ---
    if predicted_form_index is not None and current_form_index is not None:
        diff = predicted_form_index - current_form_index
        if diff > 0.5:
            trend_message = f"<span class='text-success'>📈 A várható formaindex {diff:.2f}-tel javul.</span>"
        elif diff < -0.5:
            trend_message = f"<span class='text-danger'>📉 A várható formaindex {abs(diff):.2f}-tel csökken.</span>"
        else:
            trend_message = "<span class='text-secondary'>➖ A várható formaindex stabil, nem változik jelentősen.</span>"
    else:
        trend_message = "<span class='text-muted'>❔ Még nem áll rendelkezésre elég adat a trend becsléséhez.</span>"

    # --- 5️⃣ Chart adatok előkészítése ---
    chart_data = {
        "dates": [str(w.workout_date) for w in weight_data],
        "weights": [float(w.morning_weight) for w in weight_data],
        "hrv": [float(h.hrv or 0) for h in hrv_data],
        "sleep_quality": [h.sleep_quality or 0 for h in hrv_data],
        "intensity": [f.workout_intensity or 0 for f in feedback_data],
    }

    # --- 6️⃣ Formaindex trend grafikon adatok ---
    snapshots = UserFeatureSnapshot.objects.filter(user=user).order_by("generated_at")
    trend_dates = [s.generated_at.strftime("%Y-%m-%d") for s in snapshots]
    trend_values = [s.features.get("form_score", 0) for s in snapshots]

    # Ha van predikció → hozzáadjuk a holnapot
    if predicted_form_index is not None:
        tomorrow = today + timedelta(days=1)
        trend_dates.append(tomorrow.strftime("%Y-%m-%d"))
        trend_values.append(predicted_form_index)

    chart_data["trend_dates"] = trend_dates
    chart_data["trend_values"] = trend_values

    # --- 7️⃣ Összesített statisztika a formaindexekről ---
    if trend_values:
        avg_form = sum(trend_values) / len(trend_values)
        best_form = max(trend_values)
        worst_form = min(trend_values)
    else:
        avg_form = best_form = worst_form = 0

    # --- 8️⃣ Kontextus rendereléshez ---
    context = {
        "today": today,
        "current_form_index": f"{current_form_index:.2f}" if current_form_index else "N/A",
        "predicted_form_index": f"{predicted_form_index:.2f}" if predicted_form_index else "N/A",
        "prediction_status": prediction_status or "✅ Sikeres lekérdezés",
        "trend_message": trend_message,
        "evaluation_text": evaluation_text,
        "evaluation_color": evaluation_color,
        "chart_data": chart_data,
        "avg_form": f"{avg_form:.2f}",
        "best_form": f"{best_form:.2f}",
        "worst_form": f"{worst_form:.2f}",
    }

    return render(request, "ml_engine/dashboard.html", context)
