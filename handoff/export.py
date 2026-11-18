from collections.abc import Mapping
from dataclasses import dataclass

from batch.identity import BatchKey
from capture.events import SampleOrigin
from handoff.review_list import ExposureView, ReviewEntry, build_review_list
from handoff.source import SourceReading
from publish.artifact import PublishedArtifact


@dataclass(frozen=True, slots=True)
class PickupReport:
    artifact_id: int
    batch_id: int
    evidence_id: int
    roll_id: str
    source_id: str
    latch_count: int
    exposures: tuple[ExposureView, ...]
    review: tuple[ReviewEntry, ...]


def export_report(
    artifact: PublishedArtifact, key: BatchKey, sources: Mapping[SampleOrigin, SourceReading]
) -> PickupReport:
    qualification = artifact.qualification
    exposures = tuple(
        ExposureView(
            exposure.exposure_id,
            tuple(sources[candidate.origin] for candidate in exposure.candidates),
            exposure.can_be_empty,
            exposure.disposition,
        )
        for exposure in qualification.exposures
    )
    return PickupReport(
        artifact.artifact_id, qualification.batch_id, qualification.evidence_id, key.roll_id, key.source_id,
        qualification.latch_count, exposures, build_review_list(exposures),
    )
