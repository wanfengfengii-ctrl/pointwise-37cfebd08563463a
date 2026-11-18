from collections.abc import Callable

from publish.artifact import PublishedArtifact, encode_artifact, make_artifact
from publish.receipt import PublicationReceipt, make_receipt
from publish.storage import PublicationStore
from qualify.result import QualificationResult


class PublicationError(RuntimeError):
    pass


class PublicationService:
    def __init__(self, store: PublicationStore):
        self.store = store

    def commit(
        self,
        qualification: QualificationResult,
        *,
        after_artifact: Callable[[PublishedArtifact], None] | None = None,
    ) -> tuple[PublishedArtifact, PublicationReceipt]:
        try:
            payload = encode_artifact(qualification)
            with self.store.transaction() as connection:
                inserted = connection.execute(
                    "INSERT INTO artifacts (evidence_id, payload) VALUES (?, ?)",
                    (qualification.evidence_id, payload),
                )
                artifact = make_artifact(inserted.lastrowid, qualification)
                if after_artifact is not None:
                    after_artifact(artifact)
                receipt = make_receipt(artifact)
                connection.execute(
                    "INSERT INTO receipts (artifact_id, evidence_id) VALUES (?, ?)",
                    (receipt.artifact_id, receipt.evidence_id),
                )
        except Exception as error:
            raise PublicationError(f"publication failed for evidence {qualification.evidence_id}") from error
        return artifact, receipt
