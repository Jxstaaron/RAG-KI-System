from __future__ import annotations

import re


def count_tokens(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))
