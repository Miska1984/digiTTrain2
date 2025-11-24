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
    libsm6 libxext6 libxrender-dev \
    libgl1 \
    curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# ----------------------------
# 📦 Python + Node függőségek
# ----------------------------
COPY requirements.txt ./
COPY package.json ./
COPY tailwind.config.js ./
COPY static/src/input.css ./static/src/

RUN pip install --no-cache-dir -r requirements.txt
RUN npm install

# ----------------------------
# 🎨 Tailwind CSS build
# ----------------------------
RUN mkdir -p ./static/dist && \
    npx tailwindcss -i ./static/src/input.css -o ./static/dist/output.css --minify --config tailwind.config.js

# ----------------------------
# 📁 Projektfájlok
# ----------------------------
COPY . .

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

# ----------------------------
# 👤 Felhasználó beállítása
# ----------------------------
# Fontos, hogy ne root-ként fusson a konténer.
USER www-data

# ----------------------------
# ▶️ Indítás
# ----------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8080","--timeout", "120", "--workers", "2", "digiTTrain.wsgi:application"]
