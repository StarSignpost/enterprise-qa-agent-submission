"""Run and persist actual outcomes. Live calls require an explicit --live flag."""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import time
import unittest
from unittest.mock import patch

from src.agent import now

ROOT = Path(__file__).resolve().parents[1]


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.started = {}
        self.problem_tests = set()

    def startTest(self, test):
        self.started[test.id()] = time.monotonic()
        super().startTest(test)

    def record(self, test, outcome, detail=None):
        self.records.append({"test_id": test.id(), "layer": "real_model" if ".test_live." in test.id() else "offline",
                             "outcome": outcome, "detail": detail,
                             "duration_seconds": round(time.monotonic()-self.started.get(test.id(), time.monotonic()), 6)})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "not_run", reason)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.problem_tests.add(test.id())
            self.record(subtest, "failed", self._exc_info_to_string(err, test))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="New result directory; existing reports are never overwritten")
    parser.add_argument("--live", action="store_true", help="Explicitly allow real model calls using local environment")
    parser.add_argument("--test", action="append", help="Optional targeted unittest dotted name; can repeat")
    args = parser.parse_args(argv)
    directory = Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "cases").mkdir()
    start = now()
    # Ignore ambient opt-in flags when the command did not explicitly request live.
    environment = {"QA_TEST_EVIDENCE_DIR": str(directory / "cases"), "QA_LIVE_VALIDATE": "1" if args.live else "0"}
    network_guard = (contextlib.nullcontext() if args.live else patch(
        "urllib.request.OpenerDirector.open", side_effect=AssertionError("Offline suite attempted network access")))
    with patch.dict(os.environ, environment), network_guard:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromNames(args.test) if args.test else loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    (directory / "test-output.txt").write_text(stream.getvalue(), encoding="utf-8")
    paths = sorted((ROOT / "src").glob("*.py")) + sorted((ROOT / "tests").rglob("*.py"))
    paths += sorted((ROOT / "tests/fixtures").rglob("*.json")) + sorted((ROOT / "data/scenarios").glob("*.json"))
    report = {"record_kind": "acceptance_validation", "started_at": start, "finished_at": now(),
              "python_version": platform.python_version(), "command": ["python", "-m", "tests.run_validation", *(argv if argv is not None else sys.argv[1:])],
              "live_requested": args.live, "tests_run": result.testsRun, "successful": result.wasSuccessful(),
              "provider_network_blocked": not args.live,
              "counts": {key: sum(record["outcome"] == key for record in result.records) for key in ("passed", "failed", "error", "not_run")},
              "results": result.records,
              "source_sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
              "boundaries": ["Mock choices and verdicts do not prove live model quality", "Keyword/fact checks do not replace human semantic evaluation", "Unexecuted live checks are not_run, never passed"]}
    (directory / "test-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"successful": report["successful"], "tests_run": report["tests_run"], **report["counts"],
                      "live_requested": args.live, "report": (directory / "test-report.json").relative_to(ROOT).as_posix()}, ensure_ascii=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
