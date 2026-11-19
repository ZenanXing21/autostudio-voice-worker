import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from api import create_app
from app.config import Settings
from app.handler import Worker


class FakeEngine:
    def generate(self, profile, chunks, language):
        return [(chunk, [0.1] * 2400) for chunk in chunks], 24000


def test_pod_api_generates_and_protects_real_output(tmp_path):
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
    app = create_app(worker_factory=lambda: Worker(settings, engine=FakeEngine()), api_token="test-token")

    with TestClient(app) as client:
        assert client.get("/health").json()["ready"] is True
        assert client.post("/tts", json={"text": "你好。"}).status_code == 401
        response = client.post(
            "/tts", headers={"Authorization": "Bearer test-token"},
            json={"text": "你好。", "voice": "tech_narrator", "format": "wav", "job_id": "job-001"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "completed"
        assert result["job_id"] == "job-001"
        assert result["audio_url"].endswith("/audio.wav")
        assert Path(result["audio_path"]).is_file()
        download_path = urlsplit(result["audio_url"]).path
        assert client.get(download_path).status_code == 401
        audio = client.get(download_path, headers={"Authorization": "Bearer test-token"})
        assert audio.status_code == 200
        assert audio.content.startswith(b"RIFF")
        assert "no-store" in audio.headers.get("cache-control", "")
        assert client.get(download_path.replace("audio.wav", "reference.wav"), headers={"Authorization": "Bearer test-token"}).status_code == 404
