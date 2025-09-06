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

# Node.js és Python függőségek másolása és telepítése
COPY package.json .
COPY requirements.txt .

# Node.js függőségek telepítése
RUN npm install

# Python függőségek telepítése
RUN pip install --no-cache-dir -r requirements.txt

# A Tailwind input fájl és a konfig fájl bemásolása
COPY package.json .
COPY tailwind.config.js ./
COPY static/src/input.css ./static/src/

# A többi alkalmazásfájl bemásolása
COPY . .

# Tailwind CSS buildelése
# Ezt most már a meglévő node_modules mappából fogja futtatni
RUN npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify

# Statikus fájlok összegyűjtése a GCS-be
RUN python manage.py collectstatic --no-input

# PYTHONPATH beállítás
ENV PYTHONPATH=/app

# Cloud Run port
ENV PORT=8080

# Default Django settings
ENV DJANGO_SETTINGS_MODULE=digiTTrain.production

# Mappajogok beállítása
RUN chown -R www-data:www-data /app/media_root
RUN chmod -R 775 /app/media_root

# A Gunicorn indítja a Django appot
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "digiTTrain.wsgi:application"]