from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-development-secret-key'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']  # Engedélyezi a Codespace-en való futtatást

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'digiTTrain2',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': 'db', # <-- Itt van a változás
        'PORT': '3306',
    }
}