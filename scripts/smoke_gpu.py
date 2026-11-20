"""Offline GPU smoke test; writes only to the requested local directory."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from app.alignment import write_captions
from app.audio_processor import process_segments
from app.config import Settings
from app.text_chunker import chunk_text
from app.gpt_sovits_engine import GPTSoVITSEngine
from app.voice_manager import VoiceManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--voice-id", default="tech_narrator")
    parser.add_argument("--style", default="documentary")
    parser.add_argument("--text", default="人工智能正在改变世界。")
    parser.add_argument("--language", default="Chinese")
    parser.add_argument("--format", default="wav", choices=["wav", "mp3"])
    args = parser.parse_args()
    settings = replace(Settings(), data_dir=args.data_dir)
    profile = VoiceManager(settings).get(args.voice_id, args.style)
    engine = GPTSoVITSEngine(settings)
    chunks = chunk_text(args.text, settings.chunk_chars)
    waves, sample_rate = engine.generate(profile, chunks, args.language)
    files, segments, duration = process_segments(waves, sample_rate, args.output_dir, 1.0, args.format)
    files.update(write_captions(segments, args.output_dir))
    print(json.dumps({"files": {key: str(path) for key, path in files.items()}, "duration": duration, "segments": segments}, ensure_ascii=False))


if __name__ == "__main__":
    main()
