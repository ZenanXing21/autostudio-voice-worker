import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    model_id: str = os.getenv("MODEL_ID", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    data_dir: Path = Path(os.getenv("DATA_DIR", "/runpod-volume/autostudio"))
    hf_home: Path = Path(os.getenv("HF_HOME", "/runpod-volume/hf-cache"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "/workspace/outputs"))
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "")
    s3_region: str = os.getenv("S3_REGION", "auto")
    reference_hosts: str = os.getenv("REFERENCE_HOSTS", "")
    max_reference_bytes: int = int(os.getenv("MAX_REFERENCE_BYTES", str(25 * 1024 * 1024)))
    max_text_chars: int = int(os.getenv("MAX_TEXT_CHARS", "10000"))
    chunk_chars: int = int(os.getenv("CHUNK_CHARS", "180"))
    presign_seconds: int = int(os.getenv("PRESIGN_SECONDS", "3600"))

    def validate(self):
        if not self.model_id.endswith("-Base"):
            raise ValueError("Voice cloning requires a Qwen3-TTS Base model")
