"""Turn a container run into per-test outcomes.

The heavy lifting happens in the container (env/inject/harness_runner.py writes
structured JSON). This module's real job is the boring, critical part: deciding
when a run produced *no trustworthy answer at all*, so that an infrastructure
failure is never silently scored as "the model didn't fix it".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Outcomes the injected collector can emit.
PASSING = {"passed", "expected_failure"}
FAILING = {"failed", "error", "unexpected_success"}
SKIPPED = {"skipped"}


class RunStatus(str, Enum):
    OK = "ok"                      # results are trustworthy, use them
    TIMEOUT = "timeout"            # container exceeded its wall clock
    NO_RESULTS = "no_results"      # collector never wrote a file
    INCOMPLETE = "incomplete"      # file written but run died mid-way
    MALFORMED = "malformed"        # file unparseable


@dataclass
class ParsedRun:
    status: RunStatus
    outcomes: dict[str, str] = field(default_factory=dict)
    totals: dict = field(default_factory=dict)
    detail: str = ""
    # Wall clock for the container, including startup. Carried through because
    # validation rejects tasks whose graded configuration is too slow, and this
    # is the figure grading will actually pay per model.
    duration_sec: float = 0.0

    @property
    def trustworthy(self) -> bool:
        return self.status is RunStatus.OK

    def passed(self, test_id: str) -> bool:
        return self.outcomes.get(test_id) in PASSING

    def status_of(self, test_id: str) -> str:
        """`missing` distinguishes "never ran" from "ran and failed"."""
        return self.outcomes.get(test_id, "missing")


def parse_run(
    result_path: Path,
    *,
    exit_code: int,
    timed_out: bool,
    stdout: str = "",
    duration_sec: float = 0.0,
) -> ParsedRun:
    """Read the collector's JSON, or explain why there isn't a usable one.

    Note what is deliberately *not* done here: the test-suite exit code is not
    treated as authoritative. A non-zero exit is the normal case for a task in
    its pre-patch state -- fail_to_pass is supposed to fail -- so grading reads
    individual outcomes instead. exit_code is only consulted to explain a
    missing results file.
    """
    if timed_out:
        return ParsedRun(RunStatus.TIMEOUT, detail=_tail(stdout), duration_sec=duration_sec)

    if not result_path.exists():
        return ParsedRun(
            RunStatus.NO_RESULTS,
            duration_sec=duration_sec,
            detail=(
                f"collector wrote no results (container exit {exit_code}); "
                f"likely a crash before tests ran: {_tail(stdout)}"
            ),
        )

    try:
        payload = json.loads(result_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return ParsedRun(RunStatus.MALFORMED, detail=f"{exc}; {_tail(stdout)}", duration_sec=duration_sec)

    if not payload.get("complete"):
        return ParsedRun(
            RunStatus.INCOMPLETE,
            duration_sec=duration_sec,
            outcomes=payload.get("outcomes", {}),
            detail=f"run ended before the suite finished; {_tail(stdout)}",
        )

    return ParsedRun(
        RunStatus.OK,
        outcomes=payload.get("outcomes", {}),
        totals=payload.get("totals", {}),
        duration_sec=duration_sec,
    )


def _tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])
