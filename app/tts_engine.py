import torch


class TTSEngine:
    def __init__(self, model_id: str):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is required")
        from qwen_tts import Qwen3TTSModel
        major, _ = torch.cuda.get_device_capability()
        dtype = torch.bfloat16 if major >= 8 else torch.float16
        self.model = Qwen3TTSModel.from_pretrained(model_id, device_map="cuda:0", dtype=dtype, attn_implementation="sdpa")
        self.prompt_cache = {}

    def generate(self, profile: dict, chunks: list[str], language: str):
        if language not in {"Chinese", "English", "Auto"}:
            raise ValueError("language must be Chinese, English or Auto")
        key = (profile["voice_id"], profile["style"], profile["created_at"])
        if key not in self.prompt_cache:
            self.prompt_cache[key] = self.model.create_voice_clone_prompt(ref_audio=profile["reference_audio_path"], ref_text=profile["reference_text"], x_vector_only_mode=False)
        results = []
        sr = None
        for chunk in chunks:
            try:
                wavs, sr = self.model.generate_voice_clone(text=chunk, language=language, voice_clone_prompt=self.prompt_cache[key])
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                raise RuntimeError("GPU out of memory; shorten CHUNK_CHARS or use a larger GPU")
            results.append((chunk, wavs[0]))
        return results, sr
