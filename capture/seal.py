from collections.abc import Mapping
from dataclasses import dataclass


class SealError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Seal:
    latch_count: int

    def __post_init__(self) -> None:
        if type(self.latch_count) is not int or self.latch_count < 0:
            raise SealError("latch_count must be a nonnegative integer")


def parse_seal(record: Mapping[str, object]) -> Seal:
    if set(record) != {"kind", "latch_count"} or record.get("kind") != "seal":
        raise SealError("invalid terminal seal marker")
    return Seal(record["latch_count"])


def require_terminal_seal(record: object) -> Seal:
    if record is None:
        raise SealError("missing terminal seal")
    if not isinstance(record, Mapping):
        raise SealError("terminal seal must be an object")
    return parse_seal(record)
