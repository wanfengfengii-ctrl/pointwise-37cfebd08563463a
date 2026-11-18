import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path


class PublicationStore:
    def __init__(self, path: str | Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    def initialize(self) -> None:
        with self.transaction() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id INTEGER PRIMARY KEY,
                    evidence_id INTEGER NOT NULL REFERENCES evidence (evidence_id),
                    payload TEXT NOT NULL,
                    UNIQUE (artifact_id, evidence_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS receipts (
                    artifact_id INTEGER PRIMARY KEY,
                    evidence_id INTEGER NOT NULL,
                    FOREIGN KEY (artifact_id, evidence_id)
                        REFERENCES artifacts (artifact_id, evidence_id)
                )"""
            )
