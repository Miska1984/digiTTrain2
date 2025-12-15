# digiTTrain/development.py

import os
from pathlib import Path
from storages.backends import gcloud
import sys
from datetime import timedelta
from google.oauth2 import service_account
import json

# Először mindig betöltjük az alapbeállításokat
from .base import *

# BASE_DIR a projekt gyökérkönyvtárát jelöli (ahol a gcp_service_account.json van)
BASE_DIR = Path(__file__).resolve().parent.parent

# Development-specifikus beállítások
DEBUG = True
ALLOWED_HOSTS = ["*"]
ENVIRONMENT = 'development'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'digittrain2',
        'USER': 'digittrain_user',
        'PASSWORD': 'password',
        'HOST': 'mysql-db',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# =========================================================
# 🆕 GOOGLE CLOUD STORAGE BEÁLLÍTÁSOK (DEV)
# =========================================================

# 🟢 JAVÍTOTT: A kulcs elérési útjának megadása
GCP_SA_KEY_PATH = os.path.join(BASE_DIR, 'gcp_service_account.json')
# 🟢 JAVÍTOTT: A django-storages ezt a beállítást használja a hitelesítéshez
GS_CREDENTIALS = None

if os.path.exists(GCP_SA_KEY_PATH):
    try:
        # 1. Beolvassuk a JSON fájl tartalmát
        with open(GCP_SA_KEY_PATH, 'r') as f:
            service_account_info = json.load(f)
        
        # 2. Létrehozzuk a Google Credentials objektumot
        GS_CREDENTIALS = service_account.Credentials.from_service_account_info(service_account_info)
        print("✅ GCS hitelesítő adatok sikeresen betöltve a JSON fájlból.")
    except Exception as e:
        # Ha a fájl létezik, de rossz a formátum
        print(f"❌ HIBA a gcp_service_account.json betöltésekor: {e}")


# ❗ KRITIKUS: A feltöltött env.yaml alapján beállított bucket név
GS_BUCKET_NAME = os.environ.get('GS_BUCKET_NAME', 'digittrain-media-publikus-miska1984')
GS_PROJECT_ID = 'digittrain-projekt'

# GCS storage viselkedése dev módban
GS_DEFAULT_ACL = None
# Aláírt URL-ek használatának engedélyezése a GCS-hez (Fontos a Signed URL generáláshoz!)
GS_QUERYSTRING_AUTH = True 

# 🆕 Külön Storage osztály Dev környezethez
class DevelopmentMediaStorage(gcloud.GoogleCloudStorage):
    def __init__(self, *args, **kwargs):
        kwargs['credentials'] = GS_CREDENTIALS
        
        # 🟢 ÚJ: TÖRÖLJÜK A 'predefined_acl'-t, ha az UBLA be van kapcsolva a vödrön.
        # A django-storages a GS_DEFAULT_ACL=None esetén nem adja át.
        if 'default_acl' in kwargs and kwargs['default_acl'] is None:
            kwargs.pop('default_acl') 

        # 2. Meghívjuk az ősosztály konstruktorát
        super().__init__(*args, **kwargs)

    bucket_name = GS_BUCKET_NAME
    default_acl = GS_DEFAULT_ACL # EZ MÁR None
    querystring_auth = GS_QUERYSTRING_AUTH
    location = 'media/dev'

# ===== STORAGE KONFIGURÁCIÓ DEVELOMENT MODE-BAN =====
STORAGES = {
    # 💾 MEDIA STORAGE: A videók és képek GCS-re mennek (DevStorage-on keresztül)
    "default": {
        "BACKEND": "digiTTrain.development.DevelopmentMediaStorage",
    },
    # 🖼️ STATIC FILES: Maradjon a lokális tárolás a gyorsabb fejlesztés érdekében
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# 💡 A GCS-en tárolt fájlok URL-jének megadása (a `location` prefixet használja)
MEDIA_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/media/dev/"


# Debug info
print(f"📂 [DEV] GCS Bucket: {GS_BUCKET_NAME}")
print(f"[DEV] Storage Backend: digiTTrain.development.DevelopmentMediaStorage")
print(f"[DEV] MEDIA_URL: {MEDIA_URL}")


# 🔹 Fájl feltöltés timeout növelése
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB


# ===== CELERY BEÁLLÍTÁSOK A DOCKER/REDIS-HEZ =====
# A 'redis' hostname a docker-compose.yml-ben definiált szolgáltatás neve.
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_ALWAYS_EAGER = False  # csak ha tesztelni akarod: True
CELERY_ACKS_LATE = True
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_CONCURRENCY = 2


STATIC_ROOT = '/app/staticfiles'