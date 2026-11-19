from dataclasses import replace

import pytest

from app.config import Settings
from app.storage import LocalStorage


def test_local_storage_maps_outputs_key_and_keeps_private_voice_in_place(tmp_path):
    settings = replace(Settings(), output_dir=tmp_path / "outputs")
    source = tmp_path / "audio.wav"
    source.write_bytes(b"audio")
    storage = LocalStorage(settings)

    result = storage.upload(source, "outputs/job-1/audio.wav")
    assert result == str(settings.output_dir / "job-1" / "audio.wav")
    assert (settings.output_dir / "job-1" / "audio.wav").read_bytes() == b"audio"
    assert storage.upload(source, "private/voices/voice/reference.wav", private=True) == str(source)
    assert not (settings.output_dir / "private").exists()

    with pytest.raises(ValueError):
        storage.upload(source, "outputs/../outside.wav")
