import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from batch.registry import BatchRegistry, RegisteredBatch
from capture.channel import RecordedChannels
from capture.events import parse_control_event, parse_sample_event
from capture.seal import Seal, parse_seal


class UnknownEvidence(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class FixedEvidence:
    evidence_id: int
    batch: RegisteredBatch
    channels: RecordedChannels
    seal: Seal


class EvidenceArchive:
    def __init__(self, path: str | Path):
        self.path = path
        self._registry = BatchRegistry(path)

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id INTEGER PRIMARY KEY,
                    batch_id INTEGER NOT NULL REFERENCES batches (batch_id),
                    payload TEXT NOT NULL
                )"""
            )

    def store(self, batch_id: int, channels: RecordedChannels, seal: Seal) -> int:
        """Persist channels already validated against the immutable batch manifest."""
        payload = json.dumps({
            "control": [asdict(event) for event in channels.control],
            "samples": [asdict(event) for event in channels.samples],
            "seal": {"kind": "seal", "latch_count": seal.latch_count},
        })
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            inserted = connection.execute(
                "INSERT INTO evidence (batch_id, payload) VALUES (?, ?)", (batch_id, payload)
            )
            evidence_id = inserted.lastrowid
        return evidence_id

    def get(self, evidence_id: int) -> FixedEvidence:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT batch_id, payload FROM evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if row is None:
            raise UnknownEvidence(evidence_id)
        batch_id, payload = row
        document = json.loads(payload)
        channels = RecordedChannels(
            tuple(parse_control_event(event) for event in document["control"]),
            tuple(parse_sample_event(event) for event in document["samples"]),
        )
        return FixedEvidence(evidence_id, self._registry.get(batch_id), channels, parse_seal(document["seal"]))

    def evidence_ids(self) -> tuple[int, ...]:
        with closing(sqlite3.connect(self.path)) as connection:
            return tuple(
                row[0] for row in connection.execute("SELECT evidence_id FROM evidence ORDER BY evidence_id")
            )
