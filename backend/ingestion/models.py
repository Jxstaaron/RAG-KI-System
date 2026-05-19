from dataclasses import asdict, dataclass


@dataclass
class StructuredBlock:
    type: str
    text: str
    index: int
    heading: str | None = None
    token_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class Chunk:
    id: int
    heading: str | None
    text: str
    token_count: int
    word_count: int
    block_start: int
    block_end: int
    context_before: str
    context_after: str
    text_with_context: str

    def to_dict(self) -> dict:
        return asdict(self)
