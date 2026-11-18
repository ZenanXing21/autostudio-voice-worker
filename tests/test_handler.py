from dataclasses import replace
from pathlib import Path

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
