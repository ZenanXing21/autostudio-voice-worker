from dataclasses import replace
import json
import shutil

import pytest

from app.config import Settings
from app.voice_manager import VoiceManager


def test_voice_name_cannot_traverse(tmp_path):
    manager = VoiceManager(replace(Settings(), data_dir=tmp_path))
    with pytest.raises(ValueError):
        manager.get("../secret")


def test_missing_profile(tmp_path):
    manager = VoiceManager(replace(Settings(), data_dir=tmp_path))
    with pytest.raises(ValueError, match="no registered"):
        manager.get("tech_narrator")


def test_registered_profile_survives_volume_move(tmp_path, monkeypatch):
    def fake_prepare_reference(source, destination):
        destination.write_bytes(b"reference audio")
        return {"duration": 8.8}

    monkeypatch.setattr("app.voice_manager.prepare_reference", fake_prepare_reference)
    first = tmp_path / "first"
    manager = VoiceManager(replace(Settings(), data_dir=first))
    manager.register("tech_narrator", tmp_path / "input.m4a", "准确参考文本")

    metadata = first / "voices" / "tech_narrator" / "documentary" / "profile.json"
    assert json.loads(metadata.read_text(encoding="utf-8"))["reference_audio_path"] == "reference.wav"

    second = tmp_path / "second"
    shutil.copytree(first, second)
    moved = VoiceManager(replace(Settings(), data_dir=second)).get("tech_narrator")
    assert moved["reference_audio_path"] == str(second / "voices" / "tech_narrator" / "documentary" / "reference.wav")
