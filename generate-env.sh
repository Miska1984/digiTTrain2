cat > .env.yaml <<INNEREOF
DB_NAME: digittraindb
DB_USER: root
DB_PASS: $DB_PASS  # ⬅️ VISSZA KELL TÉRNED IDE!
DJANGO_SETTINGS_MODULE: digiTTrain.settings
ALLOWED_HOSTS: digit-train-web-195803356854.europe-west1.run.app,digit-train.hu,www.digit-train.hu
CLOUDSQL_CONNECTION_NAME: digittrain-projekt:europe-west1:digitrain-mysql-db-west1
GS_BUCKET_NAME: digittrain-media-publikus-miska1984
GS_PROJECT_ID: digittrain-projekt
GS_LOCATION: europe-west1
ENVIRONMENT: production
GCP_SA_KEY_PATH: /app/gcp_service_account.json
REDIS_HOST: 10.32.84.131
REDIS_PORT: "6379"
INNEREOF

echo "✅ .env.yaml létrehozva:"
cat .env.yaml
EOF