import json
from pathlib import Path


def read_text(input_path: str | Path) -> str:
    return Path(input_path).read_text(encoding="utf-8")


def save_text(text: str, output_path: str | Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        text,
        encoding="utf-8"
    )


def read_json(input_path: str | Path):
    return json.loads(Path(input_path).read_text(encoding="utf-8"))


def save_json(data, output_path: str | Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
