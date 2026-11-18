from publish.catalog import UnknownArtifact
from tests import ArchiveTestCase, RECORDINGS, SOURCE, recording, single_sample


class HandoffTests(ArchiveTestCase):
    def test_v8_pinned_artifact(self):
        batch = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        evidence = self.ingest_path(batch, RECORDINGS / "changeover.json")
        original, _ = self.station.qualification.qualify_release(evidence)
        original_report = self.station.handoff.pickup_report(original.artifact_id)
        other_batch = self.station.registry.register("coil-072", SOURCE, ("C",))
        other_evidence = self.ingest_path(other_batch, RECORDINGS / "steady.json")
        later, _ = self.station.qualification.qualify_release(other_evidence)
        self.assertNotEqual(later.artifact_id, original.artifact_id)
        reopened = self.reopen()
        self.assertEqual(reopened.catalog.get(original.artifact_id), original)
        report = reopened.handoff.pickup_report(original.artifact_id)
        self.assertEqual(report, original_report)
        self.assertEqual((report.batch_id, report.evidence_id, report.roll_id, report.source_id),
                         (batch, evidence, "coil-071", SOURCE))
        self.assertEqual(tuple(row.exposure_id for row in report.exposures), ("A", "B"))
        self.assertEqual(tuple(row.exposure_id for row in report.review), ("B",))
        self.assertEqual(tuple((sample.event_id, sample.tick) for sample in report.review[0].candidates),
                         (("s", 1), ("t", 2)))
        later_report = reopened.handoff.pickup_report(later.artifact_id)
        self.assertEqual(later_report.evidence_id, other_evidence)
        self.assertEqual(later_report.exposures[0].candidates[0].event_id, "early-c")

    def test_v8_equal_value_origin(self):
        batch = self.station.registry.register("coil-equal", SOURCE, ("A", "B"))
        document = recording("changeover.json")
        document["samples"][2]["value"] = 23
        document["samples"].append({"tick": 2, "event_id": "u", "value": 23})
        evidence = self.ingest_document(batch, document)
        artifact, _ = self.station.qualification.qualify_release(evidence)
        reopened = self.reopen()
        report = reopened.handoff.pickup_report(artifact.artifact_id)
        self.assertEqual(tuple(row.exposure_id for row in report.review), ("B",))
        row = report.review[0]
        self.assertFalse(row.can_be_empty)
        self.assertEqual(tuple(
            (sample.evidence_id, sample.source_id, sample.sample_index, sample.event_id, sample.tick, sample.value)
            for sample in row.candidates
        ), ((evidence, SOURCE, 1, "s", 1, 23), (evidence, SOURCE, 2, "t", 2, 23)))
        self.assertEqual(report.exposures[1].candidates, row.candidates)
        self.assertEqual(tuple((event.event_id, event.value) for event in reopened.evidence.get(evidence).channels.samples),
                         (("r", 17), ("s", 23), ("t", 23), ("u", 23)))

    def test_v8_manifest_order(self):
        batch = self.station.registry.register("coil-order", SOURCE, ("Z", "A"))
        evidence = self.ingest_document(batch, single_sample(1, second="Z"))
        artifact, _ = self.station.qualification.qualify_release(evidence)
        report = self.reopen().handoff.pickup_report(artifact.artifact_id)
        self.assertEqual(tuple(row.exposure_id for row in report.exposures), ("Z", "A"))
        self.assertEqual(tuple((row.exposure_id, row.can_be_empty, row.candidates[0].event_id)
                               for row in report.review), (("Z", True, "r"), ("A", True, "r")))

    def test_v8_unknown_artifact(self):
        batch = self.station.registry.register("coil-072", SOURCE, ("C",))
        evidence = self.ingest_path(batch, RECORDINGS / "steady.json")
        artifact, _ = self.station.qualification.qualify_release(evidence)
        with self.assertRaises(UnknownArtifact) as caught:
            self.reopen().handoff.pickup_report(artifact.artifact_id + 100)
        self.assertEqual(caught.exception.args, (artifact.artifact_id + 100,))
        self.assertEqual(self.station.catalog.artifact_ids(), (artifact.artifact_id,))
