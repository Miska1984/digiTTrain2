# digiTTrain/production.py
import os
from .settings import *

INSTALLED_APPS += ["storages"]

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

# ADD THIS LINE
CSRF_TRUSTED_ORIGINS = ['https://digit-train-web-195803356854.europe-west1.run.app']


# ===== GOOGLE CLOUD STORAGE BEÁLLÍTÁSOK =====
# Fontos: django-storages backend használata
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
STATICFILES_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'

# GCS alapvető beállítások
GS_BUCKET_NAME = os.environ.get("GS_BUCKET_NAME", "digittrain-media-publikus-miska1984")
GS_PROJECT_ID = os.environ.get("GS_PROJECT_ID", "digittrain-projekt")

# KRITIKUS: Automatikus authentikáció beállítása
# Cloud Run környezetben automatikusan működik, ha a service account megfelelő jogokkal rendelkezik

# Bucket konfiguráció
GS_AUTO_CREATE_BUCKET = False
GS_LOCATION = os.environ.get("GS_LOCATION", "europe-west1")
GS_DEFAULT_ACL = 'publicRead'  # Publikus olvasás
GS_QUERYSTRING_AUTH = False  # Ne generáljon signed URL-eket

# URL beállítások
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'

# Fájl kezelési beállítások
GS_FILE_OVERWRITE = False  # Ne írja felül a meglévő fájlokat
GS_MAX_MEMORY_SIZE = 1024 * 1024 * 5  # 5MB

# Helyi media/static felülírása
MEDIA_ROOT = ''  # Ürítjük ki, mert GCS-t használunk
STATIC_ROOT = ''  # Ürítjük ki, mert GCS-t használunk

GS_MEDIA_PREFIX = 'media/'
GS_STATIC_PREFIX = 'static/'

