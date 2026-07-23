from dataclasses import dataclass, field


@dataclass(slots=True)
class IngestionError(Exception):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message
