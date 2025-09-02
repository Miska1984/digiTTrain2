# digiTTrain/production.py
from .settings import *
import os

# Ha nincs ALLOWED_HOSTS beállítva, akkor ne legyen None
ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS', '*')]

# Adatbázis beállításai Cloud SQL-hez (socket vagy TCP)
if os.getenv('CLOUDSQL_CONNECTION_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ['DB_NAME'],
            'USER': os.environ['DB_USER'],
            'PASSWORD': os.environ['DB_PASS'],
            'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
            },
        }
    }
