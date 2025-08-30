# digiTTrain/production.py
from .settings import *
import os

# Cloud Run URL-je a "Bad Request (400)" hiba elkerülésére
ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS')] 

# Adatbázis beállításai a Cloud SQL-hez, környezeti változókból
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        'HOST': os.getenv('DB_HOST'),  # Cloud SQL Unix socket
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}