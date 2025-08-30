# digiTTrain/development.py
from .settings import *

# Helyi MySQL adatbázis beállításai
from .settings import *

# Helyi MySQL adatbázis beállításai
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'digittrain2',
        'USER': 'digittrain_user',
        'PASSWORD': 'password',
        'HOST': 'mysql-db',
        'PORT': '3306',
    }
}