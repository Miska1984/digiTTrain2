# digiTTrain/development.py
from .settings import *
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

# Django adatbázis beállítások a Docker Compose-hoz
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'digittrain2',
        'USER': 'digittrain_user',
        'PASSWORD': 'password',
        'HOST': 'mysql-db', # a docker-compose.yml service neve
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Engedélyezd a DEBUG módot a helyi fejlesztéshez
DEBUG = True

# Engedélyezd a lokális hosztokat
ALLOWED_HOSTS = ['*']

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media_root')
