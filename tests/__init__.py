import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from capture.port import OfflineRecordingPort
from station import Station

SOURCE = "line-2/optical-07"
RECORDINGS = Path(__file__).resolve().parent.parent / "recordings"


def recording(name):
    return json.loads((RECORDINGS / name).read_text(encoding="utf-8"))


def single_sample(count=1, second="B"):
    document = recording("changeover.json")
    for control in document["control"]:
        if control["exposure_id"] == "B":
            control["exposure_id"] = second
    document["samples"] = [{"tick": 1, "event_id": "r", "value": 17}]
    document["seal"]["latch_count"] = count
    return document


def qualification_signature(artifact):
    return tuple(
        (row.exposure_id, tuple((c.origin.event_id, c.value) for c in row.candidates),
         row.can_be_empty, row.disposition.value)
        for row in artifact.qualification.exposures
    )


class ArchiveTestCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="optical-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.database = self.root / "archive.sqlite3"
        self.station = self.reopen()

    def reopen(self):
        station = Station(self.database)
        station.initialize()
        return station

    def write_recording(self, document, filename="operator-recording.json"):
        path = self.root / filename
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def ingest_path(self, batch_id, path):
        with OfflineRecordingPort(path) as port:
            return self.station.capture.ingest(batch_id, port)

    def ingest_document(self, batch_id, document):
        return self.ingest_path(batch_id, self.write_recording(document))
