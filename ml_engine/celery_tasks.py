from celery.schedules import crontab
# A Celery példányt a fő appból importáljuk
from digiTTrain.celery import app as celery_app

# === Napi ütemezett feladatok (Hardcoded alapbeállítások) ===

celery_app.conf.beat_schedule.update({
    # 1️⃣ Napi feature generálás minden userre – 02:00-kor
    # Ez készíti el a "fényképet" a sportolók állapotáról
    "generate_user_features_daily": {
        "task": "ml_engine.tasks.generate_user_features",
        "schedule": crontab(hour=2, minute=0),
    },

    # 2️⃣ Modell tréning minden nap 02:30-kor
    # Itt történik a hibrid tanítás (Valódi + 10.000 szintetikus adat)
    "train_form_prediction_model_daily": {
        "task": "ml_engine.tasks.train_form_prediction_model",
        "schedule": crontab(hour=2, minute=30),
    },

    # 3️⃣ Predikció aktív előfizetőkre – minden nap 03:00-kor
    # Ez számolja ki a végleges Formaindexet a friss modell alapján
    "predict_form_for_active_subscribers_daily": {
        "task": "ml_engine.tasks.predict_form_for_active_subscribers",
        "schedule": crontab(hour=3, minute=0),
    },
})

# Opcionális: Sorok (Queue) beállítása, ha több worker-t használsz
celery_app.conf.task_routes = {
    "ml_engine.tasks.*": {"queue": "ml_engine"},
}