from collections.abc import Iterator
from dataclasses import dataclass

from capture.archive import FixedEvidence
from qualify.exposure import ExposureState, LatchedSample, apply_control, apply_sample


@dataclass(frozen=True, slots=True)
class CompleteInterpretation:
    closed: tuple[tuple[str, LatchedSample | None], ...]
    latch_count: int


@dataclass(frozen=True, slots=True)
class _ReplayPosition:
    control_index: int
    sample_index: int
    state: ExposureState


def iter_matching_interpretations(evidence: FixedEvidence) -> Iterator[CompleteInterpretation]:
    control = evidence.channels.control
    samples = evidence.channels.samples
    target = evidence.seal.latch_count
    if target > min(len(samples), len(evidence.batch.manifest.exposure_ids)):
        return

    pending = [_ReplayPosition(0, 0, ExposureState())]
    while pending:
        position = pending.pop()
        i, j, state = position.control_index, position.sample_index, position.state
        if state.latch_count > target:
            continue
        next_control = control[i] if i < len(control) else None
        next_sample = samples[j] if j < len(samples) else None
        if next_control is None and next_sample is None:
            if state.active is None and state.latch_count == target:
                yield CompleteInterpretation(state.closed, state.latch_count)
            continue

        # Both transitions remain available when the two channel heads share a tick.
        if next_sample is not None and (next_control is None or next_sample.tick <= next_control.tick):
            next_state = apply_sample(state, evidence.evidence_id, j, next_sample)
            pending.append(_ReplayPosition(i, j + 1, next_state))
        if next_control is not None and (next_sample is None or next_control.tick <= next_sample.tick):
            next_state = apply_control(state, next_control)
            pending.append(_ReplayPosition(i + 1, j, next_state))
