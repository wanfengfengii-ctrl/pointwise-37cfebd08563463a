from dataclasses import dataclass

from capture.archive import FixedEvidence
from capture.events import SampleOrigin


class InvalidOrigin(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SourceReading:
    evidence_id: int
    source_id: str
    sample_index: int
    event_id: str
    tick: int
    value: int


def resolve_source(evidence: FixedEvidence, origin: SampleOrigin, value: int) -> SourceReading:
    if origin.evidence_id != evidence.evidence_id:
        raise InvalidOrigin("candidate belongs to a different evidence record")
    if not 0 <= origin.sample_index < len(evidence.channels.samples):
        raise InvalidOrigin(f"invalid source position {origin.sample_index}")
    event = evidence.channels.samples[origin.sample_index]
    if event.event_id != origin.event_id or event.value != value:
        raise InvalidOrigin(f"source position {origin.sample_index} disagrees with the published candidate")
    return SourceReading(
        evidence.evidence_id, evidence.batch.identity.key.source_id, origin.sample_index,
        event.event_id, event.tick, event.value,
    )
