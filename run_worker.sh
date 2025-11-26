#!/bin/bash

# A Cloud Run elvárja, hogy egy folyamat válaszoljon a $PORT (8080) változón lévő porton.

# 1. Indítjuk a Celery Worker-t a háttérben (Daemon mód)
# A --concurrency és a pool beállítása a Cloud Run konfigurációtól függ.
echo "🚀 Celery Worker indítása a háttérben (Redis Broker figyelése)..."
celery -A digiTTrain worker --loglevel=INFO --concurrency=2 --pool=solo & 

# Eltároljuk a Celery folyamat ID-ját, hogy később leállíthassuk (szükség esetén).
CELERY_PID=$!

# 2. Indítunk egy egyszerű HTTP szervert a 8080-as porton a Cloud Run Health Check-ekhez
# Ez a Python beépített HTTP szervere. Ezt a folyamatot hagyjuk előtérben, 
# így a konténer nem áll le, és válaszol a Health Check-ekre.
echo "✅ Elindítjuk a Health Check szervert a $PORT porton..."
python3 -m http.server $PORT