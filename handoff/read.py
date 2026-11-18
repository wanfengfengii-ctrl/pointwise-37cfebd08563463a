from capture.archive import EvidenceArchive
from handoff.export import PickupReport, export_report
from handoff.source import InvalidOrigin, resolve_source
from publish.catalog import PublicationCatalog


class HandoffService:
    def __init__(self, catalog: PublicationCatalog, evidence: EvidenceArchive):
        self.catalog = catalog
        self.evidence = evidence

    def pickup_report(self, artifact_id: int) -> PickupReport:
        artifact = self.catalog.get(artifact_id)
        fixed = self.evidence.get(artifact.evidence_id)
        if fixed.batch.identity.batch_id != artifact.qualification.batch_id:
            raise InvalidOrigin("published batch disagrees with the fixed evidence")
        sources = {}
        for exposure in artifact.qualification.exposures:
            for candidate in exposure.candidates:
                sources[candidate.origin] = resolve_source(fixed, candidate.origin, candidate.value)
        return export_report(artifact, fixed.batch.identity.key, sources)
