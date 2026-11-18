import argparse
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from batch.registry import BatchRegistry
from capture.archive import EvidenceArchive
from capture.port import OfflineRecordingPort
from capture.recording import CaptureService
from handoff.read import HandoffService
from publish.catalog import PublicationCatalog
from publish.commit import PublicationService
from publish.storage import PublicationStore
from qualify.latch import QualificationService


class Station:
    """Assemble the four workflow interfaces against one file-backed archive."""

    def __init__(self, path: str | Path):
        self.registry = BatchRegistry(path)
        self.evidence = EvidenceArchive(path)
        self.publications = PublicationStore(path)
        self.catalog = PublicationCatalog(self.publications)
        self.capture = CaptureService(self.registry, self.evidence)
        self.qualification = QualificationService(self.evidence, PublicationService(self.publications))
        self.handoff = HandoffService(self.catalog, self.evidence)

    def initialize(self) -> None:
        self.registry.initialize()
        self.evidence.initialize()
        self.publications.initialize()


def _demo() -> dict:
    recordings = Path(__file__).resolve().parent / "recordings"
    with TemporaryDirectory(prefix="optical-shift-") as directory:
        path = Path(directory) / "shift.sqlite3"
        early = Station(path)
        early.initialize()
        batch_id = early.registry.register("coil-071", "line-2/optical-07", ("A", "B"))
        with OfflineRecordingPort(recordings / "changeover.json") as port:
            evidence_id = early.capture.ingest(batch_id, port)
        artifact, receipt = early.qualification.qualify_release(evidence_id)

        later_batch = early.registry.register("coil-072", "line-2/optical-07", ("C",))
        with OfflineRecordingPort(recordings / "steady.json") as port:
            later_evidence = early.capture.ingest(later_batch, port)
        _, later_receipt = early.qualification.qualify_release(later_evidence)

        evening = Station(path)
        evening.initialize()
        report = evening.handoff.pickup_report(artifact.artifact_id)
        return {"receipt": asdict(receipt), "later_receipt": asdict(later_receipt), "pickup": asdict(report)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline optical inspection archive")
    parser.add_argument("--archive", type=Path, help="SQLite archive file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="initialize the archive")
    register = commands.add_parser("register", help="register an ordered exposure manifest")
    register.add_argument("roll_id")
    register.add_argument("source_id")
    register.add_argument("exposure_ids", nargs="*")
    ingest = commands.add_parser("ingest", help="freeze a recording")
    ingest.add_argument("batch_id", type=int)
    ingest.add_argument("recording", type=Path)
    qualify = commands.add_parser("qualify", help="qualify and issue a fixed artifact")
    qualify.add_argument("evidence_id", type=int)
    pickup = commands.add_parser("pickup", help="read one issued artifact and its sources")
    pickup.add_argument("artifact_id", type=int)
    commands.add_parser("demo", help="run the offline shift workflow in a temporary archive")
    return parser


def _run(station: Station, args: argparse.Namespace) -> dict:
    if args.command == "init":
        return {"archive": str(args.archive), "batches": station.registry.batch_ids(),
                "evidence": station.evidence.evidence_ids(), "artifacts": station.catalog.artifact_ids()}
    if args.command == "register":
        batch_id = station.registry.register(args.roll_id, args.source_id, args.exposure_ids)
        return {"batch_id": batch_id}
    if args.command == "ingest":
        with OfflineRecordingPort(args.recording) as port:
            return {"evidence_id": station.capture.ingest(args.batch_id, port)}
    if args.command == "qualify":
        artifact, receipt = station.qualification.qualify_release(args.evidence_id)
        return {"artifact": asdict(artifact), "receipt": asdict(receipt)}
    return asdict(station.handoff.pickup_report(args.artifact_id))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = _demo()
        else:
            if args.archive is None:
                parser.error("--archive is required for this command")
            station = Station(args.archive)
            station.initialize()
            result = _run(station, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, sqlite3.Error) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
