# ml_engine/views.py

import logging
import json
import re
from datetime import date, timedelta
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods,  require_GET

# Modulok és Modellek
from ml_engine.ai_coach_service import DittaCoachService
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

    # Lekérjük a legfrissebb predikciót az adatbázisból (Ezt hiányolta a kód)
    latest_prediction = UserPredictionResult.objects.filter(user=user).order_by("-predicted_at").first()

    context = {
        'current_form_index': 'N/A',
        'predicted_form_index': 'Nincs adat',
        'prediction_status': 'A modellt még nem futtattuk vagy nincs elég adat.',
        'prediction_color': 'secondary',
        'today_date': date.today().strftime('%Y-%m-%d'),
        'latest_prediction': latest_prediction,
    }

    # 1. Aktuális formaindex lekérése a snapshotból
    try:
        latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest('generated_at')
        features = latest_snapshot.features
        # Kezeljük ha lista vagy dict
        if isinstance(features, list) and len(features) > 0:
            features = features[0]
        
        current_val = features.get('form_score') or features.get('target_form_index')

        if current_val is not None:
            context['current_form_index'] = f"{float(current_val):.2f}"
    except UserFeatureSnapshot.DoesNotExist:
        pass

    # 2. Értékelés és Szín beállítása a legfrissebb predikció alapján
    if latest_prediction:
        score = latest_prediction.form_score
        context['predicted_form_index'] = f"{score:.2f}"
        
        if score >= 80:
            status_text = "Kiváló forma! Mehet a maximális terhelés."
            status_color = "success"
        elif score >= 60:
            status_text = "Jó állapotban vagy, stabil fejlődés."
            status_color = "primary"
        elif score >= 40:
            status_text = "Közepes forma. Figyelj a regenerációra!"
            status_color = "warning"
        else:
            status_text = "Fáradtság jelei! Javasolt egy pihenőnap."
            status_color = "danger"
            
        context['prediction_status'] = status_text
        context['prediction_color'] = status_color
    
    return render(request, 'ml_engine/form_prediction.html', context)


# ------------------------------------------------------------
#  Teljesítmény Dashboard
# ------------------------------------------------------------

@login_required
@subscription_required
def dashboard_view(request):
    user = request.user
    today = date.today()
    two_weeks_ago = today - timedelta(days=14)

    active_sub = UserSubscription.objects.filter(
        user=user, sub_type="ML_ACCESS", active=True
    ).first()

    # --- Biometrikus adatok ---
    weight_data = WeightData.objects.filter(
        user=user, workout_date__gte=two_weeks_ago
    ).order_by("workout_date")

    hrv_data = HRVandSleepData.objects.filter(
        user=user, recorded_at__gte=two_weeks_ago
    ).order_by("recorded_at")

    feedback_data = WorkoutFeedback.objects.filter(
        user=user, workout_date__gte=two_weeks_ago
    ).order_by("workout_date")

    # --- Aktuális snapshot ---
    latest_snapshot = (
        UserFeatureSnapshot.objects.filter(user=user)
        .order_by("-generated_at")
        .first()
    )

    ci = 0.0
    injury_risk_index = 0.0

    if latest_snapshot:
        # Ellenőrizzük a features típusát
        if isinstance(latest_snapshot.features, dict):
            ci = float(latest_snapshot.features.get("form_score", 0))
            injury_risk_index = float(
                latest_snapshot.features.get("injury_risk_index", 0)
            )
        elif isinstance(latest_snapshot.features, list):
            # Ha lista, próbáljuk az első elemből kinyerni
            if latest_snapshot.features and len(latest_snapshot.features) > 0:
                if isinstance(latest_snapshot.features[0], dict):
                    ci = float(latest_snapshot.features[0].get("form_score", 0))
                    injury_risk_index = float(
                        latest_snapshot.features[0].get("injury_risk_index", 0)
                    )

    # --- Predikció ---
    predicted_form_index = None
    ml_service = TrainingService()
    if ml_service.model:
        try:
            _, predicted_form_index = ml_service.predict_form(user)
        except Exception as e:
            logger.error(f"ML hiba: {e}")

    # --- Értékelés ---
    if ci < 20:
        evaluation_text, evaluation_color = "Gyenge forma", "#e74c3c"
    elif ci < 30:
        evaluation_text, evaluation_color = "Közepes forma", "#f39c12"
    elif ci < 40:
        evaluation_text, evaluation_color = "Jó forma", "#27ae60"
    else:
        evaluation_text, evaluation_color = "Kiemelkedő forma", "#2980b9"

    # --- Trend ---
    snapshots = (
        UserFeatureSnapshot.objects.filter(user=user)
        .order_by("snapshot_date")[:14]
    )

    trend_dates = []
    trend_values = []

    for s in snapshots:
        trend_dates.append(s.snapshot_date.strftime("%Y-%m-%d"))
        
        # Típusellenőrzés
        val = 0
        if isinstance(s.features, dict):
            val = s.features.get("form_score", 0)
        elif isinstance(s.features, list):
            if s.features and len(s.features) > 0:
                if isinstance(s.features[0], dict):
                    val = s.features[0].get("form_score", 0)
                else:
                    try:
                        val = float(s.features[0])
                    except (ValueError, TypeError):
                        val = 0
        
        trend_values.append(float(val))

    if predicted_form_index is not None:
        trend_dates.append((today + timedelta(days=1)).strftime("%Y-%m-%d"))
        trend_values.append(float(predicted_form_index))

    avg_form = sum(trend_values) / len(trend_values) if trend_values else 0
    best_form = max(trend_values) if trend_values else 0
    worst_form = min(trend_values) if trend_values else 0

    trend_message = "Stagnáló állapot."
    if len(trend_values) > 1:
        if trend_values[-1] > trend_values[-2]:
            trend_message = "📈 <span class='text-success'>Javuló trend</span>"
        elif trend_values[-1] < trend_values[-2]:
            trend_message = "📉 <span class='text-danger'>Romló trend</span>"

    latest_prediction = (
        UserPredictionResult.objects.filter(user=user)
        .order_by("-predicted_at")
        .first()
    )

    chart_data = {
        "dates": [str(w.workout_date) for w in weight_data],
        "weights": [float(w.morning_weight) for w in weight_data],
        "hrv": [float(h.hrv or 0) for h in hrv_data],
        "intensity": [f.workout_intensity or 0 for f in feedback_data],
        "trend_dates": trend_dates,
        "trend_values": trend_values,
        "injury_risk": [injury_risk_index] * len(trend_dates),
    }

    context = {
        "active_sub": active_sub,
        "current_form_index": round(ci, 2),
        "predicted_form_index": round(predicted_form_index, 2)
        if predicted_form_index is not None
        else None,
        "evaluation_text": evaluation_text,
        "evaluation_color": evaluation_color,
        "trend_message": trend_message,
        "avg_form": round(avg_form, 1),
        "best_form": round(best_form, 1),
        "worst_form": round(worst_form, 1),
        "injury_risk": round(injury_risk_index, 1),
        "latest_prediction": latest_prediction,
        "chart_data": chart_data,
    }

    return render(request, "ml_engine/dashboard.html", context)

