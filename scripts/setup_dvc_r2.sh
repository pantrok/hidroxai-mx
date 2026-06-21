#!/usr/bin/env bash
# Configura el remoto DVC sobre Cloudflare R2 (S3-compatible).
# Lee credenciales de .env. Las claves se guardan SOLO localmente (.dvc/config.local).
set -euo pipefail
if [ -f .env ]; then set -a; . ./.env; set +a; fi
: "${R2_ENDPOINT_URL:?Define R2_ENDPOINT_URL en .env}"
: "${R2_BUCKET:=hidroxai-mx}"
command -v dvc >/dev/null 2>&1 || { echo "Instala DVC:  pip install 'dvc[s3]'"; exit 1; }
[ -d .dvc ] || dvc init
dvc remote add -d -f r2 "s3://${R2_BUCKET}/dvcstore"
dvc remote modify r2 endpointurl "${R2_ENDPOINT_URL}"
dvc remote modify r2 region auto
dvc remote modify --local r2 access_key_id     "${AWS_ACCESS_KEY_ID:?Define AWS_ACCESS_KEY_ID}"
dvc remote modify --local r2 secret_access_key "${AWS_SECRET_ACCESS_KEY:?Define AWS_SECRET_ACCESS_KEY}"
echo "OK. Remoto 'r2' configurado. Versiona datos con: dvc add data/processed && dvc push"
