import pytest

from app.alignment import write_captions
from app.text_chunker import chunk_text
from app.text_normalizer import normalize


def test_multilingual_chunking():
    chunks = chunk_text("人工智能正在改变世界。GitHub projects are interesting! 下一段。", 25)
    assert all(len(chunk) <= 25 for chunk in chunks)
    assert "".join(chunks).replace(" ", "") == "人工智能正在改变世界。GitHubprojectsareinteresting!下一段。"


def test_dictionary(tmp_path):
    path = tmp_path / "words.json"
    path.write_text('{"GitHub":"Git Hub"}', encoding="utf-8")
    assert "Git Hub" in normalize("GitHub 50%", str(path))


def test_captions_are_chunk_level(tmp_path):
    files = write_captions([{"text": "你好", "start": 0, "end": 1.25}], tmp_path)
    assert "00:00:01,250" in files["captions"].read_text(encoding="utf-8")
    assert '"audio_chunk"' in files["segments"].read_text(encoding="utf-8")
