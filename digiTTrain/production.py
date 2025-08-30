# digiTTrain/production.py
from .settings import *
import os

# Cloud Run URL-je a "Bad Request (400)" hiba elkerülésére
ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS')] 

# Adatbázis beállításai a Cloud SQL-hez, környezeti változókból
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}