#!/bin/sh
set -eu
ffmpeg -version >/dev/null
sox --version >/dev/null
case "${WORKER_MODE:-pod}" in
  pod) exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips '*' ;;
  serverless) exec python handler.py ;;
  *) echo "WORKER_MODE must be pod or serverless" >&2; exit 2 ;;
esac
