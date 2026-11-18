import argparse
import json
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from capture.port import OfflineRecordingPort
from handoff.source import SourceReading
from publish.catalog import UnknownArtifact
from publish.commit import PublicationError
from qualify.result import UnexplainableRecording
from station import Station

SOURCE = "line-2/optical-07"


def open_station(root):
    station = Station(root / "shift.sqlite3")
    station.initialize()
    return station


def ingest(station, root, name, manifest, windows, samples, count):
    document = {
        "source_id": SOURCE,
        "control": [
            {"tick": tick, "kind": kind, "exposure_id": exposure}
            for exposure, opening, closing in windows
            for tick, kind in ((opening, "open"), (closing, "close"))
        ],
        "samples": [
            {"tick": tick, "event_id": event, "value": value}
            for tick, event, value in samples
        ],
        "seal": {"kind": "seal", "latch_count": count},
    }
    path = root / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    batch = station.registry.register(name, SOURCE, manifest)
    with OfflineRecordingPort(path) as port:
        evidence_id = station.capture.ingest(batch, port)
    path.unlink()
    return evidence_id


def shared_case(station, root, count=1):
    return ingest(station, root, f"shared-{count}", ("A", "B"),
                  (("A", 0, 1), ("B", 1, 3)), ((1, "r", 17),), count)


def baseline(day, root, evidence_id):
    artifact, receipt = day.qualification.qualify_release(evidence_id)
    later = open_station(root)
    report = later.handoff.pickup_report(artifact.artifact_id)
    assert report.evidence_id == evidence_id and report.latch_count == 1
    assert later.catalog.get_receipt(artifact.artifact_id) == receipt
    items = tuple((row.exposure_id, row.can_be_empty, row.candidates[0].event_id) for row in report.review)
    assert items == (("A", True, "r"), ("B", True, "r")), items
    return {"evidence_id": evidence_id, "v1_review": items}


def check_plan(station, receipt, evidence_id, ids, cost):
    assert receipt.evidence_id == evidence_id and station.catalog.get_receipt(receipt.artifact_id) == receipt
    actual = station.handoff.pickup_review(receipt.artifact_id)
    expected = {"evidence_id": evidence_id, "exposure_ids": ids, "total_cost": cost}
    assert actual == expected, (actual, expected)


