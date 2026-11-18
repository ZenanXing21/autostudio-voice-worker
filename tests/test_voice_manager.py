from dataclasses import replace

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
