FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/runpod-volume/hf-cache DATA_DIR=/runpod-volume/autostudio
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY handler.py config.py start.sh pronunciation.json ./
RUN chmod +x start.sh
CMD ["./start.sh"]
