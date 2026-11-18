from batch.registry import BatchRegistry
from capture.archive import EvidenceArchive
from capture.channel import validate_channels
from capture.port import RecordingPort
from capture.seal import require_terminal_seal


class SourceMismatch(ValueError):
    pass


class CaptureService:
    def __init__(self, registry: BatchRegistry, archive: EvidenceArchive):
        self.registry = registry
        self.archive = archive

    def ingest(self, batch_id: int, port: RecordingPort) -> int:
        batch = self.registry.get(batch_id)
        recording = port.read()
        declared_source = batch.identity.key.source_id
        if recording.source_id != declared_source:
            raise SourceMismatch(f"recorded source {recording.source_id!r} differs from {declared_source!r}")
        channels = validate_channels(batch.manifest, recording.control, recording.samples)
        seal = require_terminal_seal(recording.terminal_seal)
        return self.archive.store(batch.identity.batch_id, channels, seal)
