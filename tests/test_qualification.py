import json

from capture.channel import RecordedChannels
from capture.events import ControlEvent, SampleEvent
from capture.seal import Seal
from qualify.result import UnexplainableRecording
from tests import ArchiveTestCase, RECORDINGS, SOURCE, qualification_signature, recording, single_sample


class QualificationTests(ArchiveTestCase):
    def test_v4_first_equal_value(self):
        batch = self.station.registry.register("coil-072", SOURCE, ("C",))
        evidence_id = self.ingest_path(batch, RECORDINGS / "steady.json")
        artifact, receipt = self.station.qualification.qualify_release(evidence_id)
        self.assertEqual(qualification_signature(artifact), (("C", (("early-c", 7),), False, "confirmed"),))
        self.assertEqual(receipt.evidence_id, evidence_id)
        self.assertEqual(tuple(
            (event.event_id, event.value) for event in self.station.evidence.get(evidence_id).channels.samples
        ), (("early-c", 7), ("late-c", 7)))

    def test_v4_zero_reading_and_integer_precision(self):
        batch = self.station.registry.register("coil-072", SOURCE, ("C",))
        document = recording("steady.json")
        document["control"][0]["tick"] = -(2 ** 80)
        document["samples"][0]["value"] = 0
        document["samples"][1]["value"] = 2 ** 80 + 1
        evidence_id = self.ingest_document(batch, document)
        artifact, _ = self.reopen().qualification.qualify_release(evidence_id)
        self.assertEqual(qualification_signature(artifact), (("C", (("early-c", 0),), False, "confirmed"),))
        fixed = self.station.evidence.get(evidence_id)
        self.assertEqual(fixed.channels.control[0].tick, -(2 ** 80))
        self.assertEqual(fixed.channels.samples[1].value, 2 ** 80 + 1)
        self.assertEqual(self.station.handoff.pickup_report(artifact.artifact_id).exposures[0].candidates[0].value, 0)

    def test_v5_accident_offline(self):
        batch = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        evidence_id = self.ingest_path(batch, RECORDINGS / "changeover.json")
        offline = self.reopen()
        artifact, receipt = offline.qualification.qualify_release(evidence_id)
        expected = (
            ("A", (("r", 17),), False, "confirmed"),
            ("B", (("s", 23), ("t", 31)), False, "review"),
        )
        actual = qualification_signature(artifact)
        self.assertEqual(actual, expected, "EXPOSURE_LATCH_MISMATCH")
        self.assertEqual((receipt.artifact_id, receipt.evidence_id), (artifact.artifact_id, evidence_id))
        report = offline.handoff.pickup_report(artifact.artifact_id)
        downstream_expected = (("B", False, ((1, "s", 1, 23), (2, "t", 2, 31))),)
        downstream_actual = tuple(
            (row.exposure_id, row.can_be_empty, tuple(
                (item.sample_index, item.event_id, item.tick, item.value) for item in row.candidates
            )) for row in report.review
        )
        self.assertEqual(downstream_actual, downstream_expected)
        print("POINTWISE_SCENARIO " + json.dumps({
            "case_id": "v5",
            "input": recording("changeover.json"),
            "expected": expected,
            "actual": actual,
            "downstream_expected": downstream_expected,
            "downstream_actual": downstream_actual,
            "code_paths": ["capture/recording.py", "capture/archive.py", "qualify/replay.py",
                           "qualify/result.py", "publish/commit.py", "handoff/read.py", "handoff/source.py"],
            "oracle": "With two latches, r must precede close A. Put s before or after open B to witness t or s for B.",
        }, ensure_ascii=False), flush=True)

    def test_v5_fixed_evidence(self):
        batch = self.station.registry.register("coil-fixed", SOURCE, ("A", "B"))
        channels = RecordedChannels(
            (ControlEvent(0, "open", "A"), ControlEvent(1, "close", "A"),
             ControlEvent(1, "open", "B"), ControlEvent(3, "close", "B")),
            (SampleEvent(1, "r", 17), SampleEvent(1, "s", 23), SampleEvent(2, "t", 31)),
        )
        evidence_id = self.station.evidence.store(batch, channels, Seal(2))
        artifact, receipt = self.station.qualification.qualify_release(evidence_id)
        self.assertEqual(qualification_signature(artifact), (
            ("A", (("r", 17),), False, "confirmed"),
            ("B", (("s", 23), ("t", 31)), False, "review"),
        ))
        self.assertEqual(artifact.qualification.batch_id, batch)
        self.assertEqual(artifact.evidence_id, evidence_id)
        self.assertEqual((receipt.artifact_id, receipt.evidence_id), (artifact.artifact_id, evidence_id))
        self.assertEqual(self.station.catalog.get(artifact.artifact_id), artifact)
        self.assertEqual(self.station.catalog.get_receipt(artifact.artifact_id), receipt)

    def test_v6_shared_sample_and_impossible_count(self):
        batch = self.station.registry.register("coil-shared", SOURCE, ("A", "B"))
        valid = self.ingest_document(batch, single_sample(1))
        impossible = self.ingest_document(batch, single_sample(2))
        self.assertEqual(self.station.evidence.get(valid).channels, self.station.evidence.get(impossible).channels)
        artifact, receipt = self.station.qualification.qualify_release(valid)
        self.assertEqual(qualification_signature(artifact), (
            ("A", (("r", 17),), True, "review"), ("B", (("r", 17),), True, "review"),
        ))
        with self.assertRaises(UnexplainableRecording) as caught:
            self.station.qualification.qualify_release(impossible)
        self.assertEqual((caught.exception.evidence_id, caught.exception.latch_count), (impossible, 2))
        self.assertEqual(self.station.catalog.artifact_ids(), (artifact.artifact_id,))
        self.assertEqual(self.station.catalog.receipt_artifact_ids(), (receipt.artifact_id,))
        self.assertEqual(self.station.evidence.evidence_ids(), (valid, impossible))

    def test_v6_always_empty(self):
        batch = self.station.registry.register("coil-empty", SOURCE, ("C",))
        document = recording("steady.json")
        document["samples"] = []
        document["seal"]["latch_count"] = 0
        evidence = self.ingest_document(batch, document)
        artifact, _ = self.station.qualification.qualify_release(evidence)
        self.assertEqual(qualification_signature(artifact), (("C", (), True, "review"),))
        report = self.station.handoff.pickup_report(artifact.artifact_id)
        self.assertEqual(tuple((item.exposure_id, item.candidates, item.can_be_empty) for item in report.review),
                         (("C", (), True),))
