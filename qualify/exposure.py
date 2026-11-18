from dataclasses import dataclass, replace

from capture.events import ControlEvent, SampleEvent, SampleOrigin


@dataclass(frozen=True, slots=True)
class LatchedSample:
    origin: SampleOrigin
    value: int


@dataclass(frozen=True, slots=True)
class ExposureState:
    active: str | None = None
    first: LatchedSample | None = None
    closed: tuple[tuple[str, LatchedSample | None], ...] = ()
    latch_count: int = 0


def apply_control(state: ExposureState, event: ControlEvent) -> ExposureState:
    if event.kind == "open":
        if state.active is not None:
            raise ValueError("cannot open an exposure while another is active")
        return replace(state, active=event.exposure_id)
    if state.active != event.exposure_id:
        raise ValueError("cannot close an exposure that is not active")
    return ExposureState(
        closed=state.closed + ((event.exposure_id, state.first),), latch_count=state.latch_count
    )


def apply_sample(
    state: ExposureState, evidence_id: int, sample_index: int, event: SampleEvent
) -> ExposureState:
    if state.active is None or state.first is not None:
        return state
    origin = SampleOrigin(evidence_id, sample_index, event.event_id)
    return replace(state, first=LatchedSample(origin, event.value), latch_count=state.latch_count + 1)
