# digiTTrain/celery.py

import os
from celery import Celery
from django.core.exceptions import AppRegistryNotReady
from django.db.utils import OperationalError

# Állítsa be a Celery számára a Django beállítások modulját
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digiTTrain.settings')


# Celery app inicializálása
# A projekt neve a Celery app-hoz: 'digiTTrain'
app = Celery('digiTTrain') 

# A Celery konfigot a Django settings.py-ból olvassa (ahol a CELERY_ beállítások vannak)
app.config_from_object('django.conf:settings', namespace='CELERY')

# A Celery taskok automatikus felfedezése (minden `tasks.py` fájlban)
app.autodiscover_tasks()

# 🔹 Debug task (ellenőrzéshez)
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Celery Beat setup deferred – only runs after Django is fully loaded
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    try:
        import django
        django.setup()

        from django_celery_beat.models import PeriodicTask
        from ml_engine.schedules import setup_ml_tasks

        if not PeriodicTask.objects.exists():
            print("⏰ Celery Beat alapütemezések létrehozása...")
            setup_ml_tasks()
        else:
            print("✅ Celery Beat ütemezések már léteznek, kihagyva.")

    except (OperationalError, AppRegistryNotReady):
        print("⚠️ Django vagy az adatbázis még nem elérhető — Beat setup később próbálkozik.")
    except Exception as e:
        print(f"⚠️ Celery Beat setup kihagyva: {e}")