import shutil

import numpy as np
import pytest

from app.alignment import write_captions
from app.audio_processor import prepare_reference, process_segments, read_wav, write_wav
from app.text_chunker import chunk_text
from app.text_normalizer import normalize


def test_multilingual_chunking():
    chunks = chunk_text("人工智能正在改变世界。GitHub projects are interesting! 下一段。", 40)
    assert len(chunks) == 3
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert "".join(chunks).replace(" ", "") == "人工智能正在改变世界。GitHubprojectsareinteresting!下一段。"


def test_versions_and_domains_are_not_split_as_sentences():
    assert chunk_text("版本 v1.2.3 已发布。GitHub.com 很有用。", 40) == ["版本 v1.2.3 已发布。", "GitHub.com 很有用。"]


def test_dictionary(tmp_path):
    path = tmp_path / "words.json"
    path.write_text('{"GitHub":"Git Hub"}', encoding="utf-8")
    assert "Git Hub" in normalize("GitHub 50%", str(path))


def test_captions_are_chunk_level(tmp_path):
    files = write_captions([{"text": "你好", "start": 0, "end": 1.25}], tmp_path)
    assert "00:00:01,250" in files["captions"].read_text(encoding="utf-8")
    assert '"audio_chunk"' in files["segments"].read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg unavailable")
def test_audio_pipeline_preserves_middle_and_raw_wav(tmp_path):
    sr = 24000
    tone = 0.15 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)
    files, segments, duration = process_segments([("测试", tone)], sr, tmp_path, 1.0, "wav")
    raw, _ = read_wav(files["raw_wav"])
    final, _ = read_wav(files["wav"])
    assert 0.9 < duration < 1.1
    assert np.sqrt(np.mean(raw[sr // 3:2 * sr // 3] ** 2)) > 0.05
    assert np.sqrt(np.mean(final[sr // 3:2 * sr // 3] ** 2)) > 0.05
    assert segments[0]["end"] > 0.9


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg unavailable")
def test_sentence_boundaries_track_rendered_audio(tmp_path):
    sr = 24000
    tone = 0.1 * np.sin(2 * np.pi * 220 * np.arange(sr // 2) / sr)
    files, segments, duration = process_segments([("第一句。", tone), ("Second sentence.", tone)], sr, tmp_path, 1.0, "wav")
    final, _ = read_wav(files["wav"])
    assert len(segments) == 2
    assert abs(segments[1]["start"] - segments[0]["end"] - 0.12) < 0.002
    assert abs(segments[1]["end"] - duration) < 0.002
    assert abs(len(final) / sr - duration) < 0.02


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg unavailable")
def test_reference_preparation_keeps_internal_pause_and_later_speech(tmp_path):
    sr = 24000
    tone = 0.15 * np.sin(2 * np.pi * 220 * np.arange(2 * sr) / sr)
    source = tmp_path / "source.wav"
    write_wav(source, np.concatenate([np.zeros(sr // 2), tone, np.zeros(sr * 2 // 5), tone, np.zeros(sr // 2)]), sr)
    target = tmp_path / "reference.wav"
    quality = prepare_reference(source, target)
    assert 4.2 < quality["duration"] < 5.1
    assert target.exists()
