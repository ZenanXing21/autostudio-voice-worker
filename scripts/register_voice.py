import argparse
import json
from pathlib import Path

from app.config import Settings
from app.voice_manager import VoiceManager


def main():
    parser = argparse.ArgumentParser(description="Register a private, locally held voice reference")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--voice-name", default="tech_narrator")
    parser.add_argument("--reference-text", required=True)
    parser.add_argument("--language", default="Chinese", choices=["Chinese", "English", "Auto"])
    parser.add_argument("--style", default="documentary", choices=["documentary", "energetic", "calm", "conversational"])
    args = parser.parse_args()
    profile = VoiceManager(Settings()).register(args.voice_name, args.audio, args.reference_text, args.language, args.style)
    print(json.dumps(profile, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
