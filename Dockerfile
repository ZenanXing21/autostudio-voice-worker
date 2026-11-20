ARG PYTHON_BASE=python:3.12-slim
FROM ${PYTHON_BASE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/runpod-volume/hf-cache DATA_DIR=/runpod-volume/autostudio
WORKDIR /app
COPY requirements.txt requirements-gpt-sovits.txt ./
RUN python -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu126
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends build-essential cmake git ffmpeg sox \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir -r requirements.txt -r requirements-gpt-sovits.txt 'torch==2.7.1' 'torchaudio==2.7.1' 'x_transformers==2.3.1'
RUN python -c "import torch, torchaudio; assert torch.__version__ == '2.7.1+cu126', torch.__version__; assert torchaudio.__version__ == '2.7.1+cu126', torchaudio.__version__; assert torch.version.cuda == '12.6', torch.version.cuda; print('Verified official PyTorch CUDA wheel:', torch.__version__, 'CUDA', torch.version.cuda)"
RUN ffmpeg -hide_banner -encoders | grep -q libmp3lame

ARG GPT_SOVITS_COMMIT=6d51ffceafbf240145619af4c92408a6e54b7924
RUN git init /opt/GPT-SoVITS \
    && cd /opt/GPT-SoVITS \
    && git remote add origin https://github.com/RVC-Boss/GPT-SoVITS.git \
    && git config http.version HTTP/1.1 \
    && git sparse-checkout init --cone \
    && git sparse-checkout set GPT_SoVITS tools \
    && git fetch --filter=blob:none --depth 1 origin "$GPT_SOVITS_COMMIT" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "$GPT_SOVITS_COMMIT" \
    && printf '%s\n' "$GPT_SOVITS_COMMIT" > UPSTREAM_COMMIT \
    && rm -rf GPT_SoVITS/pretrained_models .git
ENV OUTPUT_DIR=/runpod-volume/autostudio/outputs
ENV GPT_SOVITS_SOURCE_DIR=/opt/GPT-SoVITS GPT_SOVITS_MODEL_DIR=/runpod-volume/gpt-sovits
ENV PYTHONPATH=/app:/opt/GPT-SoVITS:/opt/GPT-SoVITS/GPT_SoVITS
COPY app ./app
COPY scripts ./scripts
COPY evaluation ./evaluation
COPY handler.py config.py start.sh pronunciation.json ./
RUN chmod +x start.sh
WORKDIR /opt/GPT-SoVITS
CMD ["python", "-u", "/app/handler.py"]
