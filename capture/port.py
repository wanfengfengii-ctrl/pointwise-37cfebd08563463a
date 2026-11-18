import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RecordingFormatError(ValueError):
    pass


class ClosedRecordingPort(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PortRecording:
    source_id: str
    control: tuple[Mapping[str, object], ...]
    samples: tuple[Mapping[str, object], ...]
    terminal_seal: object


class RecordingPort(Protocol):
    def read(self) -> PortRecording:
        """Read one complete offline recording from the open port."""
        raise NotImplementedError

    def close(self) -> None:
        """End the lifetime of the input port."""
        raise NotImplementedError


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {}
    for key, value in pairs:
        if key in record:
            raise RecordingFormatError(f"duplicate recording field {key!r}")
        record[key] = value
    return record


def _read_channel(document: dict[str, object], key: str) -> tuple[Mapping[str, object], ...]:
    channel = document.get(key)
    if not isinstance(channel, list) or any(not isinstance(event, dict) for event in channel):
        raise RecordingFormatError(f"{key} must be an array of event objects")
    return tuple(channel)


class OfflineRecordingPort:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._closed = False

    def read(self) -> PortRecording:
        if self._closed:
            raise ClosedRecordingPort(f"recording port is closed: {self.path.name}")
        try:
            with self.path.open(encoding="utf-8") as stream:
                document = json.load(stream, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise RecordingFormatError(f"invalid recording JSON: {error}") from error
        if not isinstance(document, dict) or set(document) - {"source_id", "control", "samples", "seal"}:
            raise RecordingFormatError("invalid recording envelope")
        source = document.get("source_id")
        if not isinstance(source, str) or not source:
            raise RecordingFormatError("source_id must be a nonempty string")
        return PortRecording(
            source, _read_channel(document, "control"), _read_channel(document, "samples"), document.get("seal")
        )

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> 'OfflineRecordingPort':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
