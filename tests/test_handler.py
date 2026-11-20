from dataclasses import replace
from pathlib import Path
import json
import pytest
import sys
from types import SimpleNamespace

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


@pytest.mark.parametrize("payload", [
    {"text": "你好，这是一段测试语音。"},
    {"prompt": "你好，这是一段测试语音。"},
    {"task_type": "tts_generate", "prompt": "你好，这是一段测试语音。"},
    "你好，这是一段测试语音。",
])
def test_text_only_request_uses_default_voice(tmp_path, payload):
    settings = replace(
        Settings(), data_dir=tmp_path / "data", hf_home=tmp_path / "cache",
        output_dir=tmp_path / "outputs", s3_bucket="",
    )
    profile_dir = settings.data_dir / "voices" / "tech_narrator" / "documentary"
    profile_dir.mkdir(parents=True)
    (profile_dir / "reference.wav").write_bytes(b"private reference")
    (profile_dir / "profile.json").write_text(json.dumps({
        "voice_id": "tech_narrator", "style": "documentary",
        "created_at": "now", "reference_text": "reference",
    }), encoding="utf-8")

    result = Worker(settings, engine=FakeEngine()).handle({"input": payload})

    assert result["status"] == "completed"
    assert result["voice_id"] == "tech_narrator"
    assert Path(result["audio_path"]).is_file()


def test_missing_text_has_actionable_error(tmp_path):
    settings = replace(Settings(), data_dir=tmp_path, hf_home=tmp_path / "cache", output_dir=tmp_path / "outputs", s3_bucket="")
    result = Worker(settings, engine=FakeEngine()).handle({"input": {"task_type": "tts_generate"}})

    assert result["status"] == "error"
    assert result["error_type"] == "ValueError"
    assert "text" in result["message"]
    assert "prompt" in result["message"]


def test_missing_default_voice_explains_enrollment(tmp_path):
    settings = replace(Settings(), data_dir=tmp_path, hf_home=tmp_path / "cache", output_dir=tmp_path / "outputs", s3_bucket="")
    result = Worker(settings, engine=FakeEngine()).handle({"input": {"text": "你好"}})

    assert result["status"] == "error"
    assert "register_voice" in result["message"]
    assert "DATA_DIR" in result["message"]


def test_invalid_request_does_not_load_model(tmp_path, monkeypatch):
    settings = replace(
        Settings(), data_dir=tmp_path, hf_home=tmp_path / "cache",
        output_dir=tmp_path / "outputs", s3_bucket="",
    )

    def fail_if_loaded(_model_id):
        raise AssertionError("model loaded before request and voice validation")

    monkeypatch.setitem(sys.modules, "app.gpt_sovits_engine", SimpleNamespace(GPTSoVITSEngine=fail_if_loaded))
    worker = Worker(settings)
    result = worker.handle({"input": {"text": "你好"}})

    assert result["status"] == "error"
    assert "register_voice" in result["message"]
