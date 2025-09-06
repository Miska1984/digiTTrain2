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

# Először csak a csomagkezelő fájlokat másoljuk be, hogy kihasználjuk a Docker réteg-cache-t
COPY package.json .
COPY requirements.txt .

# Node.js függőségek telepítése
# Ez a parancs a package.json alapján telepíti a fejlesztési és futtatási függőségeket
RUN npm install

# Python függőségek telepítése
RUN pip install --no-cache-dir -r requirements.txt

# Most másoljuk be a teljes projektet, beleértve a Tailwind konfigurációs és input fájlokat
# A tailwind.config.js és input.css fájloknak már létezniük kell a projekt gyökerében
COPY tailwind.config.js ./
COPY static/src/input.css ./static/src/
COPY . .

# Tailwind CSS buildelése
# Ez most már a node_modules mappából fog futni, ahová az npm install telepítette
RUN npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify

# Statikus fájlok összegyűjtése a GCS-be
# A production.py felülírja a STATIC_ROOT beállítást, így ez a parancs a GCS-be tölti fel.
RUN python manage.py collectstatic --no-input

# PYTHONPATH beállítás (hogy a modulok jól látszódjanak)
ENV PYTHONPATH=/app

# Cloud Run port beállítása
ENV PORT=8080

# Default Django settings éles környezethez
ENV DJANGO_SETTINGS_MODULE=digiTTrain.production

# Mappa jogainak beállítása a media fájlokhoz
# Ez főleg a fejlesztési környezetben fontos, élesben a GCS kezeli a fájlokat.
# Ha a collectstatic futtatása előtt történik, a www-data felhasználónak írási jogot adunk.
RUN chown -R www-data:www-data /app/media_root
RUN chmod -R 775 /app/media_root

# A Gunicorn indítja a Django appot a megadott porton
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "digiTTrain.wsgi:application"]