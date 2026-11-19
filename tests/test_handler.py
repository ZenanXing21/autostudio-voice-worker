from dataclasses import replace
from pathlib import Path
import json

from app.config import Settings
from app.handler import Worker


class FakeStorage:
    def upload(self, path, key, private=False):
        return key if private else "https://example.test/" + key


class FakeEngine:
    def generate(self, profile, chunks, language):
        return [(chunk, [0.0] * 2400) for chunk in chunks], 24000


def test_invalid_task(tmp_path):
    settings = replace(Settings(), data_dir=tmp_path, hf_home=tmp_path / "cache", s3_bucket="test", reference_hosts="example.com")
    worker = Worker(settings, engine=FakeEngine(), storage=FakeStorage())
    result = worker.handle({"input": {"task_type": "bad"}})
    assert result["status"] == "error"


def test_missing_style(tmp_path):
    settings = replace(Settings(), data_dir=tmp_path, hf_home=tmp_path / "cache", s3_bucket="test", reference_hosts="example.com")
    worker = Worker(settings, engine=FakeEngine(), storage=FakeStorage())
    result = worker.handle({"input": {"task_type": "tts_generate", "voice_id": "tech_narrator", "text": "Hello", "style": "calm"}})
    assert result["status"] == "error"
    assert "registered" in result["message"]


def test_local_mode_starts_without_s3_and_returns_persistent_paths(tmp_path):
    settings = replace(
        Settings(), data_dir=tmp_path / "data", hf_home=tmp_path / "hf-cache",
        output_dir=tmp_path / "outputs", s3_bucket="", reference_hosts="",
    )
    profile_dir = settings.data_dir / "voices" / "tech_narrator" / "documentary"
    profile_dir.mkdir(parents=True)
    (profile_dir / "reference.wav").write_bytes(b"private reference")
    (profile_dir / "profile.json").write_text(json.dumps({"voice_id": "tech_narrator", "style": "documentary", "created_at": "now", "reference_text": "reference"}), encoding="utf-8")

    result = Worker(settings, engine=FakeEngine()).handle({"input": {"task_type": "tts_generate", "voice_id": "tech_narrator", "text": "Hello.", "format": "wav"}})

    assert result["status"] == "completed"
    assert result["storage_mode"] == "local"
    assert result["audio_url"] is None
    assert Path(result["audio_path"]).is_file()
    assert Path(result["captions_path"]).is_file()
    assert Path(result["audio_path"]).is_relative_to(settings.output_dir)
    assert not (settings.output_dir / "private").exists()

    s3_settings = replace(settings, s3_bucket="private-bucket")
    s3_result = Worker(s3_settings, engine=FakeEngine(), storage=FakeStorage()).handle({"input": {"task_type": "tts_generate", "voice_id": "tech_narrator", "text": "Hello.", "format": "wav"}})
    assert s3_result["status"] == "completed"
    assert s3_result["storage_mode"] == "s3"
    assert s3_result["audio_url"].startswith("https://example.test/outputs/")
    assert "audio_path" not in s3_result
