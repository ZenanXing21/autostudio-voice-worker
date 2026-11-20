# Fixed voice GPT-SoVITS v2Pro design

## Goal

Serve the owner's trained GPT and SoVITS checkpoints through the existing RunPod queue worker. After a one-time private voice enrollment, requests contain only text. No decoder redesign or additional training is required for this deployment mode.

## Evidence and model boundary

- The supplied GPT checkpoint is a Text2Semantic checkpoint with `weight` and `config`.
- The supplied SoVITS checkpoint has upstream's `05` prefix, which identifies v2Pro. Its embedded config says `model.version=v2Pro`, 32 kHz output, and 25 Hz semantic frames. Upstream `load_sovits_new` restores the ZIP header in memory before loading. The original file is valid and must not be rewritten.
- In upstream commit `6d51ffceafbf240145619af4c92408a6e54b7924`, `TTS.set_ref_audio()` computes prompt semantic tokens and reference spectrogram. During v2Pro inference `SV.compute_embedding3()` derives a speaker embedding from the cached reference audio; the unmodified SoVITS decoder combines the embedding with the reference encoder output.
- The two personal checkpoints do not contain the public Chinese RoBERTa, CNHuBERT, ERes2Net speaker verification, or G2PW assets. These are runtime dependencies on a private/persistent volume, not part of the public image.

## Runtime

The image includes code and official CUDA PyTorch wheels, but no personal audio or weights. It carries a pinned MIT-licensed GPT-SoVITS source checkout. The worker validates the volume paths, loads the private checkpoints once, calls upstream `set_ref_audio` once per fixed profile, and sends text plus fixed prompt text/language to upstream `TTS.run`. Upstream `ref_audio_path` is omitted after caching. The existing audio processor normalizes and exports WAV/MP3, and the existing storage layer returns local paths or presigned S3 URLs.

The API accepts `{"input":{"text":"..."}}`; `task_type`, `voice_id`, and `language` have defaults. Enrollment still requires a private reference recording with an accurate transcript. A volume and credentials remain outside Git/GHCR.

## Verification

Unit tests cover request defaults, missing assets, path mapping, reference reuse, and response files. A container build checks dependency installation and import. Real v2Pro audio, naturalness, similarity, and pronunciation require the public auxiliary models and the private files on a GPU volume; those measurements must not be claimed before playback and review.

## Sources

- [GPT-SoVITS TTS pipeline](https://github.com/RVC-Boss/GPT-SoVITS/blob/6d51ffceafbf240145619af4c92408a6e54b7924/GPT_SoVITS/TTS_infer_pack/TTS.py)
- [GPT-SoVITS checkpoint loader](https://github.com/RVC-Boss/GPT-SoVITS/blob/6d51ffceafbf240145619af4c92408a6e54b7924/GPT_SoVITS/process_ckpt.py)
- [GPT-SoVITS decoder](https://github.com/RVC-Boss/GPT-SoVITS/blob/6d51ffceafbf240145619af4c92408a6e54b7924/GPT_SoVITS/module/models.py)
