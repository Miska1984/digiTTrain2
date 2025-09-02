# digiTTrain/production.py
from .settings import *
import os

# Ha nincs ALLOWED_HOSTS beállítva, akkor ne legyen None
ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS', '*')]

# Adatbázis beállításai Cloud SQL-hez (socket vagy TCP)
CLOUDSQL_CONNECTION_NAME = os.getenv("CLOUDSQL_CONNECTION_NAME")

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        'HOST': f"/cloudsql/{CLOUDSQL_CONNECTION_NAME}" if CLOUDSQL_CONNECTION_NAME else os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