def verify(day, root, shared):
    errors = unittest.TestCase()
    legacy, _ = day.qualification.qualify_release(shared)
    issue = day.qualification.qualify_release_review
    _, first = issue(shared, {"B": 1, "A": 4})
    _, second = issue(shared, {"A": 1, "B": 4})
    trap = ingest(day, root, "overlapping-choices", ("B", "C", "D"),
                  (("B", 0, 1), ("C", 3, 6), ("D", 6, 7)),
                  ((1, "r", 7), (3, "s", 7), (6, "t", 7), (7, "u", 7)), 2)
    _, third = issue(trap, {"B": 1, "C": 1, "D": 5})
    tie = ingest(day, root, "one-of-three", ("Z", "A", "M"),
                 (("A", 0, 1), ("M", 2, 3), ("Z", 4, 5)),
                 ((0, "a", 7), (2, "m", 7), (4, "z", 7)), 1)
    _, tied = issue(tie, {"M": 1, "A": 1, "Z": 1})
    stable = ingest(day, root, "same-first", ("C",), (("C", 0, 2),),
                    ((1, "early", 0), (2, "extra", 0)), 1)
    _, certain = issue(stable, {"C": 3})
    impossible = shared_case(day, root, count=2)
    later = open_station(root)
    for receipt, evidence_id, ids, cost in (
        (first, shared, ("B",), 1), (second, shared, ("A",), 1),
        (third, trap, ("C", "D"), 6), (tied, tie, ("Z", "A"), 2),
        (certain, stable, (), 0),
    ):
        check_plan(later, receipt, evidence_id, ids, cost)

    handoff = later.handoff
    resolve = handoff.resolve_review
    r = SourceReading(shared, SOURCE, 0, "r", 1, 17)
    assert resolve(first.artifact_id, {"B": None}) == (("A", r), ("B", None))
    assert resolve(first.artifact_id, {"B": "r"}) == (("A", None), ("B", r))
    assert resolve(second.artifact_id, {"A": None}) == (("A", None), ("B", r))
    readings = (("s", 1, 3), ("t", 2, 6))
    for event, index, tick in readings:
        assert resolve(third.artifact_id, {"D": None, "C": event}) == (
            ("B", SourceReading(trap, SOURCE, 0, "r", 1, 7)),
            ("C", SourceReading(trap, SOURCE, index, event, tick, 7)), ("D", None),
        )
    assert resolve(tied.artifact_id, {"A": None, "Z": None}) == (
        ("Z", None), ("A", None), ("M", SourceReading(tie, SOURCE, 1, "m", 2, 7)),
    )
    assert resolve(certain.artifact_id, {}) == (("C", SourceReading(stable, SOURCE, 0, "early", 1, 0)),)
    assert handoff.pickup_report(legacy.artifact_id).review == handoff.pickup_report(first.artifact_id).review
    before = later.catalog.artifact_ids(), later.catalog.receipt_artifact_ids()
    for answers in ({}, {"A": "r"}, {"B": None, "A": "r"}, {"B": 17}, {"B": "unseen"}):
        with errors.assertRaises(ValueError):
            resolve(first.artifact_id, answers)
    with errors.assertRaises(ValueError):
        resolve(third.artifact_id, {"C": None, "D": None})
    with errors.assertRaises(ValueError):
        handoff.pickup_review(legacy.artifact_id)
    with errors.assertRaises(ValueError):
        resolve(legacy.artifact_id, {})
    with errors.assertRaises(UnknownArtifact):
        handoff.pickup_review(max(before[0]) + 1)
    with errors.assertRaises(UnknownArtifact):
        resolve(max(before[0]) + 1, {})
    for costs in ({"A": 1}, {"A": True, "B": 1}, {"A": 0, "B": 1}, {"A": 1, "B": 1, "C": 1}):
        with errors.assertRaises(ValueError):
            issue(shared, costs)
    with errors.assertRaises(UnexplainableRecording):
        issue(impossible, {"A": 4, "B": 1})

    seen = []

    def interrupt(_artifact):
        seen.append((later.catalog.artifact_ids(), later.catalog.receipt_artifact_ids()))
        raise OSError("fixture interrupted publication")

    with errors.assertRaises(PublicationError):
        issue(shared, {"A": 4, "B": 1}, after_artifact=interrupt)
    assert seen == [before], seen
    final = open_station(root)
    assert (final.catalog.artifact_ids(), final.catalog.receipt_artifact_ids()) == before
    check_plan(final, first, shared, ("B",), 1)
    assert final.handoff.resolve_review(first.artifact_id, {"B": None}) == (("A", r), ("B", None))
    return {"verified_artifacts": (first.artifact_id, second.artifact_id, third.artifact_id,
                                  tied.artifact_id, certain.artifact_id)}


def demo(day, root, evidence_id):
    _, receipt = day.qualification.qualify_release_review(evidence_id, {"A": 4, "B": 1})
    later = open_station(root)
    handoff = later.handoff
    plan = handoff.pickup_review(receipt.artifact_id)
    resolutions = []
    for answer in ("r", None):
        rows = handoff.resolve_review(receipt.artifact_id, {"B": answer})
        resolutions.append({"answers": {"B": answer}, "first_samples": [
            (exposure, None if sample is None else asdict(sample)) for exposure, sample in rows
        ]})
    return {"receipt": asdict(receipt), "plan": plan, "resolutions": resolutions}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Optical review examples")
    parser.add_argument("mode", choices=("baseline", "verify", "demo"))
    mode = parser.parse_args(argv).mode
    if mode == "verify":
        suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
            return 1
    with TemporaryDirectory(prefix="optical-review-") as directory:
        root = Path(directory)
        day = open_station(root)
        evidence = shared_case(day, root)
        run = {"baseline": baseline, "verify": verify, "demo": demo}[mode]
        print(json.dumps(run(day, root, evidence), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
