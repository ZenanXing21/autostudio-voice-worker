#!/bin/sh
set -eu
export HF_HOME="${HF_HOME:-/runpod-volume/hf-cache}"
python -c 'from huggingface_hub import snapshot_download; snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-Base")'
