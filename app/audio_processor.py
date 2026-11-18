import json
import math
import subprocess
from pathlib import Path

def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True, capture_output=True)


def prepare_reference(source: Path, destination: Path) -> dict:
    import numpy as np
    import soundfile as sf
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", source, "-vn", "-af", "highpass=f=70,lowpass=f=10000,silenceremove=start_periods=1:start_silence=0.15:start_threshold=-45dB:stop_periods=1:stop_silence=0.15:stop_threshold=-45dB,loudnorm=I=-19:TP=-2:LRA=9", "-ac", "1", "-ar", "24000", destination)
    samples, sr = sf.read(destination, dtype="float32")
    if samples.ndim != 1 or len(samples) == 0:
        raise ValueError("reference audio must contain mono speech")
    duration = len(samples) / sr
    if not 3 <= duration <= 20:
        raise ValueError("reference speech must be 3–20 seconds after trimming")
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples ** 2)))
    frame = max(1, int(sr * 0.02))
    levels = np.array([np.sqrt(np.mean(samples[i:i + frame] ** 2)) for i in range(0, len(samples), frame)])
    silence_ratio = float(np.mean(levels < 0.003))
    noise_floor = float(np.percentile(levels, 15))
    snr_proxy = 20 * math.log10(max(rms, 1e-8) / max(noise_floor, 1e-8))
    if rms < 0.01 or peak > 0.999 or silence_ratio > 0.45 or (silence_ratio > 0.03 and snr_proxy < 8):
        raise ValueError("reference failed level, clipping, silence, or noise screening; use a clean recording")
    return {"duration": round(duration, 3), "rms": round(rms, 4), "peak": round(peak, 4), "silence_ratio": round(silence_ratio, 3), "snr_proxy_db": round(snr_proxy, 1)}


def process_segments(waves, sample_rate: int, workdir: Path, speed: float, output_format: str):
    import numpy as np
    import soundfile as sf
    if not 0.75 <= speed <= 1.5:
        raise ValueError("speed must be between 0.75 and 1.5")
    if output_format not in {"wav", "mp3"}:
        raise ValueError("format must be wav or mp3")
    workdir.mkdir(parents=True, exist_ok=True)
    processed, segments, cursor = [], [], 0.0
    pause = 0.12
    for index, (text, wave) in enumerate(waves):
        raw = workdir / f"raw_{index}.wav"
        clip = workdir / f"clip_{index}.wav"
        sf.write(raw, np.asarray(wave, dtype="float32"), sample_rate)
        expected_duration = len(wave) / sample_rate / speed
        fade_out_start = max(0.0, expected_duration - 0.02)
        ffmpeg("-i", raw, "-af", f"atempo={speed},afade=t=in:st=0:d=0.015,afade=t=out:st={fade_out_start:.3f}:d=0.02", "-ar", "24000", "-ac", "1", clip)
        signal, sr = sf.read(clip, dtype="float32")
        duration = len(signal) / sr
        segments.append({"index": index, "text": text, "start": round(cursor, 3), "end": round(cursor + duration, 3), "timing_basis": "generated_audio_chunk"})
        processed.append(signal)
        cursor += duration
        if index < len(waves) - 1:
            processed.append(np.zeros(round(pause * sr), dtype="float32"))
            cursor += pause
    joined = np.concatenate(processed)
    raw_wav = workdir / "audio_raw.wav"
    final_wav = workdir / "audio.wav"
    sf.write(raw_wav, joined, 24000)
    ffmpeg("-i", raw_wav, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "24000", "-ac", "1", final_wav)
    files = {"wav": final_wav, "raw_wav": raw_wav}
    if output_format == "mp3":
        mp3 = workdir / "audio.mp3"
        ffmpeg("-i", final_wav, "-codec:a", "libmp3lame", "-b:a", "192k", mp3)
        files["mp3"] = mp3
    return files, segments, len(joined) / 24000
