# ----------------------------
# 📦 Base image
# ----------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ----------------------------
# 🧩 System dependencies
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
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ----------------------------
# 🧘 TensorFlow / MediaPipe CPU-only environment
# ----------------------------
ENV TF_CPP_MIN_LOG_LEVEL=2
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV CUDA_VISIBLE_DEVICES=-1

# ----------------------------
# 📦 Python dependencies
# ----------------------------
COPY requirements.txt ./requirements.txt
COPY package.json ./package.json
COPY tailwind.config.js ./tailwind.config.js
COPY static/src/input.css ./static/src/input.css

# Install protobuf first to ensure Google libs are compatible
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --upgrade protobuf==4.25.3 && \
    pip install --no-cache-dir --default-timeout=300 -r requirements.txt

# ✅ Fix: Frissítjük a google-cloud-run csomagot az ExecutionOverrides támogatáshoz
RUN pip install --no-cache-dir --upgrade "google-cloud-run>=0.10.0"

# ✅ Sanity checks
RUN python -c "import google.cloud.run_v2, google.cloud.storage, tensorflow, mediapipe; print('✅ All imports OK')"

# ----------------------------
# 🎨 Tailwind CSS build
# ----------------------------
RUN node -v && npm -v && \
    npm install -g npm@latest && \
    npm install && \
    npm install -g tailwindcss && \
    mkdir -p ./static/dist && \
    npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify

# ----------------------------
# 📁 Project files
# ----------------------------
COPY . .

# Cleanup caches
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ----------------------------
# 🔐 GCP credentials
# ----------------------------
COPY gcp_service_account.json /app/gcp_service_account.json
ENV GCP_SA_KEY_PATH=/app/gcp_service_account.json

# ----------------------------
# 🧠 MediaPipe asset check
# ----------------------------
RUN if [ -f assets/pose_landmarker_full.task ]; then \
        echo "✅ MediaPipe asset found."; \
    else \
        echo "⚠️ MediaPipe asset not found, will be downloaded at runtime."; \
    fi

# ----------------------------
# ⚙️ Django environment
# ----------------------------
ENV ENVIRONMENT=production
ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages:/app
ENV DJANGO_SETTINGS_MODULE=digiTTrain.settings
ENV PORT=8080

# ----------------------------
# 🧱 Static files
# ----------------------------
ENV BUILD_MODE=true
RUN python manage.py collectstatic --no-input --verbosity=2
ENV BUILD_MODE=false

# ----------------------------
# 👤 User and permissions
# ----------------------------
RUN mkdir -p /app/media_root /app/staticfiles_temp && \
    chown -R www-data:www-data /app/media_root /app/staticfiles_temp && \
    chmod -R 775 /app/media_root /app/staticfiles_temp

USER www-data

# ----------------------------
# ▶️ Start Gunicorn
# ----------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--workers", "2", "digiTTrain.wsgi:application"]