@login_required
@subscription_required
@require_GET
def dashboard_data_api(request):
    """AJAX adatforrás – 7 / 14 / 30 nap"""

    user = request.user
    days = int(request.GET.get("days", 14))
    today = date.today()
    since = today - timedelta(days=days)

    # Snapshotok
    snapshots = (
        UserFeatureSnapshot.objects
        .filter(user=user, snapshot_date__gte=since)
        .order_by("snapshot_date")
    )

    trend_dates = []
    trend_values = []

    for s in snapshots:
        # Ellenőrizzük, hogy mi a features típusa
        if isinstance(s.features, dict):
            # Ha dictionary
            value = s.features.get("form_score", 0) or s.features.get("avg_hrv", 0) or 0
        elif isinstance(s.features, list):
            # Ha lista, akkor próbáljuk meg az első elemet használni
            if s.features and len(s.features) > 0:
                if isinstance(s.features[0], dict):
                    value = s.features[0].get("form_score", 0) or s.features[0].get("avg_hrv", 0) or 0
                else:
                    # Ha az első elem is nem dict, akkor számként próbáljuk
                    try:
                        value = float(s.features[0])
                    except (ValueError, TypeError):
                        value = 0
            else:
                value = 0
        else:
            # Ha egyéb típus (pl. szám vagy string)
            try:
                value = float(s.features)
            except (ValueError, TypeError):
                value = 0
        
        trend_dates.append(s.snapshot_date.strftime("%Y-%m-%d"))
        trend_values.append(float(value))

    # Predikció
    predicted_value = None
    ml_service = TrainingService()
    
    # Debug
    print(f"DEBUG - ML Service model exists: {ml_service.model is not None}")
    
    if ml_service.model:
        try:
            _, predicted_value = ml_service.predict_form(user)
            print(f"DEBUG - Predicted value: {predicted_value}")
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            print(f"DEBUG - Prediction error: {e}")

    if predicted_value:
        trend_dates.append((today + timedelta(days=1)).strftime("%Y-%m-%d"))
        trend_values.append(float(predicted_value))
        print(f"DEBUG - Added prediction to trend")
    else:
        print(f"DEBUG - No prediction value to add")

    # 1. Injury Risk kinyerése a legfrissebb snapshotból
    latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).order_by("-generated_at").first()
    injury_risk_val = 0
    if latest_snapshot:
        if isinstance(latest_snapshot.features, dict):
            injury_risk_val = latest_snapshot.features.get("injury_risk_index", 0)
        elif isinstance(latest_snapshot.features, list) and len(latest_snapshot.features) > 0:
            injury_risk_val = latest_snapshot.features[0].get("injury_risk_index", 0)

    # 2. Statisztikák (marad a korábbi)
    avg_form = sum(trend_values) / len(trend_values) if trend_values else 0
    best_form = max(trend_values) if trend_values else 0
    worst_form = min(trend_values) if trend_values else 0
    current_form = trend_values[-1] if trend_values else 0

    # 3. Értékelés (marad a korábbi)
    if current_form < 20:
        evaluation_text, evaluation_color = "Gyenge forma", "#e74c3c"
    elif current_form < 30:
        evaluation_text, evaluation_color = "Közepes forma", "#f39c12"
    elif current_form < 40:
        evaluation_text, evaluation_color = "Jó forma", "#27ae60"
    else:
        evaluation_text, evaluation_color = "Kiemelkedő forma", "#2980b9"

    # 4. A válasz összeállítása - HOZZÁADVA AZ injury_risk
    response_data = {
        "current_form_index": round(current_form, 2),
        "predicted_form_index": round(predicted_value, 2) if predicted_value else None,
        "avg_form": round(avg_form, 1),
        "best_form": round(best_form, 1),
        "worst_form": round(worst_form, 1),
        "injury_risk": round(float(injury_risk_val), 1), # EZ HIÁNYZOTT!
        "evaluation_text": evaluation_text,
        "evaluation_color": evaluation_color,
        "trend_dates": trend_dates,
        "trend_values": trend_values,
    }
    
    return JsonResponse(response_data)


