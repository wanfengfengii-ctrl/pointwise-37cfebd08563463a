from publish.catalog import UnknownArtifact, UnknownReceipt
from publish.commit import PublicationError
from station import Station
from tests import ArchiveTestCase, RECORDINGS, SOURCE


class ReleaseTests(ArchiveTestCase):
    def test_v7_atomic_publication_and_reopen(self):
        batch = self.station.registry.register("coil-071", SOURCE, ("A", "B"))
        first_evidence = self.ingest_path(batch, RECORDINGS / "changeover.json")
        original, receipt = self.station.qualification.qualify_release(first_evidence)
        original_report = self.station.handoff.pickup_report(original.artifact_id)
        next_batch = self.station.registry.register("coil-072", SOURCE, ("C",))
        next_evidence = self.ingest_path(next_batch, RECORDINGS / "steady.json")
        observer = Station(self.database)
        observations = []

        def fail_after_artifact(staged):
            observations.append((staged.artifact_id, staged.evidence_id, observer.catalog.artifact_ids(),
                                 observer.catalog.receipt_artifact_ids()))
            raise OSError("injected interruption between artifact and receipt writes")

        with self.assertRaises(PublicationError) as caught:
            self.station.qualification.qualify_release(next_evidence, after_artifact=fail_after_artifact)
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertEqual(len(observations), 1)
        staged_id, parent, artifacts, receipts = observations[0]
        self.assertNotEqual(staged_id, original.artifact_id)
        self.assertEqual(parent, next_evidence)
        self.assertEqual(artifacts, (original.artifact_id,))
        self.assertEqual(receipts, (receipt.artifact_id,))

        self.station.initialize()
        reopened = self.reopen()
        self.assertEqual(reopened.catalog.artifact_ids(), (original.artifact_id,))
        self.assertEqual(reopened.catalog.receipt_artifact_ids(), (receipt.artifact_id,))
        with self.assertRaises(UnknownArtifact):
            reopened.catalog.get(staged_id)
        with self.assertRaises(UnknownReceipt):
            reopened.catalog.get_receipt(staged_id)
        self.assertEqual(reopened.catalog.get(original.artifact_id), original)
        self.assertEqual(reopened.catalog.get_receipt(original.artifact_id), receipt)
        self.assertEqual(reopened.handoff.pickup_report(original.artifact_id), original_report)
        self.assertEqual(reopened.evidence.evidence_ids(), (first_evidence, next_evidence))

        recovered, recovered_receipt = reopened.qualification.qualify_release(next_evidence)
        self.assertEqual(recovered.evidence_id, next_evidence)
        self.assertEqual(reopened.catalog.get_receipt(recovered.artifact_id), recovered_receipt)
        self.assertEqual(reopened.catalog.get_receipt(original.artifact_id), receipt)
