import re


def chunk_text(text: str, limit: int = 180) -> list[str]:
    if limit < 20:
        raise ValueError("chunk limit must be at least 20")
    sentences = re.findall(r"[^。！？.!?；;]+[。！？.!?；;]*", text)
    out, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) <= limit:
            current += sentence
            continue
        if current:
            out.append(current)
            current = ""
        while len(sentence) > limit:
            boundary = max(sentence.rfind("，", 0, limit), sentence.rfind(",", 0, limit), sentence.rfind(" ", 0, limit))
            boundary = boundary + 1 if boundary >= limit // 2 else limit
            out.append(sentence[:boundary].strip())
            sentence = sentence[boundary:].strip()
        current = sentence
    if current:
        out.append(current)
    return out
