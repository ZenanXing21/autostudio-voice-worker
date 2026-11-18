def chunk_text(text: str, limit: int = 180) -> list[str]:
    if limit < 20:
        raise ValueError("chunk limit must be at least 20")
    sentences = []
    start = 0
    for index, character in enumerate(text):
        next_character = text[index + 1] if index + 1 < len(text) else ""
        boundary = character in "。！？；!?;" or (character == "." and (not next_character or next_character.isspace() or "\u4e00" <= next_character <= "\u9fff"))
        if boundary:
            sentences.append(text[start:index + 1])
            start = index + 1
    if start < len(text):
        sentences.append(text[start:])
    out = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > limit:
            boundary = max(sentence.rfind("，", 0, limit), sentence.rfind(",", 0, limit), sentence.rfind(" ", 0, limit))
            boundary = boundary + 1 if boundary >= limit // 2 else limit
            out.append(sentence[:boundary].strip())
            sentence = sentence[boundary:].strip()
        if sentence:
            out.append(sentence)
    return out
