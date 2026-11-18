from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ControlEvent:
    tick: int
    kind: Literal["open", "close"]
    exposure_id: str
    event_id: str | None = None


@dataclass(frozen=True, slots=True)
class SampleEvent:
    tick: int
    event_id: str
    value: int


@dataclass(frozen=True, slots=True)
class SampleOrigin:
    evidence_id: int
    sample_index: int
    event_id: str


def _read_int(record: Mapping[str, object], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer")
    return value


def _read_name(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string")
    return value


def parse_control_event(record: Mapping[str, object]) -> ControlEvent:
    if set(record) - {"tick", "kind", "exposure_id", "event_id"}:
        raise ValueError("unknown control event field")
    kind = record.get("kind")
    if kind not in ("open", "close"):
        raise ValueError("control kind must be open or close")
    event_id = None if record.get("event_id") is None else _read_name(record, "event_id")
    return ControlEvent(_read_int(record, "tick"), kind, _read_name(record, "exposure_id"), event_id)


def parse_sample_event(record: Mapping[str, object]) -> SampleEvent:
    if set(record) - {"tick", "event_id", "value"}:
        raise ValueError("unknown sample event field")
    return SampleEvent(_read_int(record, "tick"), _read_name(record, "event_id"), _read_int(record, "value"))
