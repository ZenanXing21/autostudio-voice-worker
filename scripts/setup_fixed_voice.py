"""Stage the owner's checkpoints and reference on a private persistent volume."""

import argparse
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from app.config import Settings
from app.voice_manager import VoiceManager


def copy_new(source: Path, destination: Path):
    if destination.exists():
        raise FileExistsError(f"private checkpoint already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
    os.chmod(destination, 0o600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpt", type=Path, required=True)
    parser.add_argument("--sovits", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True, help="3–10 second WAV/MP3/M4A clip")
    parser.add_argument("--reference-text", required=True, help="exact words spoken in the reference clip")
    parser.add_argument("--model-dir", type=Path, default=Path("/runpod-volume/gpt-sovits"))
    parser.add_argument("--data-dir", type=Path, default=Path("/runpod-volume/autostudio"))
    args = parser.parse_args()

    with args.sovits.open("rb") as checkpoint:
        if checkpoint.read(2) != b"05":
            raise ValueError("SoVITS file is not upstream v2Pro format (expected 05 header)")
    with args.gpt.open("rb") as checkpoint:
        if checkpoint.read(2) != b"PK":
            raise ValueError("GPT checkpoint is not a PyTorch ZIP checkpoint")
    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(args.reference),
    ], text=True).strip())
    if not 3 <= duration <= 10:
        raise ValueError("GPT-SoVITS reference must be 3–10 seconds")
    targets = [
        args.model_dir / "zenan_voice_v1-e15.ckpt",
        args.model_dir / "zenan_voice_v1_e8_s160.pth",
        args.data_dir / "voices/tech_narrator/documentary/profile.json",
    ]
    if any(path.exists() for path in targets):
        raise FileExistsError("fixed voice assets already exist; choose an empty volume or inspect the existing profile")
    copy_new(args.gpt, args.model_dir / "zenan_voice_v1-e15.ckpt")
    copy_new(args.sovits, args.model_dir / "zenan_voice_v1_e8_s160.pth")
    settings = replace(Settings(), data_dir=args.data_dir, s3_bucket="")
    profile = VoiceManager(settings).register(
        "tech_narrator", args.reference, args.reference_text, "Chinese", "documentary"
    )
    print(f"Private v2Pro checkpoints and {profile['voice_id']} profile staged on the volume")


if __name__ == "__main__":
    main()
