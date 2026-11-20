ARG PYTHON_BASE=python:3.12-slim
FROM ${PYTHON_BASE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/runpod-volume/hf-cache DATA_DIR=/runpod-volume/autostudio
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu126
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN python -c "import torch, torchaudio; assert torch.__version__ == '2.7.1+cu126', torch.__version__; assert torchaudio.__version__ == '2.7.1+cu126', torchaudio.__version__; assert torch.version.cuda == '12.6', torch.version.cuda; print('Verified official PyTorch CUDA wheel:', torch.__version__, 'CUDA', torch.version.cuda)"
RUN apt-get update && apt-get install -y --no-install-recommends sox && rm -rf /var/lib/apt/lists/*
RUN python -c "import imageio_ffmpeg, shutil; shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), '/usr/local/bin/ffmpeg')" && ffmpeg -hide_banner -encoders | grep -q libmp3lame
ENV OUTPUT_DIR=/runpod-volume/autostudio/outputs
COPY app ./app
COPY scripts ./scripts
COPY handler.py config.py start.sh pronunciation.json ./
RUN chmod +x start.sh
CMD ["python", "-u", "handler.py"]
