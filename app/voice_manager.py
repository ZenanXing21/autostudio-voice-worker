import ipaddress
import json
import os
import re
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.audio_processor import prepare_reference


STYLES = {"documentary", "energetic", "calm", "conversational"}


def fetch_reference(url: str, destination: Path, settings):
    parsed = urlparse(url)
    hosts = {h.strip().lower() for h in settings.reference_hosts.split(",") if h.strip()}
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
        raise ValueError("reference_audio_url must use HTTPS on a configured REFERENCE_HOSTS domain")
    for info in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError("reference host resolves to a non-public address")
    with requests.get(url, stream=True, timeout=(5, 30), allow_redirects=False) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("reference download redirects are disallowed")
        size = 0
        with destination.open("wb") as out:
            for block in response.iter_content(65536):
                size += len(block)
                if size > settings.max_reference_bytes:
                    raise ValueError("reference audio exceeds size limit")
                out.write(block)
        if size == 0:
            raise ValueError("empty reference audio")


class VoiceManager:
    def __init__(self, settings, storage=None):
        self.settings = settings
        self.storage = storage
        self.root = settings.data_dir / "voices"
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths(self, voice_id, style):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", voice_id):
            raise ValueError("voice_name must contain only letters, digits, underscore or dash")
        if style not in STYLES:
            raise ValueError("unsupported style")
        directory = self.root / voice_id / style
        return directory, directory / "reference.wav", directory / "profile.json"

    def register(self, voice_name, source: Path, reference_text, language="Chinese", style="documentary"):
        if language not in {"Chinese", "English", "Auto"}:
            raise ValueError("language must be Chinese, English or Auto")
        if not isinstance(reference_text, str) or not reference_text.strip():
            raise ValueError("accurate reference_text is required")
        directory, audio, metadata = self._paths(voice_name, style)
        if metadata.exists():
            raise ValueError("voice style already exists; choose a new voice_name or style")
        directory.mkdir(parents=True, exist_ok=True)
        staged = directory / "reference.staged.wav"
        try:
            quality = prepare_reference(source, staged)
            os.replace(staged, audio)
            profile = {"voice_id": voice_name, "voice_name": voice_name, "reference_audio_path": audio.name, "reference_text": reference_text.strip(), "language": language, "style": style, "created_at": datetime.now(timezone.utc).isoformat(), "quality": quality}
            temp_meta = metadata.with_suffix(".tmp")
            temp_meta.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp_meta, metadata)
            if self.storage:
                try:
                    self.storage.upload(audio, f"private/voices/{voice_name}/{style}/reference.wav", private=True)
                    self.storage.upload(metadata, f"private/voices/{voice_name}/{style}/profile.json", private=True)
                except Exception:
                    metadata.unlink(missing_ok=True)
                    audio.unlink(missing_ok=True)
                    raise
            return {**profile, "reference_audio_path": str(audio)}
        finally:
            staged.unlink(missing_ok=True)

    def get(self, voice_id, style="documentary"):
        _, audio, metadata = self._paths(voice_id, style)
        if not metadata.exists() or not audio.exists():
            raise ValueError(f"voice {voice_id!r} has no registered {style!r} reference")
        profile = json.loads(metadata.read_text(encoding="utf-8"))
        profile["reference_audio_path"] = str(audio)
        return profile

    def list_profiles(self):
        return [str(p.relative_to(self.root)) for p in self.root.glob("*/*/profile.json")]
