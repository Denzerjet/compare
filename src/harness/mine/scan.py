"""Walk django's git history and emit task candidates.

Cheap and read-only: no containers, no patches applied. Everything here is a
filter that can be decided from the commit metadata alone. Anything needing the
tests to actually run belongs in validate.py.
"""

from __future__ import annotations

import datetime as _dt
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HARNESS_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPO = HARNESS_ROOT / "repo" / "django"
DEFAULT_CONFIG = HARNESS_ROOT / "config" / "mining.yaml"

TICKET_RE = re.compile(r"^Fixed #(\d+)")


@dataclass
class Candidate:
    sha: str
    date: _dt.date
    subject: str
    ticket: str
    source_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    other_files: list[str] = field(default_factory=list)
    source_loc: int = 0

    @property
    def task_id(self) -> str:
        return f"django__django-{self.ticket}"

    @property
    def area(self) -> str:
        """Primary subsystem: the area of the most-changed source file."""
        if not self.source_files:
            return "unknown"
        parts = self.source_files[0].split("/")
        return "/".join(parts[:3]) if len(parts) > 3 else "/".join(parts[:2])


def load_config(path: Path | None = None) -> dict:
    return yaml.safe_load(Path(path or DEFAULT_CONFIG).read_text())


def _git_log(repo: Path, since: str) -> list[dict]:
    """One pass over the log. Parsing --numstat inline avoids a `git show` per
    commit, which matters at ~2000 commits."""
    raw = subprocess.run(
        ["git", "-C", str(repo), "log", f"--since={since}", "--no-merges",
         "--numstat", "--format=@@@%H|%cd|%s", "--date=short"],
        capture_output=True, text=True, check=True,
    ).stdout

    commits: list[dict] = []
    cur: dict | None = None
    for line in raw.splitlines():
        if line.startswith("@@@"):
            sha, date, subject = line[3:].split("|", 2)
            cur = {"sha": sha, "date": date, "subject": subject, "files": []}
            commits.append(cur)
        elif line.strip() and cur is not None:
            parts = line.split("\t")
            if len(parts) == 3:
                added, deleted, path = parts
                cur["files"].append((
                    path,
                    0 if added == "-" else int(added),
                    0 if deleted == "-" else int(deleted),
                ))
    return commits


def scan(repo: Path | None = None, config: dict | None = None) -> list[Candidate]:
    """Return candidates passing every metadata-only filter, newest first."""
    repo = Path(repo or DEFAULT_REPO)
    cfg = config or load_config()
    window = cfg["window"]
    filt = cfg["candidate_filters"]
    excl = cfg["exclude"]

    subject_re = re.compile(filt["subject_pattern"])
    bad_paths = tuple(excl["paths"])
    bad_subject = [s.lower() for s in excl["subject_contains"]]
    loc_lo, loc_hi = filt["source_loc_range"]

    candidates: list[Candidate] = []
    for c in _git_log(repo, window["since"]):
        if not subject_re.match(c["subject"]):
            continue
        if any(s in c["subject"].lower() for s in bad_subject):
            continue
        if any(p.startswith(bad_paths) for p, _, _ in c["files"]):
            continue

        source = [(p, a + d) for p, a, d in c["files"] if p.startswith("django/")]
        tests = [p for p, _, _ in c["files"] if p.startswith("tests/")]
        other = [
            p for p, _, _ in c["files"]
            if not p.startswith(("django/", "tests/"))
        ]
        if not source or not tests:
            continue
        if len(source) > filt["max_source_files"]:
            continue

        loc = sum(n for _, n in source)
        if not (loc_lo <= loc <= loc_hi):
            continue

        ticket = TICKET_RE.match(c["subject"]).group(1)
        # Sorted by size so `area` reflects the most-changed file, not file order.
        source.sort(key=lambda x: -x[1])
        candidates.append(Candidate(
            sha=c["sha"],
            date=_dt.date.fromisoformat(c["date"]),
            subject=c["subject"],
            ticket=ticket,
            source_files=[p for p, _ in source],
            test_files=tests,
            other_files=other,
            source_loc=loc,
        ))

    candidates.sort(key=lambda c: (c.date, c.sha), reverse=True)

    if excl.get("one_task_per_ticket", True):
        candidates = _dedupe_by_ticket(candidates)
    return candidates


def _dedupe_by_ticket(candidates: list[Candidate]) -> list[Candidate]:
    """One candidate per ticket, keeping the newest commit.

    A ticket fixed across several commits would otherwise yield a task per
    commit, several of them partial and therefore unsolvable. Keeping the newest
    carries a known hazard -- its parent may already contain an earlier commit's
    fix, making the task void -- but that case is self-correcting: validation
    observes no failing tests at base and rejects it, rather than producing a
    task every model passes for free.
    """
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:  # already newest-first
        if c.ticket in seen:
            continue
        seen.add(c.ticket)
        out.append(c)
    return out
