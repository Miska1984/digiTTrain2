# digiTTrain/production.py
import os
from .base import *


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

# ===== GOOGLE CLOUD STORAGE =====
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
STATICFILES_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"

GS_BUCKET_NAME = os.environ.get("GS_BUCKET_NAME", "digittrain-media-publikus-miska1984")
GS_PROJECT_ID = os.environ.get("GS_PROJECT_ID", "digittrain-projekt")
GS_DEFAULT_ACL = "publicRead"
GS_QUERYSTRING_AUTH = False
GS_FILE_OVERWRITE = False
GS_MAX_MEMORY_SIZE = 1024 * 1024 * 5  # 5MB

MEDIA_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/"
STATIC_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/static/"

MEDIA_ROOT = ""
STATIC_ROOT = ""
