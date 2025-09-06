# Használjunk hivatalos Python image-t
FROM python:3.12-slim

# Ne bufferezzen a Python (jobb logolás Cloud Run-ban)
ENV PYTHONUNBUFFERED=1

# Munkakönyvtár
WORKDIR /app

# Rendszerfüggőségek telepítése (mysqlclient miatt kell)
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libmariadb-dev-compat \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.js és npm telepítése a Tailwindhez
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Követelmények másolása és telepítése
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Alkalmazás fájlok bemásolása
COPY . .

# Tailwind CSS telepítése és buildelése
# Ezt kell futtatni a production.py fájl betöltése előtt,
# mivel a Tailwindnek szüksége van az összes sablonfájlra.
RUN npm install -D tailwindcss
RUN npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify

# Statikus fájlok összegyűjtése
# A Django `collectstatic` parancs összegyűjti az összes statikus fájlt
# a STATIC_ROOT-ba. A production.py fájlban a STATIC_ROOT
# GCS-re van beállítva.
RUN python manage.py collectstatic --no-input

# PYTHONPATH beállítás (hogy a modulok jól látszódjanak)
ENV PYTHONPATH=/app

# Cloud Run port
ENV PORT=8080

# Default Django settings
ENV DJANGO_SETTINGS_MODULE=digiTTrain.production

# Változtasd meg a mappa tulajdonosát a www-data felhasználóra
RUN chown -R www-data:www-data /app/media_root

# Adjon írási jogot a mappára a www-data számára
RUN chmod -R 775 /app/media_root

# A Gunicorn indítja a Django appot
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "digiTTrain.wsgi:application"]
