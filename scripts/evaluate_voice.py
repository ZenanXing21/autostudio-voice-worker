"""Generate local review clips; human scores remain blank until listening."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from app.alignment import write_captions
from app.audio_processor import process_segments
from app.config import Settings
from app.gpt_sovits_engine import GPTSoVITSEngine
from app.text_chunker import chunk_text
from app.voice_manager import VoiceManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path("/app/evaluation/cases.json"))
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    settings = replace(Settings(), data_dir=args.data_dir)
    profile = VoiceManager(settings).get("tech_narrator", "documentary")
    engine = GPTSoVITSEngine(settings)
    manifest = []
    for case in cases:
        destination = args.output_dir / case["id"]
        chunks = chunk_text(case["text"], settings.chunk_chars)
        waves, source_rate = engine.generate(profile, chunks, case["language"])
        files, segments, duration = process_segments(waves, source_rate, destination, 1.0, "wav")
        files.update(write_captions(segments, destination))
        manifest.append({"id": case["id"], "duration": duration, "audio": str(files["wav"])})
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
