from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from batch.manifest import BatchManifest
from capture.events import ControlEvent, SampleEvent, parse_control_event, parse_sample_event


class ChannelError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecordedChannels:
    # Positions in each immutable tuple are the original zero-based channel positions.
    control: tuple[ControlEvent, ...]
    samples: tuple[SampleEvent, ...]


def _parse_channel(records, parse_event, label):
    events = []
    previous_tick = None
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ChannelError(f"{label}[{index}] must be an event object")
        try:
            event = parse_event(record)
        except ValueError as error:
            raise ChannelError(f"{label}[{index}]: {error}") from error
        if previous_tick is not None and event.tick < previous_tick:
            raise ChannelError(f"{label}[{index}] goes backwards in tick order")
        previous_tick = event.tick
        events.append(event)
    return tuple(events)


def _check_control(manifest: BatchManifest, events: tuple[ControlEvent, ...]) -> None:
    remaining = set(manifest.exposure_ids)
    active = None
    for index, event in enumerate(events):
        exposure_id = event.exposure_id
        if event.kind == "open":
            if active is not None:
                raise ChannelError(f"control[{index}] overlaps exposure {active!r}")
            if exposure_id not in remaining:
                raise ChannelError(f"control[{index}] opens an unlisted or repeated exposure {exposure_id!r}")
            active = exposure_id
            remaining.remove(exposure_id)
        else:
            if active != exposure_id:
                raise ChannelError(f"control[{index}] close does not match the open exposure")
            active = None
    if active is not None:
        raise ChannelError(f"exposure {active!r} is still open")
    if remaining:
        raise ChannelError(f"missing exposure controls: {', '.join(sorted(remaining))}")


def validate_channels(
    manifest: BatchManifest,
    control: Iterable[Mapping[str, object]],
    samples: Iterable[Mapping[str, object]],
) -> RecordedChannels:
    recorded_control = _parse_channel(control, parse_control_event, "control")
    recorded_samples = _parse_channel(samples, parse_sample_event, "samples")
    _check_control(manifest, recorded_control)
    sample_ids: set[str] = set()
    for index, sample in enumerate(recorded_samples):
        if sample.event_id in sample_ids:
            raise ChannelError(f"samples[{index}] repeats event ID {sample.event_id!r}")
        sample_ids.add(sample.event_id)
    return RecordedChannels(recorded_control, recorded_samples)
