# ml_engine/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ml_engine.training_service import TrainingService # A korábban létrehozott szolgáltatás
from ml_engine.models import UserFeatureSnapshot # Az aktuális forma index lekérdezéséhez
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback
from django.db.models import Max
from datetime import date, timedelta

@login_required
def form_prediction_view(request):
    """
    Kiszámítja a sportoló aktuális és várható forma indexét,
    majd megjeleníti azt egy dashboardon.
    """
    user = request.user
    
    # Adatok a sablonhoz
    context = {
        'current_form_index': 'N/A',
        'predicted_form_index': 'Nincs adat',
        'prediction_status': 'A modellt még nem futtattuk vagy nincs elég adat.',
        'today_date': date.today().strftime('%Y-%m-%d')
    }
    
    # ------------------------------------------------------------------
    # 1. Aktuális Forma Index (A tegnap kiszámított TARGET) lekérdezése
    # ------------------------------------------------------------------
    try:
        # Lekérjük a sportoló legutóbbi, mára érvényes feature snapshotját
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        current_form_index = latest_snapshot.features.get('target_form_index')
        
        if current_form_index is not None:
            # Tizedesjegyek kerekítése a szebb megjelenésért
            context['current_form_index'] = f"{current_form_index:.2f}"
            context['prediction_status'] = "Sikeresen lekérdezve az aktuális forma index."
            
    except UserFeatureSnapshot.DoesNotExist:
        context['prediction_status'] = "⚠️ Nincs elérhető aktuális feature snapshot. Kérlek, futtasd a feature generálást."
        
    # ------------------------------------------------------------------
    # 2. Várható Forma Index (A modell predikciója) lekérdezése
    # ------------------------------------------------------------------
    
    # Inicializáljuk a TrainingService-t (betölti a betanított modellt)
    ml_service = TrainingService()
    
    if ml_service.model:
        # Elvégezzük a predikciót
        try:
            # A predikció a holnapi (vagy a következő elérhető nap) forma indexét adja vissza.
            generated_at, predicted_index = ml_service.predict_form(user)
            
            if predicted_index is not None:
                context['predicted_form_index'] = f"{predicted_index:.2f}"
                context['prediction_status'] = "Aktuális és várható forma index sikeresen kiszámítva."
            else:
                 context['prediction_status'] = "❌ A modell betöltése sikerült, de a predikció sikertelen volt (valószínűleg hiányzik a mai feature snapshot)."

        except Exception as e:
            # Hiba esetén (pl. hiányzó oszlop a predikciós DF-ben, ha a modell nem volt mentve jól)
            context['predicted_form_index'] = 'Hiba'
            context['prediction_status'] = f"❌ Hiba történt a predikció futtatása közben: {e}"
            
    else:
        # Ha a modell nem töltődött be (mert még nem volt betanítva)
        context['prediction_status'] = "❌ A gépi tanulási modell még nincs betanítva. Kérlek, futtasd a `train_form_prediction_model` Celery taskot."


    # Megjelenítés
    return render(request, 'ml_engine/form_prediction.html', context)

@login_required
def dashboard_view(request):
    user = request.user
    today = date.today()
    week_ago = today - timedelta(days=14)

    weight_data = WeightData.objects.filter(user=user, workout_date__gte=week_ago).order_by('workout_date')
    hrv_data = HRVandSleepData.objects.filter(user=user, recorded_at__gte=week_ago).order_by('recorded_at')
    feedback_data = WorkoutFeedback.objects.filter(user=user, workout_date__gte=week_ago).order_by('workout_date')

    current_form_index = None
    predicted_form_index = None
    prediction_status = None

    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        current_form_index = latest_snapshot.features.get('target_form_index')
    except UserFeatureSnapshot.DoesNotExist:
        prediction_status = "⚠️ Nincs elérhető formaindex adat."

    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_index = ml_service.predict_form(user)
            predicted_form_index = predicted_index
        except Exception as e:
            prediction_status = f"❌ Predikciós hiba: {e}"
    else:
        prediction_status = "❌ Modell még nincs betanítva."

    chart_data = {
        "dates": [str(w.workout_date) for w in weight_data],
        "weights": [float(w.morning_weight) for w in weight_data],
        "hrv": [float(h.hrv or 0) for h in hrv_data],
        "sleep_quality": [h.sleep_quality or 0 for h in hrv_data],
        "intensity": [f.workout_intensity or 0 for f in feedback_data],
    }

    context = {
        "today": today,
        "current_form_index": f"{current_form_index:.2f}" if current_form_index else "N/A",
        "predicted_form_index": f"{predicted_form_index:.2f}" if predicted_form_index else "N/A",
        "prediction_status": prediction_status or "✅ Sikeres lekérdezés",
        "chart_data": chart_data,
    }

    return render(request, "ml_engine/dashboard.html", context)


@login_required
def upload_data_view(request):
    """Felhasználó edzésadatokat tölt fel (CSV vagy JSON)."""
    if request.method == 'POST' and request.FILES.get('data_file'):
        # Fájlfeltöltés kezelése és mentés
        data_file = request.FILES['data_file']
        # Itt jön majd a feldolgozás logikája
        messages.success(request, f"Sikeres feltöltés: {data_file.name}")
    return render(request, 'ml_engine/upload_data.html')
