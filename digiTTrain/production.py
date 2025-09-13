# digiTTrain/production.py
import os
import sys

print(">>> [DEBUG] Production settings loaded <<<", file=sys.stderr)

# Először mindig betöltjük az alapbeállításokat
from .base import *

# Production-specifikus beállítások
DEBUG = False

ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS', '*')]

CLOUDSQL_CONNECTION_NAME = os.getenv("CLOUDSQL_CONNECTION_NAME")

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        'HOST': f"/cloudsql/{CLOUDSQL_CONNECTION_NAME}",
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

CSRF_TRUSTED_ORIGINS = [
    'https://digit-train-web-195803356854.europe-west1.run.app'
]

# ===== GOOGLE CLOUD STORAGE BEÁLLÍTÁSOK =====
# FONTOS: Két külön storage backend kell!
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
STATICFILES_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"

GS_BUCKET_NAME = os.environ.get("GS_BUCKET_NAME", "digittrain-media-publikus-miska1984")
GS_PROJECT_ID = os.environ.get("GS_PROJECT_ID", "digittrain-projekt")

# Hitelesítés beállítása
GS_AUTO_CREATE_BUCKET = False
GS_DEFAULT_ACL = "publicRead"
GS_QUERYSTRING_AUTH = False
GS_FILE_OVERWRITE = False
GS_MAX_MEMORY_SIZE = 1024 * 1024 * 5  # 5MB

# Location beállítás
GS_LOCATION = os.environ.get("GS_LOCATION", "europe-west1")

# KRITIKUS: Custom storage osztályok definiálása
GS_MEDIA_BUCKET_NAME = GS_BUCKET_NAME
GS_STATIC_BUCKET_NAME = GS_BUCKET_NAME

# URL-ek pontos beállítása
MEDIA_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/"
STATIC_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/static/"

# Ideiglenes mappák (collectstatic-hez)
STATIC_ROOT = "/app/staticfiles_temp"
MEDIA_ROOT = "/app/mediafiles_temp"

# Részletes logging a hibakereséshez
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('storages')
logger.setLevel(logging.DEBUG)

# Storage backend explicit importálása
from storages.backends import gcloud

# Custom storage class a jobb kontroll érdekében
class MediaStorage(gcloud.GoogleCloudStorage):
    bucket_name = GS_BUCKET_NAME
    default_acl = 'publicRead'
    querystring_auth = False
    location = ''  # Ne legyen prefix a media fájlokhoz

class StaticStorage(gcloud.GoogleCloudStorage):
    bucket_name = GS_BUCKET_NAME
    default_acl = 'publicRead' 
    querystring_auth = False
    location = 'static'  # Static fájlok a /static/ mappába

# Storage backend újradefiniálása
DEFAULT_FILE_STORAGE = 'digiTTrain.production.MediaStorage'
STATICFILES_STORAGE = 'digiTTrain.production.StaticStorage'