# digiTTrain/production.py
import os
import sys
from .base import *

print(">>> [DEBUG] Production settings loaded <<<", file=sys.stderr)

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
GS_BUCKET_NAME = os.environ.get("GS_BUCKET_NAME", "digittrain-media-publikus-miska1984")
GS_PROJECT_ID = os.environ.get("GS_PROJECT_ID", "digittrain-projekt")
GS_LOCATION = os.environ.get("GS_LOCATION", "europe-west1")

GS_AUTO_CREATE_BUCKET = False
GS_DEFAULT_ACL = "publicRead"
GS_QUERYSTRING_AUTH = False
GS_FILE_OVERWRITE = False
GS_MAX_MEMORY_SIZE = 1024 * 1024 * 5  # 5MB

# URL-ek
MEDIA_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/"
STATIC_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/static/"

# Ideiglenes mappák (collectstatic-hez)
STATIC_ROOT = "/app/staticfiles_temp"
MEDIA_ROOT = "/app/mediafiles_temp"

# Logging a hibakereséshez
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('storages')
logger.setLevel(logging.DEBUG)

# Custom storage classok
from storages.backends import gcloud

# Custom storage classok részletesebb hibakezeléssel
class MediaStorage(gcloud.GoogleCloudStorage):
    bucket_name = GS_BUCKET_NAME
    default_acl = 'publicRead'
    querystring_auth = False
    location = ''
    
    def _save(self, name, content):
        try:
            print(f"Próbálkozás fájl mentésével: {name}")
            print(f"Bucket: {self.bucket_name}")
            result = super()._save(name, content)
            print(f"Sikeres mentés: {result}")
            return result
        except Exception as e:
            print(f"Storage mentési hiba: {str(e)}")
            print(f"Hiba típusa: {type(e).__name__}")
            raise

class StaticStorage(gcloud.GoogleCloudStorage):
    bucket_name = GS_BUCKET_NAME
    default_acl = 'publicRead'
    querystring_auth = False
    location = 'static'  # minden static fájl a /static/ alá kerül

# ===== STORAGE KONFIGURÁCIÓ BUILD MODE TÁMOGATÁSSAL =====
BUILD_MODE = os.getenv('BUILD_MODE', 'false').lower() == 'true'

if BUILD_MODE:
    # Build közben használjon local storage-t
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    print(">>> [DEBUG] BUILD MODE: Using local storage for collectstatic <<<", file=sys.stderr)
    
    # Build közben helyi útvonalak
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    
else:
    # Runtime-ban használja a GCS-t
    STORAGES = {
        "default": {
            "BACKEND": "digiTTrain.production.MediaStorage",
        },
        "staticfiles": {
            "BACKEND": "digiTTrain.production.StaticStorage",
        },
    }
    print(">>> [DEBUG] RUNTIME MODE: Using GCS storage <<<", file=sys.stderr)

print(
    ">>> [DEBUG] Active storage configuration:",
    f"BUILD_MODE={BUILD_MODE},",
    "default:", STORAGES["default"]["BACKEND"],
    "staticfiles:", STORAGES["staticfiles"]["BACKEND"],
    file=sys.stderr
)