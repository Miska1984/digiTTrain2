# Dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt

COPY . /app/

# Django settings
ENV DJANGO_SETTINGS_MODULE=digiTTrain.settings

CMD exec gunicorn digiTTrain.wsgi:application --bind :$PORT --workers 2 --threads 4 --timeout 0