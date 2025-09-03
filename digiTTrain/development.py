# digiTTrain/development.py
from .settings import *

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