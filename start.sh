#!/bin/sh
set -eu
ffmpeg -version >/dev/null
sox --version >/dev/null
exec python -u /app/handler.py
