from __future__ import annotations
"""Einfache Token-/Wortzählung für Chunk-Größen."""

import re


def count_tokens(text: str) -> int:
    """Zählt grob Wörter und Satzzeichen als Tokens."""

    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def count_words(text: str) -> int:
    """Zählt nur Wortbestandteile."""

    return len(re.findall(r"\w+", text, flags=re.UNICODE))
