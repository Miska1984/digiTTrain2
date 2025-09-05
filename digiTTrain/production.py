# digiTTrain/production.py
from .settings import *
import os


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

# Képfeltöltés Google Cloud Storage-ba
DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
GS_BUCKET_NAME = os.environ.get('GS_BUCKET_NAME')
GS_AUTO_CREATE_BUCKET = False
GS_LOCATION = 'europe-west1'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'
