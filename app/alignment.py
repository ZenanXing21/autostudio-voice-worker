import json
from pathlib import Path


def _stamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def write_captions(segments: list[dict], workdir: Path):
    (workdir / "segments.json").write_text(json.dumps({"alignment_level": "audio_chunk", "segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
    srt = "\n\n".join(f"{i + 1}\n{_stamp(s['start'])} --> {_stamp(s['end'])}\n{s['text']}" for i, s in enumerate(segments)) + "\n"
    (workdir / "captions.srt").write_text(srt, encoding="utf-8")
    return {"segments": workdir / "segments.json", "captions": workdir / "captions.srt"}
