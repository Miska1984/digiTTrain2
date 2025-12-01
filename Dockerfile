# ----------------------------
# 📦 Alap image
# ----------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ----------------------------
# 🧩 Rendszerfüggőségek
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
# 📦 Python függőségek
# ----------------------------
COPY requirements.txt ./requirements.txt
COPY package.json ./package.json
COPY tailwind.config.js ./tailwind.config.js
COPY static/src/input.css ./static/src/input.css

# ⚠️ KRITIKUS: Előbb telepítjük a protobuf 4.25.3-at, MAJD a többit
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --default-timeout=300 -r requirements.txt

RUN python -m pip show google-cloud-run

# ✅ Ellenőrzés: protobuf verzió
RUN python -c "import google.protobuf; print(f'✅ Protobuf: {google.protobuf.__version__}')"

# ✅ Google Cloud import tesztek
RUN python -c "from google.cloud import run_v2; print('✅ run_v2 import OK')" || exit 1
RUN python -c "from google.cloud import storage; print('✅ storage import OK')" || exit 1

# ✅ AI/ML import tesztek
RUN python -c "import tensorflow as tf; print(f'✅ TensorFlow: {tf.__version__}')" || exit 1
RUN python -c "import mediapipe as mp; print(f'✅ MediaPipe: {mp.__version__}')" || exit 1

# ----------------------------
# 🎨 Tailwind CSS build
# ----------------------------
RUN npm install && \
    npm install -g tailwindcss && \
    mkdir -p ./static/dist && \
    npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify

# ----------------------------
# 📁 Projektfájlok
# ----------------------------
COPY . .

# Python cache tisztítása
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find . -type f -name "*.pyc" -delete 2>/dev/null || true

# GCP kulcs másolása
COPY gcp_service_account.json /app/gcp_service_account.json
ENV GCP_SA_KEY_PATH=/app/gcp_service_account.json

# MediaPipe asset ellenőrzés
RUN if [ -f assets/pose_landmarker_full.task ]; then \
        echo "✅ MediaPipe assets found."; \
    else \
        echo "⚠️ WARNING: MediaPipe asset not found" && exit 1; \
    fi

# ----------------------------
# ⚙️ Django környezet
# ----------------------------
ENV ENVIRONMENT=production
ENV PYTHONPATH=/app:/usr/local/lib/python3.12/site-packages
ENV DJANGO_SETTINGS_MODULE=digiTTrain.settings
ENV PORT=8080

# ----------------------------
# 🧱 Statikus fájlok
# ----------------------------
ENV BUILD_MODE=true
RUN python manage.py collectstatic --no-input --verbosity=2
ENV BUILD_MODE=false

RUN mkdir -p /app/media_root /app/staticfiles_temp && \
    chown -R www-data:www-data /app/media_root /app/staticfiles_temp && \
    chmod -R 775 /app/media_root /app/staticfiles_temp

# Jogosultságok
RUN chmod -R a+rX /usr/local/lib/python3.12/site-packages

# ----------------------------
# 👤 Felhasználó
# ----------------------------
USER www-data

# ✅ PYTHONPATH fix a www-data számára
ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages:/app

# ----------------------------
# ▶️ Indítás
# ----------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--workers", "2", "digiTTrain.wsgi:application"]