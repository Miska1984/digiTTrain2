# ml_engine/schedules.py
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

def setup_ml_tasks():
    # Napi feature generálás – 02:00
    schedule_1, _ = CrontabSchedule.objects.get_or_create(hour=2, minute=0)
    PeriodicTask.objects.get_or_create(
        crontab=schedule_1,
        name="Generate daily user features",
        task="ml_engine.tasks.generate_user_features",
    )

    # Modell tréning – 02:30
    schedule_2, _ = CrontabSchedule.objects.get_or_create(hour=2, minute=30)
    PeriodicTask.objects.get_or_create(
        crontab=schedule_2,
        name="Train daily form prediction model",
        task="ml_engine.tasks.train_form_prediction_model",
    )
