import re


TOKEN_RE = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)
WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


def estimate_token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))
