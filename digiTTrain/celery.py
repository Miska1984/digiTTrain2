# digiTTrain/celery.py

import os
from celery import Celery

# Állítsa be a Celery számára a Django beállítások modulját
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digiTTrain.settings')


# Celery app inicializálása
# A projekt neve a Celery app-hoz: 'digiTTrain'
app = Celery('digiTTrain') 

# A Celery konfigot a Django settings.py-ból olvassa (ahol a CELERY_ beállítások vannak)
app.config_from_object('django.conf:settings', namespace='CELERY')

# A Celery taskok automatikus felfedezése (minden `tasks.py` fájlban)
app.autodiscover_tasks()