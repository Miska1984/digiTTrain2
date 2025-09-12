# digiTTrain/settings.py
import os
from .base import *

ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development').strip().lower()

if ENVIRONMENT == 'production':
    from .production import *
else:
    from .development import *
