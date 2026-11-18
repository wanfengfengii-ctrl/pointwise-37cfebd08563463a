import json
from dataclasses import asdict, dataclass

from capture.events import SampleOrigin
from qualify.eligibility import ExposureDisposition
from qualify.exposure import LatchedSample
from qualify.result import ExposureQualification, QualificationResult


@dataclass(frozen=True, slots=True)
class PublishedArtifact:
    artifact_id: int
    qualification: QualificationResult

    @property
    def evidence_id(self) -> int:
        return self.qualification.evidence_id


def make_artifact(artifact_id: int, qualification: QualificationResult) -> PublishedArtifact:
    if artifact_id <= 0:
        raise ValueError("artifact ID must be positive")
    return PublishedArtifact(artifact_id, qualification)


def encode_artifact(qualification: QualificationResult) -> str:
    return json.dumps({
        "batch_id": qualification.batch_id,
        "latch_count": qualification.latch_count,
        "exposures": [asdict(exposure) for exposure in qualification.exposures],
    })


def decode_artifact(artifact_id: int, evidence_id: int, payload: str) -> PublishedArtifact:
    document = json.loads(payload)
    exposures = []
    for record in document["exposures"]:
        candidates = tuple(
            LatchedSample(SampleOrigin(**candidate["origin"]), candidate["value"])
            for candidate in record["candidates"]
        )
        exposures.append(ExposureQualification(
            record["exposure_id"], candidates, record["can_be_empty"], ExposureDisposition(record["disposition"])
        ))
    qualification = QualificationResult(
        evidence_id, document["batch_id"], document["latch_count"], tuple(exposures)
    )
    return make_artifact(artifact_id, qualification)
