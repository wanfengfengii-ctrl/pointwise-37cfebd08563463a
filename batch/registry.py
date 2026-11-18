import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from batch.admission import RegistrationDecision, decide_registration
from batch.identity import BatchIdentity, make_batch_key
from batch.manifest import BatchManifest, build_manifest


class UnknownBatch(KeyError):
    pass


class RegistrationConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredBatch:
    identity: BatchIdentity
    manifest: BatchManifest


class BatchRegistry:
    def __init__(self, path: str | Path):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS batches (
                    batch_id INTEGER PRIMARY KEY,
                    roll_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    exposure_ids TEXT NOT NULL,
                    UNIQUE (roll_id, source_id)
                )"""
            )

    def register(self, roll_id: str, source_id: str, exposure_ids: Iterable[str]) -> int:
        key = make_batch_key(roll_id, source_id)
        submitted = build_manifest(key, exposure_ids)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT batch_id, exposure_ids FROM batches WHERE roll_id = ? AND source_id = ?",
                (key.roll_id, key.source_id),
            ).fetchone()
            existing = None if row is None else build_manifest(key, json.loads(row[1]))
            decision = decide_registration(submitted, existing)
            if decision is RegistrationDecision.CONFLICT:
                raise RegistrationConflict(f"conflicting exposure manifest for {key!r}")
            if decision is RegistrationDecision.REUSE:
                return row[0]
            inserted = connection.execute(
                "INSERT INTO batches (roll_id, source_id, exposure_ids) VALUES (?, ?, ?)",
                (key.roll_id, key.source_id, json.dumps(submitted.exposure_ids)),
            )
            batch_id = inserted.lastrowid
        return batch_id

    def get(self, batch_id: int) -> RegisteredBatch:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT roll_id, source_id, exposure_ids FROM batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
        if row is None:
            raise UnknownBatch(batch_id)
        roll_id, source_id, stored_exposures = row
        key = make_batch_key(roll_id, source_id)
        return RegisteredBatch(
            BatchIdentity(batch_id, key), build_manifest(key, json.loads(stored_exposures))
        )

    def batch_ids(self) -> tuple[int, ...]:
        with closing(sqlite3.connect(self.path)) as connection:
            return tuple(
                row[0] for row in connection.execute("SELECT batch_id FROM batches ORDER BY batch_id")
            )
