"""Write a validated candidate to disk as a task.

tasks/ is the committed artifact -- reviewable in a diff and stable across runs
-- so everything written here is deterministic given the same commit and
validation result. No timestamps, no ordering that depends on dict iteration.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from ..grade import diff_hunks
from ..schema import DEFAULT_IMAGE, Task
from .scan import DEFAULT_REPO, Candidate
from .split import Split

HARNESS_ROOT = Path(__file__).resolve().parents[3]
TASKS_DIR = HARNESS_ROOT / "tasks"
MANIFEST = TASKS_DIR / "manifest.jsonl"

# Markers that mean a statement is describing the fix rather than the bug. Trac
# descriptions are written pre-fix so they rarely contain these, but they are
# editable after the fact, and the commit-subject fallback is post-fix by nature.
LEAK_MARKERS = ("--- a/", "+++ b/", "@@ ", "github.com/django/django/pull")

# Presence of this string in problem_statement.md makes the file authoritative:
# mining reads it instead of regenerating it. Kept as an HTML comment so it is
# invisible in rendered markdown but survives a round trip through the file.
HAND_EDITED_MARKER = "<!-- hand-edited: do not regenerate -->"


def django_version_at(sha: str, repo: Path | None = None) -> str:
    """VERSION tuple from django/__init__.py at a commit, e.g. '5.2.dev'."""
    try:
        src = subprocess.run(
            ["git", "-C", str(repo or DEFAULT_REPO), "show", f"{sha}:django/__init__.py"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return ""
    for line in src.splitlines():
        if line.startswith("VERSION = "):
            parts = line.split("=", 1)[1].strip().strip("()").split(",")
            nums = [p.strip().strip("\"'") for p in parts if p.strip()]
            if len(nums) >= 4:
                return f"{nums[0]}.{nums[1]}.{nums[3]}" if nums[3] != "final" else f"{nums[0]}.{nums[1]}"
            return ".".join(nums[:2])
    return ""


def statement_from_subject(cand: Candidate) -> str:
    """Provisional statement, used until the Trac description is fetched.

    Flagged rather than dressed up. A commit subject is written *after* the fix
    and routinely names the function and the mechanism, so a task carrying one is
    easier than it should be. Tasks tagged statement_source=commit_subject must be
    backfilled before they are used to compare models.
    """
    subject = cand.subject
    prefix = f"Fixed #{cand.ticket} -- "
    body = subject[len(prefix):] if subject.startswith(prefix) else subject
    return (
        f"# {body}\n\n"
        f"Reported in django ticket #{cand.ticket}:\n"
        f"https://code.djangoproject.com/ticket/{cand.ticket}\n\n"
        f"> PROVISIONAL STATEMENT. Derived from the commit subject because the\n"
        f"> Trac description has not been fetched. Written post-fix, so it may\n"
        f"> name the mechanism rather than only the symptom.\n"
    )


def has_reproduction(statement: str) -> bool:
    """Whether the statement shows concrete failing input/output.

    Crude on purpose -- it is a recorded slicing dimension, not a gate.
    """
    return any(m in statement for m in (">>>", "Traceback", "```"))


def leaks(statement: str) -> list[str]:
    return [m for m in LEAK_MARKERS if m in statement]


def write_task(
    cand: Candidate,
    sp: Split,
    val,  # ValidationResult; untyped to avoid a circular import
    *,
    statement: str | None = None,
    statement_source: str = "commit_subject",
    ticket_type: str = "unknown",
    statement_meta: dict | None = None,
    tasks_dir: Path | None = None,
    repo: Path | None = None,
) -> Path:
    tasks_dir = Path(tasks_dir or TASKS_DIR)
    out = tasks_dir / cand.task_id
    out.mkdir(parents=True, exist_ok=True)

    statement = statement or statement_from_subject(cand)

    (out / "test.patch").write_text(sp.test_patch)
    (out / "solution.patch").write_text(sp.solution_patch)

    # A hand-edited statement is never regenerated. Without this, re-mining would
    # silently revert a human's leak removal -- the one file here a person has any
    # reason to touch, and the only one that used to carry no warning.
    stmt_path = out / "problem_statement.md"
    if HAND_EDITED_MARKER in (stmt_path.read_text() if stmt_path.exists() else ""):
        statement = stmt_path.read_text()
        statement_source = "hand_edited"
    else:
        stmt_path.write_text(statement)

    spec = {
        "task_id": cand.task_id,
        "base_commit": val.base,
        "django_version": django_version_at(val.base, repo=repo),
        "env_image": DEFAULT_IMAGE,
        "test_labels": val.test_labels,
        "fail_to_pass": val.fail_to_pass,
        "pass_to_pass": val.pass_to_pass,
        "commit_date": cand.date.isoformat(),
        "tags": {
            "ticket_type": ticket_type,
            "is_feature": ticket_type == "feature",
            "area": cand.area,
            # Measured with grade.diff_loc on solution.patch -- the same function
            # grading applies to the model's patch, so loc_ratio is meaningful.
            "loc_changed": val.reference_loc,
            "files_changed": len(cand.source_files),
            "hunks_changed": diff_hunks(sp.solution_patch),
            "statement_chars": len(statement),
            "has_reproduction": has_reproduction(statement),
            "statement_source": statement_source,
            # True when statement.py altered the text (truncation, paren strip,
            # patch removal). Heuristic edits, so these are the short list worth
            # a human read before the set is used to compare models.
            "statement_needs_review": bool((statement_meta or {}).get("needs_review")),
        },
    }
    (out / "task.yaml").write_text(
        "# Generated by mine/. Do not hand-edit: re-mining overwrites it.\n"
        + yaml.safe_dump(spec, sort_keys=False, default_flow_style=False, width=88)
    )

    (out / "provenance.json").write_text(json.dumps({
        "source": "mined",
        "repo": "https://github.com/django/django",
        "fix_commit": cand.sha,
        "base_commit": val.base,
        "commit_date": cand.date.isoformat(),
        "subject": cand.subject,
        "trac_ticket": f"https://code.djangoproject.com/ticket/{cand.ticket}",
        "source_files": cand.source_files,
        "test_files": cand.test_files,
        "dropped_files": sp.dropped_files,
        "full_test_labels": sp.test_labels,
        "narrowed_test_labels": val.test_labels,
        "skipped_tests": val.skipped,
        "graded_runtime_sec": round(val.graded_runtime_sec, 2),
        "harness_retries": val.harness_retries,
        "statement_leak_markers": leaks(statement),
        "statement": statement_meta or {},
    }, indent=2) + "\n")

    # Load it back with strict tag validation: a task that can't round-trip has no
    # business in the manifest, and this is the only place that guarantee holds.
    Task.load(out, require_tags=True)
    return out


def rebuild_manifest(tasks_dir: Path | None = None) -> int:
    """Regenerate manifest.jsonl from what is on disk.

    Rebuilt rather than appended so it can never drift from the task directories,
    and so re-running mining is idempotent.
    """
    tasks_dir = Path(tasks_dir or TASKS_DIR)
    rows = []
    for d in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        if not (d / "task.yaml").exists():
            continue
        t = Task.load(d, require_tags=True)
        rows.append({
            "task_id": t.task_id,
            "base_commit": t.base_commit,
            "commit_date": t.commit_date.isoformat() if t.commit_date else None,
            "area": t.area,
            "ticket_type": t.ticket_type,
            "loc_changed": t.loc_changed,
            "files_changed": t.files_changed,
            "n_fail_to_pass": len(t.fail_to_pass),
            "n_pass_to_pass": len(t.pass_to_pass),
            "hunks_changed": t.hunks_changed,
            "statement_source": t.tags.get("statement_source"),
        })
    (tasks_dir / "manifest.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    return len(rows)
