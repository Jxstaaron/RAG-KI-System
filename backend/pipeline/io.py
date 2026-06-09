from __future__ import annotations
"""Kleine Datei-Helfer für UTF-8-Text und JSON."""

import json
from pathlib import Path
from typing import Any


def read_text(path: str | Path) -> str:
    """Liest eine Textdatei mit UTF-8-Encoding."""

    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    """Schreibt Text und legt den Zielordner bei Bedarf an."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: str | Path) -> Any:
    """Liest JSON über die zentrale UTF-8-Textfunktion."""

    return json.loads(read_text(path))


def write_json(path: str | Path, data: Any) -> None:
    """Schreibt JSON lesbar eingerueckt und ohne ASCII-Zwang."""

    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
