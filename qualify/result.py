from collections.abc import Iterable
from dataclasses import dataclass

from capture.archive import FixedEvidence
from qualify.eligibility import ExposureDisposition, classify_exposure
from qualify.exposure import LatchedSample
from qualify.replay import CompleteInterpretation


class UnexplainableRecording(ValueError):
    def __init__(self, evidence_id: int, latch_count: int):
        self.evidence_id = evidence_id
        self.latch_count = latch_count
        super().__init__(f"no complete interpretation for evidence {evidence_id} with latch count {latch_count}")


@dataclass(frozen=True, slots=True)
class ExposureQualification:
    exposure_id: str
    candidates: tuple[LatchedSample, ...]
    can_be_empty: bool
    disposition: ExposureDisposition


@dataclass(frozen=True, slots=True)
class QualificationResult:
    evidence_id: int
    batch_id: int
    latch_count: int
    exposures: tuple[ExposureQualification, ...]


def build_qualification(
    evidence: FixedEvidence, interpretations: Iterable[CompleteInterpretation]
) -> QualificationResult:
    manifest_order = evidence.batch.manifest.exposure_ids
    candidate_index: dict[str, dict[int, LatchedSample]] = {
        exposure_id: {} for exposure_id in manifest_order
    }
    empty_exposures: set[str] = set()
    witnessed = False
    for interpretation in interpretations:
        witnessed = True
        for exposure_id, first in interpretation.closed:
            if first is None:
                empty_exposures.add(exposure_id)
            else:
                candidate_index[exposure_id][first.origin.sample_index] = first
    if not witnessed:
        raise UnexplainableRecording(evidence.evidence_id, evidence.seal.latch_count)

    exposures = []
    for exposure_id in manifest_order:
        indexed = candidate_index[exposure_id]
        candidates = tuple(indexed[index] for index in sorted(indexed))
        can_be_empty = exposure_id in empty_exposures
        exposures.append(ExposureQualification(
            exposure_id, candidates, can_be_empty, classify_exposure(len(candidates), can_be_empty)
        ))
    return QualificationResult(
        evidence.evidence_id, evidence.batch.identity.batch_id, evidence.seal.latch_count, tuple(exposures)
    )
