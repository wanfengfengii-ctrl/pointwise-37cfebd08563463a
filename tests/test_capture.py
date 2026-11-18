from batch.registry import RegistrationConflict, UnknownBatch
from capture.archive import UnknownEvidence
from capture.channel import ChannelError
from capture.port import ClosedRecordingPort, OfflineRecordingPort, RecordingFormatError
from capture.recording import SourceMismatch
from capture.seal import SealError
from tests import ArchiveTestCase, RECORDINGS, SOURCE, recording


class CaptureTests(ArchiveTestCase):
    def test_v1_original_channels(self):
        batch_id = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        port = OfflineRecordingPort(RECORDINGS / "changeover.json")
        with port:
            evidence_id = self.station.capture.ingest(batch_id, port)
        with self.assertRaises(ClosedRecordingPort):
            port.read()
        fixed = self.reopen().evidence.get(evidence_id)
        self.assertEqual(fixed.batch, self.station.registry.get(batch_id))
        self.assertEqual(fixed.batch.manifest.exposure_ids, ("A", "B"))
        self.assertEqual(fixed.batch.identity.key.source_id, SOURCE)
        self.assertEqual(tuple(
            (index, event.tick, event.kind, event.exposure_id, event.event_id)
            for index, event in enumerate(fixed.channels.control)
        ), (
            (0, 0, "open", "A", "open-a"), (1, 1, "close", "A", "close-a"),
            (2, 1, "open", "B", "open-b"), (3, 3, "close", "B", "close-b"),
        ))
        self.assertEqual(tuple(
            (index, event.tick, event.event_id, event.value)
            for index, event in enumerate(fixed.channels.samples)
        ), ((0, 1, "r", 17), (1, 1, "s", 23), (2, 2, "t", 31)))
        self.assertEqual(fixed.seal.latch_count, 2)

    def test_v1_foreign_source(self):
        batch_id = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        original = self.ingest_path(batch_id, RECORDINGS / "changeover.json")
        foreign = recording("changeover.json")
        foreign["source_id"] = "line-2/optical-08"
        foreign["samples"][0]["event_id"] = "foreign-r"
        with self.assertRaises(SourceMismatch):
            self.ingest_document(batch_id, foreign)
        self.assertEqual(self.station.evidence.evidence_ids(), (original,))
        self.assertEqual(self.station.evidence.get(original).channels.samples[0].event_id, "r")

    def test_v1_invalid_controls_and_channel_order(self):
        batch_id = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        control_cases = (
            ("mismatched close", 1, "exposure_id", "B"),
            ("overlap", 1, "kind", "open"),
            ("backward control tick", 3, "tick", 0),
            ("noninteger tick", 0, "tick", False),
        )
        for name, index, field, value in control_cases:
            with self.subTest(name=name):
                document = recording("changeover.json")
                document["control"][index][field] = value
                with self.assertRaises(ChannelError):
                    self.ingest_document(batch_id, document)
        for field, value in (("event_id", "r"), ("tick", 0), ("value", 1.5)):
            with self.subTest(field=field):
                document = recording("changeover.json")
                document["samples"][1][field] = value
                with self.assertRaises(ChannelError):
                    self.ingest_document(batch_id, document)
        for retained in (2, 3):
            with self.subTest(retained=retained):
                document = recording("changeover.json")
                document["control"] = document["control"][:retained]
                with self.assertRaises(ChannelError):
                    self.ingest_document(batch_id, document)
        self.assertEqual(self.station.evidence.evidence_ids(), ())

    def test_v1_reopen_init_preserves_data_and_external_recording(self):
        batch_id = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        path = self.write_recording(recording("changeover.json"))
        evidence_id = self.ingest_path(batch_id, path)
        fixed = self.station.evidence.get(evidence_id)
        updated = recording("changeover.json")
        updated["samples"][0]["value"] = 211
        self.write_recording(updated)
        edited_bytes = path.read_bytes()
        self.station.initialize()
        reopened = self.reopen()
        self.assertEqual(path.read_bytes(), edited_bytes)
        self.assertEqual(reopened.registry.get(batch_id), fixed.batch)
        self.assertEqual(reopened.evidence.get(evidence_id), fixed)
        self.assertEqual(fixed.channels.samples[0].value, 17)
        with self.assertRaises(UnknownEvidence):
            reopened.evidence.get(evidence_id + 100)

    def test_v2_duplicate_exposure_rejected_without_registration(self):
        original = self.station.registry.register("coil-001", SOURCE, ("A",))
        with self.assertRaisesRegex(ValueError, "duplicate exposure ID"):
            self.station.registry.register("coil-002", SOURCE, ("A", "B", "A"))
        self.assertEqual(self.station.registry.batch_ids(), (original,))
        self.assertEqual(self.station.registry.get(original).manifest.exposure_ids, ("A",))

    def test_v2_repeat_declaration(self):
        first = self.station.registry.register("coil-001", SOURCE, ("A", "B"))
        self.assertEqual(self.reopen().registry.register("coil-001", SOURCE, ("A", "B")), first)
        with self.assertRaises(RegistrationConflict):
            self.station.registry.register("coil-001", SOURCE, ("B", "A"))
        other = self.station.registry.register("coil-001", "line-2/optical-08", ("B", "A"))
        self.assertNotEqual(first, other)
        self.assertEqual(self.station.registry.batch_ids(), (first, other))
        self.assertEqual(self.station.registry.get(first).manifest.exposure_ids, ("A", "B"))
        with self.assertRaises(UnknownBatch):
            self.station.registry.get(other + 100)

    def test_v3_missing_seal(self):
        batch_id = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        document = recording("changeover.json")
        del document["seal"]
        with self.assertRaisesRegex(SealError, "missing terminal seal"):
            self.ingest_document(batch_id, document)
        self.assertEqual(self.station.evidence.evidence_ids(), ())

    def test_v3_invalid_or_repeated_seal(self):
        batch_id = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        for count in (-1, True, "2", 2.0):
            with self.subTest(count=count):
                document = recording("changeover.json")
                document["seal"]["latch_count"] = count
                with self.assertRaises(SealError):
                    self.ingest_document(batch_id, document)
        path = self.root / "repeated-seal.json"
        original = (RECORDINGS / "changeover.json").read_text(encoding="utf-8").rstrip()
        path.write_text(original[:-1] + ', "seal": {"kind": "seal", "latch_count": 2}}', encoding="utf-8")
        with self.assertRaisesRegex(RecordingFormatError, "duplicate recording field"):
            self.ingest_path(batch_id, path)
        self.assertEqual(self.station.evidence.evidence_ids(), ())
