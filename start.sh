#!/bin/sh
set -eu
ffmpeg -version >/dev/null
exec python handler.py
