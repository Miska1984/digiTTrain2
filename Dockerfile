# Dockerfile

# Alap kép
FROM python:3.12

# A kimenet azonnali megjelenítése a logokban
ENV PYTHONUNBUFFERED=1

# Konténer munkakönyvtárának beállítása
# Most a gyökérkönyvtár lesz a munkakönyvtár
WORKDIR /app

# MySQL függőségek telepítése (fontos a telepítés a pip előtt)
RUN apt-get update && apt-get install -y default-libmysqlclient-dev

# Függőségek másolása és telepítése
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt

# A teljes projekt másolása
COPY . /app/

# Django settings környezeti változó beállítása
ENV DJANGO_SETTINGS_MODULE=digiTTrain2.digiTTrain.production

# A Gunicorn parancs a megfelelő elérési úttal
CMD exec gunicorn digiTTrain2.digiTTrain.wsgi:application --bind :$PORT --workers 2 --threads 4 --timeout 0