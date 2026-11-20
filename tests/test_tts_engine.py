import runpy
import sys
from pathlib import Path
from types import SimpleNamespace


def test_engine_uses_fp16_when_gpu_does_not_support_bf16(monkeypatch):
    selected = {}

    class FakeQwenModel:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            selected.update(kwargs)
            return cls()

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True, is_bf16_supported=lambda: False),
        float16="fp16", bfloat16="bf16",
    ))
    monkeypatch.setitem(sys.modules, "qwen_tts", SimpleNamespace(Qwen3TTSModel=FakeQwenModel))

    engine_class = runpy.run_path(str(Path(__file__).parents[1] / "app" / "tts_engine.py"))["TTSEngine"]
    engine_class("Qwen/Qwen3-TTS-12Hz-1.7B-Base")

    assert selected["dtype"] == "fp16"
    assert selected["attn_implementation"] == "sdpa"
