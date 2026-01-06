# ml_engine/schedules.py
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
import json

def setup_ml_tasks():
    """
    Létrehozza (ha még nem léteznek) az ML engine automatikus ütemezéseit.
    Ezek az ütemezések az adminból is szerkeszthetők.
    """

    # 1️⃣ Napi Feature generálás (02:00)
    schedule_1, _ = CrontabSchedule.objects.get_or_create(hour=2, minute=0)
    PeriodicTask.objects.get_or_create(
        name="ML Engine - Feature generálás minden userre",
        task="ml_engine.tasks.generate_user_features",
        crontab=schedule_1,
        defaults={"enabled": True, "description": "Napi feature snapshot generálás minden felhasználónak."}
    )

    # 2️⃣ Modell tréning (02:30)
    schedule_2, _ = CrontabSchedule.objects.get_or_create(hour=2, minute=30)
    PeriodicTask.objects.get_or_create(
        name="ML Engine - Modell tréning (formaindex)",
        task="ml_engine.tasks.train_form_prediction_model",
        crontab=schedule_2,
        defaults={"enabled": True, "description": "Formaindex modell újratanítása napi adatok alapján."}
    )

    # 3️⃣ Predikció aktív előfizetőkre (03:00)
    schedule_3, _ = CrontabSchedule.objects.get_or_create(hour=3, minute=0)
    PeriodicTask.objects.get_or_create(
        name="ML Engine - Predikció aktív előfizetőkre",
        task="ml_engine.tasks.predict_form_for_active_subscribers",
        crontab=schedule_3,
        defaults={"enabled": True, "description": "Csak aktív ML előfizetők napi predikciója."}
    )

    print("✅ ML engine ütemezett taskok regisztrálva.")