ditta_service = DittaCoachService()

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def ditta_chat_api(request):
    try:
        data = json.loads(request.body)
        user_query = data.get('query', '').strip()
        
        if not user_query:
            return JsonResponse({'success': False, 'error': 'Üres kérdés.'}, status=400)
        
        session_key = f'ditta_active_role_{request.user.id}'
        active_role = request.session.get(session_key, None)
        
        logger.info(f"Ditta chat - User: {request.user.username}, Query: {user_query[:50]}, Active role from session: {active_role}")

        print(f"=" * 50)
        print(f"DEBUG - User query: {user_query}")
        print(f"DEBUG - Session key: {session_key}")
        print(f"DEBUG - Active role from session: {active_role}")
        print(f"DEBUG - All session keys: {list(request.session.keys())}")
        print(f"=" * 50)
        
        history = []
        if active_role:
            history.append({'metadata': {'selected_role': active_role}})
            logger.info(f"History built with role: {active_role}")
        
        service = DittaCoachService()
        
        response_text = service.get_ditta_response(
            user=request.user,
            context_app='ml_engine',
            user_query=user_query,
            history=history,
            active_role=active_role
        )

        print(f"DEBUG - Response (first 200 chars): {response_text[:200]}")
        
        # === ÚJ RÉSZ: Ellenőrizzük, hogy sikerült-e szerepkört választani ===
        # 1. Regex alapú keresés (ha benne van a válaszban)
        role_pattern = r'Rendben, \*\*([^*]+)\*\* minőségedben segítek'
        role_match = re.search(role_pattern, response_text)
        
        if role_match:
            new_role = role_match.group(1)
            request.session[session_key] = new_role
            request.session.modified = True
            logger.info(f"[SESSION SAVED] Role from response: {new_role}")
            print(f"[SESSION SAVED] Role saved: {new_role}")
        
        # 2. Ha nincs a válaszban, de sikerült megállapítani a kérdésből
        # (pl. "gyerekkel" -> Szülő), akkor is mentsük el!
        elif not active_role:  # Ha még nincs mentve
            # Próbáljuk meg kitalálni még egyszer
            from users.models import UserRole
            user_roles = UserRole.objects.filter(user=request.user, status='approved')
            
            # Egyszerű kulcsszó alapú detektálás
            query_lower = user_query.lower()
            detected_role = None
            
            if any(kw in query_lower for kw in ['gyerek', 'gyermek', 'fiam', 'lányom']):
                parent_role = user_roles.filter(role__name='Szülő').first()
                if parent_role:
                    detected_role = 'Szülő'
            elif any(kw in query_lower for kw in ['sportoló', 'tanítványaim', 'csapatom']):
                coach_role = user_roles.filter(role__name='Edző').first()
                if coach_role:
                    detected_role = 'Edző'
            
            if detected_role:
                request.session[session_key] = detected_role
                request.session.modified = True
                logger.info(f"[SESSION SAVED] Role inferred from query: {detected_role}")
                print(f"[SESSION SAVED] Role inferred: {detected_role}")
        
        # Szerepkör törlés kezelése
        reset_keywords = ['váltok', 'másik szerepkör', 'új szerep', 'szerepkör váltás']
        if any(keyword in user_query.lower() for keyword in reset_keywords):
            if session_key in request.session:
                del request.session[session_key]
                request.session.modified = True
                logger.info(f"Role reset requested by user")
        
        return JsonResponse({'success': True, 'response': response_text})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({'success': False, 'error': 'Érvénytelen kérés formátum.'}, status=400)
        
    except Exception as e:
        logger.error(f"Ditta chat error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Hiba történt a kommunikációban. Kérlek próbáld újra!'}, status=500)