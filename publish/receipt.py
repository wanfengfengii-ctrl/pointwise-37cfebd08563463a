from dataclasses import dataclass

from publish.artifact import PublishedArtifact


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    artifact_id: int
    evidence_id: int


def make_receipt(artifact: PublishedArtifact) -> PublicationReceipt:
    return PublicationReceipt(artifact.artifact_id, artifact.evidence_id)


def receipt_from_row(row: tuple[int, int]) -> PublicationReceipt:
    artifact_id, evidence_id = row
    return PublicationReceipt(artifact_id, evidence_id)
