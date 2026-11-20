from dataclasses import replace

import numpy as np
import pytest

from app.config import Settings


class FakePipeline:
    def __init__(self):
        self.references = []
        self.requests = []

    def set_ref_audio(self, path):
        self.references.append(path)

    def run(self, request):
        self.requests.append(request)
        yield 32000, np.array([0, 16384, -16384], dtype=np.int16)


def assets(tmp_path):
    model_dir = tmp_path / "models"
    for name in (
        "zenan_voice_v1-e15.ckpt", "zenan_voice_v1_e8_s160.pth",
        "pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
    ):
        path = model_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"05checkpoint" if path.suffix == ".pth" else b"checkpoint")
    for name in ("pretrained_models/chinese-roberta-wwm-ext-large", "pretrained_models/chinese-hubert-base", "G2PWModel"):
        (model_dir / name).mkdir(parents=True)
    return replace(Settings(), tts_backend="gpt_sovits", gpt_sovits_model_dir=model_dir)


def test_fixed_profile_reuses_upstream_reference(tmp_path):
    from app.gpt_sovits_engine import GPTSoVITSEngine

    settings = assets(tmp_path)
    pipeline = FakePipeline()
    configs = []

    def factory(config):
        configs.append(config)
        return pipeline

    engine = GPTSoVITSEngine(settings, pipeline_factory=factory)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"private voice")
    profile = {"voice_id": "tech_narrator", "style": "documentary", "created_at": "now", "reference_audio_path": str(reference), "reference_text": "你好，我是曾南。", "language": "Chinese"}

    waves1, sr1 = engine.generate(profile, ["第一句。", "第二句。"], "Chinese")
    waves2, sr2 = engine.generate(profile, ["Hello."], "English")

    assert sr1 == sr2 == 32000
    assert [text for text, _ in waves1 + waves2] == ["第一句。", "第二句。", "Hello."]
    assert np.allclose(waves1[0][1], [0, 0.5, -0.5])
    assert pipeline.references == [str(reference)]
    assert all(request["ref_audio_path"] is None for request in pipeline.requests)
    assert [request["text_lang"] for request in pipeline.requests] == ["zh", "zh", "en"]
    assert all(request["prompt_text"] == profile["reference_text"] for request in pipeline.requests)
    assert configs[0]["version"] == "v2Pro"
    assert configs[0]["t2s_weights_path"] == str(settings.gpt_sovits_model_dir / "zenan_voice_v1-e15.ckpt")


def test_missing_auxiliary_assets_fail_before_pipeline_load(tmp_path):
    from app.gpt_sovits_engine import GPTSoVITSEngine

    settings = replace(Settings(), tts_backend="gpt_sovits", gpt_sovits_model_dir=tmp_path)
    engine = GPTSoVITSEngine(settings, pipeline_factory=lambda _: pytest.fail("pipeline loaded"))
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"private voice")
    profile = {"voice_id": "tech_narrator", "style": "documentary", "created_at": "now", "reference_audio_path": str(reference), "reference_text": "你好", "language": "Chinese"}

    with pytest.raises(ValueError, match="GPT-SoVITS assets missing"):
        engine.generate(profile, ["你好"], "Chinese")


def test_wrong_sovits_version_is_rejected(tmp_path):
    from app.gpt_sovits_engine import GPTSoVITSEngine

    settings = assets(tmp_path)
    (settings.gpt_sovits_model_dir / "zenan_voice_v1_e8_s160.pth").write_bytes(b"01checkpoint")
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"private voice")
    profile = {"voice_id": "tech_narrator", "style": "documentary", "created_at": "now", "reference_audio_path": str(reference), "reference_text": "你好", "language": "Chinese"}

    engine = GPTSoVITSEngine(settings, pipeline_factory=lambda _: pytest.fail("pipeline loaded"))
    with pytest.raises(ValueError, match="v2Pro"):
        engine.generate(profile, ["你好"], "Chinese")
