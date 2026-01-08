from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

def setup_ml_tasks():
    """
    Létrehozza az adatbázis alapú ütemezéseket az ML engine-hez.
    Ezek után az Admin felületen a 'Periodic Tasks' alatt láthatóak és módosíthatóak lesznek.
    """

    # 1️⃣ Napi Feature generálás (02:00)
    schedule_0200, _ = CrontabSchedule.objects.get_or_create(
        hour=2, 
        minute=0,
        timezone='Europe/Budapest' # Érdemes fixálni az időzónát
    )
    
    PeriodicTask.objects.update_or_create(
        name="ML Engine - 1. Feature snapshotok generálása",
        defaults={
            "task": "ml_engine.tasks.generate_user_features",
            "crontab": schedule_0200,
            "enabled": True,
            "description": "Minden felhasználó adatából napi jellemzőket készít a tanításhoz.",
        }
    )

    # 2️⃣ Modell tréning (02:30)
    schedule_0230, _ = CrontabSchedule.objects.get_or_create(
        hour=2, 
        minute=30,
        timezone='Europe/Budapest'
    )
    
    PeriodicTask.objects.update_or_create(
        name="ML Engine - 2. Hibrid modell újratanítása",
        defaults={
            "task": "ml_engine.tasks.train_form_prediction_model",
            "crontab": schedule_0230,
            "enabled": True,
            "description": "Valódi és 10.000 szintetikus adat alapján frissíti a modellt.",
        }
    )

    # 3️⃣ Predikció aktív előfizetőknek (03:00)
    schedule_0300, _ = CrontabSchedule.objects.get_or_create(
        hour=3, 
        minute=0,
        timezone='Europe/Budapest'
    )
    
    PeriodicTask.objects.update_or_create(
        name="ML Engine - 3. Formaindex jóslás előfizetőknek",
        defaults={
            "task": "ml_engine.tasks.predict_form_for_active_subscribers",
            "crontab": schedule_0300,
            "enabled": True,
            "description": "Kiszámolja a napi formaindexet azoknak, akiknek van előfizetésük.",
        }
    )

    print("✅ ML engine ütemezett taskok regisztrálva az adatbázisba.")