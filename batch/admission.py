from enum import Enum, auto

from batch.manifest import BatchManifest


class RegistrationDecision(Enum):
    CREATE = auto()
    REUSE = auto()
    CONFLICT = auto()


def decide_registration(
    submitted: BatchManifest, existing: BatchManifest | None
) -> RegistrationDecision:
    if existing is None:
        return RegistrationDecision.CREATE
    if submitted == existing:
        return RegistrationDecision.REUSE
    return RegistrationDecision.CONFLICT
