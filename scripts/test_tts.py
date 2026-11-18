import argparse
import json

from app.handler import Worker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--voice-id", default="tech_narrator")
    parser.add_argument("--language", default="Auto")
    parser.add_argument("--format", default="wav")
    args = parser.parse_args()
    print(json.dumps(Worker().handle({"input": {"task_type": "tts_generate", "voice_id": args.voice_id, "text": args.text, "language": args.language, "format": args.format}}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
