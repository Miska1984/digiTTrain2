# ----------------------------
# 📦 Alap image
# ----------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ----------------------------
# 🧩 Rendszerfüggőségek (WeasyPrint + OpenCV + Node.js)
# ----------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    cmake \
    git \
    wget \
    ffmpeg \
    libmariadb-dev-compat \
    libffi-dev \
    # 🧾 WeasyPrint + Cairo függőségek
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libgobject-2.0-0 \
    libpangocairo-1.0-0 \
    shared-mime-info \
    pango1.0-tools \
    libglib2.0-0 \
    libsm6 libxext6 libxrender-dev \
    libgl1 \
    curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ----------------------------
# 📦 Python + Node függőségek
# ----------------------------
COPY requirements.txt ./requirements.txt
COPY package.json ./package.json
COPY tailwind.config.js ./tailwind.config.js
COPY static/src/input.css ./static/src/input.css

# 🟢 PIP frissítés + függőségek telepítése (megnövelt timeout a nagy fájlokhoz)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --default-timeout=300 -r requirements.txt

# Ensure google-cloud-run is definitely installed in the web container too
RUN pip install --no-cache-dir google-cloud-run google-cloud-storage && \
    python -c "from google.cloud import run_v2; print('✅ google-cloud-run import OK')" && \
    python -c "from google.cloud import storage; print('✅ google-cloud-storage import OK')"

# ✅ KRITIKUS ELLENŐRZÉSEK - Ne engedd át a buildet, ha hiányzik valami!
RUN python -m pip show google-cloud-run || (echo "❌ google-cloud-run NOT FOUND!" && exit 1)
RUN python -m pip show google-cloud-storage || (echo "❌ google-cloud-storage NOT FOUND!" && exit 1)

# 🔧 Extra GCP kliens könyvtárak — a webapp is használja őket (Cloud Run API, Storage stb.)
RUN pip install --no-cache-dir google-cloud-run google-cloud-storage

# ✅ ÚJ: Python import teszt - ellenőrzi, hogy tényleg importálható-e
RUN python -c "from google.cloud import run_v2; print('✅ google-cloud-run import OK')" || \
    (echo "❌ google-cloud-run nem importálható!" && exit 1)

RUN python -c "from google.cloud import storage; print('✅ google-cloud-storage import OK')" || \
    (echo "❌ google-cloud-storage nem importálható!" && exit 1)

# ----------------------------
# 🎨 Tailwind CSS build JAVÍTOTT
# ----------------------------
RUN npm install && \
    npm install -g tailwindcss && \
    mkdir -p ./static/dist && \
    npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify --config tailwind.config.js

# ----------------------------
# 📁 Projektfájlok
# ----------------------------
COPY . .

# 🧹 Python cache tisztítása (force friss import)
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 🔐 Szolgáltatási fiók kulcs másolása a konténerbe
COPY gcp_service_account.json /app/gcp_service_account.json

# Környezeti változó, hogy a Django-kód megtalálja
ENV GCP_SA_KEY_PATH=/app/gcp_service_account.json

RUN if [ -f assets/pose_landmarker_full.task ]; then echo "MediaPipe assets found."; else echo "WARNING: MediaPipe asset not found in assets/pose_landmarker_full.task" && exit 1; fi

# ----------------------------
# ⚙️ Django környezet
# ----------------------------
ENV ENVIRONMENT=production
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=digiTTrain.settings
ENV PORT=8080

# ----------------------------
# 🧱 Statikus és média fájlok
# ----------------------------
ENV BUILD_MODE=true
RUN python manage.py collectstatic --no-input --verbosity=2 --settings=digiTTrain.settings
ENV BUILD_MODE=false

RUN mkdir -p /app/media_root /app/staticfiles_temp && \
    chown -R www-data:www-data /app/media_root /app/staticfiles_temp && \
    chmod -R 775 /app/media_root /app/staticfiles_temp

# 🔧 Jogosultság javítás a Python könyvtárra (különösen a google-cloud-run csomaghoz)
RUN chmod -R a+rX /usr/local/lib/python3.12/site-packages

# ✅ PATH javítás: a www-data és Django is látja a telepített csomagokat
ENV PYTHONPATH="/usr/local/lib/python3.12/site-packages:/app"

# ----------------------------
# 👤 Felhasználó beállítása
# ----------------------------
USER www-data

# ----------------------------
# ▶️ Indítás
# ----------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8080","--timeout", "120", "--workers", "2", "digiTTrain.wsgi:application"]

