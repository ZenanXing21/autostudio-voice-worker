import json
import re
from pathlib import Path


def normalize(text: str, dictionary_path: str | None = None) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be nonempty")
    text = text.replace("\r", " ").replace("\n", " ").replace("％", "%")
    text = re.sub(r"\s+", " ", text).strip()
    if dictionary_path and Path(dictionary_path).exists():
        words = json.loads(Path(dictionary_path).read_text(encoding="utf-8"))
        for source, spoken in sorted(words.items(), key=lambda item: -len(item[0])):
            text = re.sub(re.escape(source), spoken, text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)%", " percent", text) if not re.search(r"[\u4e00-\u9fff]", text) else re.sub(r"(?<=\d)%", "百分比", text)
    return text
