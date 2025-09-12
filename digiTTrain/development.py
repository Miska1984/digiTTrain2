# digiTTrain/development.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'digittrain2',
        'USER': 'digittrain_user',
        'PASSWORD': 'password',
        'HOST': 'mysql-db',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

DEBUG = True
ALLOWED_HOSTS = ["*"]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media_root")
