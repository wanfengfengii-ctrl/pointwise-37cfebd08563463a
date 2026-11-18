from collections.abc import Callable

from capture.archive import EvidenceArchive
from publish.artifact import PublishedArtifact
from publish.commit import PublicationService
from publish.receipt import PublicationReceipt
from qualify.replay import iter_matching_interpretations
from qualify.result import build_qualification


class QualificationService:
    def __init__(self, evidence: EvidenceArchive, publication: PublicationService):
        self.evidence = evidence
        self.publication = publication

    def qualify_release(
        self,
        evidence_id: int,
        *,
        after_artifact: Callable[[PublishedArtifact], None] | None = None,
    ) -> tuple[PublishedArtifact, PublicationReceipt]:
        fixed = self.evidence.get(evidence_id)
        qualification = build_qualification(fixed, iter_matching_interpretations(fixed))
        return self.publication.commit(qualification, after_artifact=after_artifact)
