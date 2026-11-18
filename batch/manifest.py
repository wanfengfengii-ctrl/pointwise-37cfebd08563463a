from collections.abc import Iterable
from dataclasses import dataclass

from batch.identity import BatchKey


@dataclass(frozen=True, slots=True)
class BatchManifest:
    key: BatchKey
    exposure_ids: tuple[str, ...]


def build_manifest(key: BatchKey, exposure_ids: Iterable[str]) -> BatchManifest:
    if isinstance(exposure_ids, (str, bytes)):
        raise ValueError("exposure manifest must be a sequence of exposure IDs")
    ordered = tuple(exposure_ids)
    if any(not isinstance(exposure_id, str) or not exposure_id for exposure_id in ordered):
        raise ValueError("each exposure ID must be a nonempty string")
    seen: set[str] = set()
    for exposure_id in ordered:
        if exposure_id in seen:
            raise ValueError(f"duplicate exposure ID {exposure_id!r}")
        seen.add(exposure_id)
    return BatchManifest(key, ordered)
