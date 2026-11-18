from enum import StrEnum


class ExposureDisposition(StrEnum):
    CONFIRMED = "confirmed"
    REVIEW = "review"


def classify_exposure(candidate_count: int, can_be_empty: bool) -> ExposureDisposition:
    if candidate_count == 1 and not can_be_empty:
        return ExposureDisposition.CONFIRMED
    return ExposureDisposition.REVIEW
