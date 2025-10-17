# Használjunk hivatalos Python image-t
FROM python:3.12-slim

# Munkakönyvtár
WORKDIR /app

# ----------------------------
# 🧩 Rendszerszintű függőségek telepítése (WeasyPrint, Node.js/Tailwind)
# A függőségeket egyetlen RUN parancsban telepítjük a rétegek számának csökkentése érdekében.
# ----------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libmariadb-dev-compat \
    libffi-dev \
    # WeasyPrint/Cairo/Pango függőségek
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \  <-- 💥 JAVÍTVA EZ A SOR!
    libgobject-2.0-0 \
    libjpeg-dev \
    zlib1g-dev \
    pkg-config \
    pango1.0-tools \
    libpangocairo-1.0-0 \
    shared-mime-info \
    # Node.js (a Tailwind buildeléshez)
    nodejs \
    npm \
    # Tisztítás
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# 📦 Python és Node.js függőségek telepítése
# ----------------------------

# Függőségek és fájlok másolása
COPY requirements.txt .
COPY package.json .
COPY tailwind.config.js ./
COPY static/src/input.css ./static/src/

# Python függőségek telepítése
RUN pip install --no-cache-dir -r requirements.txt

# Node.js függőségek telepítése
RUN npm install

# Tailwind CSS buildelése
RUN mkdir -p ./static/dist && \
    npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify --config tailwind.config.js

# A többi alkalmazásfájl bemásolása
COPY . .

# ----------------------------
# ⚙️ Környezeti Beállítások (Cloud Run / Django)
# ----------------------------

# Környezeti változók (egyszeri beállítás)
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT="production"
ENV PYTHONPATH=/app
ENV PORT=8080
ENV DJANGO_SETTINGS_MODULE="digiTTrain.settings"

# BUILD MODE beállítás a collectstatic-hoz (helyi storage használata build közben)
ENV BUILD_MODE=true
# Statikus fájlok összegyűjtése (build közben helyi storage-ba)
RUN python manage.py collectstatic --no-input --verbosity=2 --settings=digiTTrain.settings
# BUILD MODE kikapcsolása runtime-hoz (GCS használata)
ENV BUILD_MODE=false


# Mappajogok beállítása (jó gyakorlat a biztonságos futtatáshoz)
RUN mkdir -p /app/media_root /app/staticfiles_temp && \
    chown -R www-data:www-data /app/media_root /app/staticfiles_temp && \
    chmod -R 775 /app/media_root /app/staticfiles_temp

# ----------------------------
# ▶️ Indítás
# ----------------------------

# A Gunicorn indítja a Django appot
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "digiTTrain.wsgi:application"]