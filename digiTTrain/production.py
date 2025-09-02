# digiTTrain/production.py
from .settings import *
import os

# Ha nincs ALLOWED_HOSTS beállítva, akkor ne legyen None
ALLOWED_HOSTS = [os.environ.get('ALLOWED_HOSTS', '*')]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        # TCP kapcsolathoz a DB hostot használjuk
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
