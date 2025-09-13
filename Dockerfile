# Használjunk hivatalos Python image-t
FROM python:3.12-slim

# Ne bufferezzen a Python (jobb logolás Cloud Run-ban)
ENV PYTHONUNBUFFERED=1

# Munkakönyvtár
WORKDIR /app

# Rendszerfüggőségek telepítése (mysqlclient és Node.js miatt)
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libmariadb-dev-compat \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Függőségek másolása és telepítése
COPY requirements.txt .
COPY package.json .

# Python függőségek telepítése
RUN pip install --no-cache-dir -r requirements.txt

# Explicit módon másoljuk be a Tailwindhez szükséges fájlokat
COPY tailwind.config.js ./
COPY static/src/input.css ./static/src/

# Node.js függőségek telepítése
RUN npm install

# A többi alkalmazásfájl bemásolása
COPY . .

# Tailwind CSS buildelése
RUN mkdir -p ./static/dist && \
    npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify --config tailwind.config.js

# Állítsuk be a környezetet a beállításokhoz
ENV ENVIRONMENT="production"

# BUILD MODE beállítás a collectstatic-hoz (helyi storage használata build közben)
ENV BUILD_MODE=true

# Statikus fájlok összegyűjtése (build közben helyi storage-ba)
RUN python manage.py collectstatic --no-input --verbosity=2 --settings=digiTTrain.settings

# BUILD MODE kikapcsolása runtime-hoz (GCS használata)
ENV BUILD_MODE=false

# PYTHONPATH beállítás
ENV PYTHONPATH=/app

# Cloud Run port
ENV PORT=8080

# FONTOS: Settings module javítása
ENV DJANGO_SETTINGS_MODULE="digiTTrain.settings"

# Mappajogok beállítása (bár GCS esetén ez nem lesz releváns)
RUN mkdir -p /app/media_root /app/staticfiles_temp
RUN chown -R www-data:www-data /app/media_root /app/staticfiles_temp
RUN chmod -R 775 /app/media_root /app/staticfiles_temp

# A Gunicorn indítja a Django appot
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "digiTTrain.wsgi:application"]