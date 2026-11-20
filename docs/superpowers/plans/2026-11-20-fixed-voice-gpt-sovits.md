# Fixed voice GPT-SoVITS v2Pro implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default Qwen inference backend with the owner's v2Pro GPT-SoVITS checkpoints while keeping text-only RunPod requests.

**Architecture:** Use pinned upstream GPT-SoVITS inference code unmodified. The worker owns private checkpoint/profile paths, calls `set_ref_audio` once, and reuses upstream `TTS.run` for every text chunk. Existing output and storage code remains responsible for WAV/MP3 and URLs.

**Tech Stack:** Python 3.12, official PyTorch CUDA 12.6 wheels, GPT-SoVITS v2Pro, RunPod queue worker, FFmpeg.

**Spec:** [design](../../gpt-sovits-v2pro-design.md)

## Global constraints

- Never include the user's `.ckpt`, `.pth`, or recording in Git or Docker layers.
- The original upstream decoder and checkpoint bytes remain untouched.
- The fixed reference must be 3–10 seconds with an accurate transcript.
- Fail with a clear missing-volume-assets error before loading models.
- Build and publish the image only after implementation and tests.

## Review focus

- A missing `input.text` returns a useful validation error.
- A wrong or absent v2Pro checkpoint cannot silently fall back to a public voice.
- Missing public BERT, HuBERT, SV, or G2PW files are reported as dependencies.
- Repeated text jobs reuse the fixed reference on the same worker.
- A local file path is never represented as a public URL.

### Task 1: Backend and request integration

**Files:** `app/gpt_sovits_engine.py`, `app/handler.py`, `app/config.py`, `tests/test_gpt_sovits_engine.py`, `tests/test_handler.py`.

**Interfaces:** `GPTSoVITSEngine(settings).generate(profile, chunks, language) -> ([(text, float_audio)], source_sample_rate)`.

- [ ] Write a failing test with a fake upstream TTS that verifies checkpoint paths, one `set_ref_audio`, text-only requests, language mapping, and no per-request reference upload.
- [ ] Run the focused tests and confirm the failure is due to the missing backend.
- [ ] Implement the backend and select it as the default in the worker.
- [ ] Run focused and full tests, then commit.

### Task 2: Reproducible private-volume image

**Files:** `Dockerfile`, `requirements.txt`, `scripts/download_gpt_sovits_models.py`, `.env.example`, `.dockerignore`, `README.md`.

**Interfaces:** Private assets under `GPT_SOVITS_MODEL_DIR`; source under `GPT_SOVITS_SOURCE_DIR`; RunPod handler remains `python -u handler.py`.

- [ ] Add a test or static check for asset paths and source revision.
- [ ] Add pinned upstream source and inference dependencies without private assets.
- [ ] Document volume layout and one-time reference registration.
- [ ] Verify no private files enter the build context.
- [ ] Run full tests, compile, and Docker build; fix only observed failures.

### Task 3: Publish and smoke check

**Files:** `.github/workflows/publish-image.yml`, `README.md`.

- [ ] Check the actual image command and CUDA wheel in the built container.
- [ ] Push the validated commit and inspect GitHub Actions image publication.
- [ ] If RunPod credentials and required volume files are available, run a real GPU job; otherwise state the exact missing prerequisite and do not claim voice quality validation.
