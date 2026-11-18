from collections.abc import Iterable
from dataclasses import dataclass

from handoff.source import SourceReading
from qualify.eligibility import ExposureDisposition


@dataclass(frozen=True, slots=True)
class ExposureView:
    exposure_id: str
    candidates: tuple[SourceReading, ...]
    can_be_empty: bool
    disposition: ExposureDisposition


@dataclass(frozen=True, slots=True)
class ReviewEntry:
    exposure_id: str
    candidates: tuple[SourceReading, ...]
    can_be_empty: bool


def build_review_list(exposures: Iterable[ExposureView]) -> tuple[ReviewEntry, ...]:
    return tuple(
        ReviewEntry(exposure.exposure_id, exposure.candidates, exposure.can_be_empty)
        for exposure in exposures
        if exposure.disposition is ExposureDisposition.REVIEW
    )
