#!/bin/sh
set -eu
python -m scripts.download_gpt_sovits_models --model-dir "${GPT_SOVITS_MODEL_DIR:-/runpod-volume/gpt-sovits}"
