from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchKey:
    roll_id: str
    source_id: str


@dataclass(frozen=True, slots=True)
class BatchIdentity:
    batch_id: int
    key: BatchKey


def make_batch_key(roll_id: str, source_id: str) -> BatchKey:
    for label, value in (("roll_id", roll_id), ("source_id", source_id)):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label} must be a nonempty string")
    return BatchKey(roll_id, source_id)
