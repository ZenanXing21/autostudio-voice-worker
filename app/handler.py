import os
import tempfile
import uuid
from pathlib import Path

from app.alignment import write_captions
from app.audio_processor import process_segments
from app.config import Settings
from app.storage import LocalStorage, Storage
from app.text_chunker import chunk_text
from app.text_normalizer import normalize
from app.voice_manager import VoiceManager, fetch_reference


class Worker:
    def __init__(self, settings=None, engine=None, storage=None):
        self.settings = settings or Settings()
        self.settings.validate()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.hf_home.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(self.settings.hf_home)
        self.storage_mode = "s3" if self.settings.s3_bucket else "local"
        self.storage = storage or (Storage(self.settings) if self.settings.s3_bucket else LocalStorage(self.settings))
        self.voices = VoiceManager(self.settings, self.storage)
        self.loaded_profiles = self.voices.list_profiles()
        if engine is None:
            from app.tts_engine import TTSEngine
            engine = TTSEngine(self.settings.model_id)
        self.engine = engine

    def handle(self, job):
        data = job.get("input", job)
        try:
            if not isinstance(data, dict):
                raise ValueError("input must be an object")
            task = data.get("task_type")
            if task == "register_voice":
                with tempfile.TemporaryDirectory() as tmp:
                    source = Path(tmp) / "reference_input"
                    fetch_reference(data["reference_audio_url"], source, self.settings)
                    profile = self.voices.register(data["voice_name"], source, data["reference_text"], data.get("language", "Chinese"), data.get("style", "documentary"))
                return {"status": "completed", "voice_id": profile["voice_id"], "style": profile["style"], "message": "Voice profile created", "quality": profile["quality"]}
            if task == "tts_generate":
                text = data["text"]
                if len(text) > self.settings.max_text_chars:
                    raise ValueError("text exceeds MAX_TEXT_CHARS")
                profile = self.voices.get(data["voice_id"], data.get("style", "documentary"))
                normalized = normalize(text, os.getenv("PRONUNCIATION_DICTIONARY", "/app/pronunciation.json"))
                chunks = chunk_text(normalized, self.settings.chunk_chars)
                waves, sr = self.engine.generate(profile, chunks, data.get("language", "Auto"))
                with tempfile.TemporaryDirectory() as tmp:
                    workdir = Path(tmp)
                    fmt = data.get("format", "wav")
                    files, segments, duration = process_segments(waves, sr, workdir, float(data.get("speed", 1.0)), fmt)
                    files.update(write_captions(segments, workdir))
                    job_id = uuid.uuid4().hex
                    locations = {name: self.storage.upload(path, f"outputs/{job_id}/{path.name}") for name, path in files.items()}
                result = {"status": "completed", "voice_id": profile["voice_id"], "storage_mode": self.storage_mode, "duration": round(duration, 3), "sample_rate": 24000, "alignment_level": "audio_chunk"}
                for name, source in (("audio", fmt), ("wav", "wav"), ("raw_wav", "raw_wav"), ("captions", "captions"), ("segments", "segments")):
                    result[f"{name}_url"] = locations[source] if self.storage_mode == "s3" else None
                    if self.storage_mode == "local":
                        result[f"{name}_path"] = locations[source]
                return result
            raise ValueError("task_type must be register_voice or tts_generate")
        except (KeyError, ValueError, RuntimeError) as exc:
            return {"status": "error", "error_type": type(exc).__name__, "message": str(exc)}
        except Exception:
            return {"status": "error", "error_type": "ProcessingError", "message": "processing failed; inspect worker dependencies, media input, and storage configuration"}


_worker = None


def handler(job):
    global _worker
    if _worker is None:
        _worker = Worker()
    return _worker.handle(job)
