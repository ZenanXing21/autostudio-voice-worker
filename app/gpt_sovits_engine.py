"""Fixed-reference adapter for the unmodified GPT-SoVITS v2Pro inference pipeline."""

import os
import sys
from pathlib import Path
from threading import Lock

import numpy as np


LANGUAGES = {"Chinese": "zh", "English": "en", "Auto": "auto"}


class GPTSoVITSEngine:
    def __init__(self, settings, pipeline_factory=None):
        self.settings = settings
        self.pipeline_factory = pipeline_factory or self._create_pipeline
        self.pipeline = None
        self.profile_key = None
        self.lock = Lock()

    def _assets(self):
        root = self.settings.gpt_sovits_model_dir
        files = {
            "t2s_weights_path": root / "zenan_voice_v1-e15.ckpt",
            "vits_weights_path": root / "zenan_voice_v1_e8_s160.pth",
            "sv": root / "pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
        }
        dirs = {
            "bert_base_path": root / "pretrained_models/chinese-roberta-wwm-ext-large",
            "cnhuhbert_base_path": root / "pretrained_models/chinese-hubert-base",
            "g2pw": root / "G2PWModel",
        }
        missing = [str(path) for path in files.values() if not path.is_file()]
        missing += [str(path) for path in dirs.values() if not path.is_dir()]
        if missing:
            raise ValueError("GPT-SoVITS assets missing from GPT_SOVITS_MODEL_DIR: " + ", ".join(missing))
        with files["vits_weights_path"].open("rb") as checkpoint:
            if checkpoint.read(2) != b"05":
                raise ValueError("SoVITS checkpoint is not a v2Pro fine-tuned weight (expected upstream 05 header)")
        return {
            "version": "v2Pro",
            "device": "cuda",
            "is_half": True,
            "t2s_weights_path": str(files["t2s_weights_path"]),
            "vits_weights_path": str(files["vits_weights_path"]),
            "bert_base_path": str(dirs["bert_base_path"]),
            "cnhuhbert_base_path": str(dirs["cnhuhbert_base_path"]),
        }

    def _create_pipeline(self, config):
        source = self.settings.gpt_sovits_source_dir
        if not (source / "GPT_SoVITS/TTS_infer_pack/TTS.py").is_file():
            raise ValueError(f"GPT-SoVITS source missing at {source}; check GPT_SOVITS_SOURCE_DIR")
        model_dir = self.settings.gpt_sovits_model_dir.resolve()
        for link, target in (
            (source / "GPT_SoVITS/pretrained_models", model_dir / "pretrained_models"),
            (source / "GPT_SoVITS/text/G2PWModel", model_dir / "G2PWModel"),
        ):
            if link.is_symlink():
                if link.resolve() != target:
                    raise ValueError(f"GPT-SoVITS asset link points to the wrong volume: {link}")
            elif link.exists():
                raise ValueError(f"GPT-SoVITS asset path must be a volume link: {link}")
            else:
                link.symlink_to(target, target_is_directory=True)
        os.chdir(source)
        for path in (source, source / "GPT_SoVITS"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from TTS_infer_pack.TTS import TTS, TTS_Config

        return TTS(TTS_Config({"custom": config}))

    def generate(self, profile: dict, chunks: list[str], language: str):
        if language not in LANGUAGES:
            raise ValueError("language must be Chinese, English or Auto")
        reference = Path(profile["reference_audio_path"])
        if not reference.is_file():
            raise ValueError("fixed voice reference missing in DATA_DIR; run register_voice once")
        with self.lock:
            if self.pipeline is None:
                self.pipeline = self.pipeline_factory(self._assets())
            key = (profile["voice_id"], profile["style"], profile["created_at"])
            if key != self.profile_key:
                self.pipeline.set_ref_audio(str(reference))
                self.profile_key = key
            results = []
            sample_rate = None
            for chunk in chunks:
                request = {
                    "text": chunk,
                    "text_lang": LANGUAGES[language],
                    "ref_audio_path": None,
                    "prompt_text": profile["reference_text"],
                    "prompt_lang": LANGUAGES[profile["language"]],
                    "text_split_method": "cut0",
                    "batch_size": 1,
                    "parallel_infer": False,
                    "use_cuda_graph": False,
                    "use_flash_attention": False,
                }
                parts = []
                for sr, audio in self.pipeline.run(request):
                    if sample_rate is not None and sr != sample_rate:
                        raise RuntimeError("GPT-SoVITS returned inconsistent sample rates")
                    sample_rate = sr
                    samples = np.asarray(audio)
                    if samples.dtype == np.int16:
                        samples = samples.astype(np.float32) / 32768.0
                    else:
                        samples = samples.astype(np.float32)
                    parts.append(samples.reshape(-1))
                if not parts:
                    raise RuntimeError("GPT-SoVITS returned no audio")
                results.append((chunk, np.concatenate(parts)))
            return results, sample_rate
