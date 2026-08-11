"""Task and result schemas. Single source of truth for on-disk formats."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_IMAGE = "harness/django:py313-v1"

# Tags every mined task must carry. These are deliberately a dict rather than
# typed fields: the governing mining principle is "flag, don't reject", so the
# tag set grows over time and analysis-time slicing is where filtering happens.
# The required subset is validated at load so a missing tag surfaces here rather
# than as a KeyError halfway through a report.
#
# `loc_changed` is measured with grade.diff_loc -- the same function grading uses
# for the model's patch -- so the two are identical by construction. A ratio
# between two differently-computed line counts would be meaningless.
REQUIRED_TAGS: dict[str, type | tuple[type, ...]] = {
    "ticket_type": str,          # bug | feature | cleanup
    "is_feature": bool,          # convenience flag over ticket_type
    "area": str,                 # top-level django subsystem
    "loc_changed": int,          # source LOC in the reference fix
    "files_changed": int,        # source files in the reference fix
    "hunks_changed": int,        # distinct edit sites in the reference fix
    "statement_chars": int,      # crude thinness proxy for problem_statement.md
    "has_reproduction": bool,    # does the ticket show failing input/output
    "statement_source": str,     # trac_description | commit_subject
    "statement_needs_review": bool,  # statement.py altered the text heuristically
}

# "unknown" means the Trac ticket has not been fetched yet, so the type could not
# be determined. Tasks carrying it are provisional: the statement came from the
# commit subject, which is written post-fix and often names the mechanism.
VALID_TICKET_TYPES = {"bug", "feature", "cleanup", "unknown"}


@dataclass(frozen=True)
class Task:
    """One benchmark task: a repo state plus the tests that define success.

    Test identifiers are always *method* ids (`module.Class.method`) -- the
    granularity unittest reports at. Never bare method names: a single django
    test module routinely defines the same method name in several classes
    (utils_tests.test_http has four separate `test_basic` methods), so bare
    names are ambiguous.
    """

    task_id: str
    base_commit: str
    test_labels: list[str]
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    dir: Path
    django_version: str = ""
    env_image: str = DEFAULT_IMAGE
    commit_date: _dt.date | None = None
    tags: dict = field(default_factory=dict)

    # -- tag accessors --------------------------------------------------------
    # Reporting slices on these constantly; going through properties keeps the
    # tag keys in one place instead of scattering string literals.

    @property
    def area(self) -> str:
        return self.tags.get("area", "unknown")

    @property
    def ticket_type(self) -> str:
        return self.tags.get("ticket_type", "unknown")

    @property
    def is_feature(self) -> bool:
        return bool(self.tags.get("is_feature", False))

    @property
    def loc_changed(self) -> int:
        return int(self.tags.get("loc_changed", 0))

    @property
    def files_changed(self) -> int:
        return int(self.tags.get("files_changed", 0))

    @property
    def hunks_changed(self) -> int:
        return int(self.tags.get("hunks_changed", 0))

    @property
    def statement_chars(self) -> int:
        return int(self.tags.get("statement_chars", 0))

    @property
    def has_reproduction(self) -> bool:
        return bool(self.tags.get("has_reproduction", False))

    # Files alongside task.yaml. Read lazily -- patches are only needed at
    # grade time, and validation reports shouldn't pay to load them.
    @property
    def test_patch(self) -> str:
        return (self.dir / "test.patch").read_text()

    @property
    def solution_patch(self) -> str:
        return (self.dir / "solution.patch").read_text()

    @property
    def problem_statement(self) -> str:
        return (self.dir / "problem_statement.md").read_text()

    @classmethod
    def load(cls, task_dir: str | Path, *, require_tags: bool = False) -> Task:
        """Load a task spec.

        `require_tags` is off by default so hand-written fixtures stay loadable;
        mining turns it on so a task can never reach the manifest missing a
        slicing dimension the report depends on.
        """
        task_dir = Path(task_dir)
        spec = yaml.safe_load((task_dir / "task.yaml").read_text())

        unknown = set(spec) - {f.name for f in cls.__dataclass_fields__.values()}
        if unknown:
            raise ValueError(f"{task_dir}: unknown task.yaml keys: {sorted(unknown)}")

        commit_date = spec.get("commit_date")
        if isinstance(commit_date, str):
            commit_date = _dt.date.fromisoformat(commit_date)

        task = cls(
            task_id=spec["task_id"],
            base_commit=spec["base_commit"],
            test_labels=list(spec["test_labels"]),
            fail_to_pass=list(spec["fail_to_pass"]),
            pass_to_pass=list(spec["pass_to_pass"]),
            dir=task_dir,
            django_version=spec.get("django_version", ""),
            env_image=spec.get("env_image", DEFAULT_IMAGE),
            commit_date=commit_date,
            tags=spec.get("tags") or {},
        )
        task.validate_spec(require_tags=require_tags)
        return task

    def validate_spec(self, *, require_tags: bool = False) -> None:
        """Catch malformed specs at load time rather than mid-run."""
        if not self.fail_to_pass:
            raise ValueError(f"{self.task_id}: fail_to_pass must not be empty")
        if not self.test_labels:
            raise ValueError(f"{self.task_id}: test_labels must not be empty")
        # A test in both lists is a contradiction: it would have to fail and
        # pass in the same pre-patch state.
        both = set(self.fail_to_pass) & set(self.pass_to_pass)
        if both:
            raise ValueError(
                f"{self.task_id}: tests in both fail_to_pass and pass_to_pass: "
                f"{sorted(both)}"
            )
        for missing in (p for p in ("task.yaml", "test.patch") if not (self.dir / p).exists()):
            raise FileNotFoundError(f"{self.task_id}: missing {missing}")

        if not require_tags:
            return

        absent = sorted(set(REQUIRED_TAGS) - set(self.tags))
        if absent:
            raise ValueError(f"{self.task_id}: task.yaml missing tags: {absent}")
        for key, expected in REQUIRED_TAGS.items():
            value = self.tags[key]
            # bool is a subclass of int, so check it first or every bool passes
            # an int check and vice versa.
            if expected is int and isinstance(value, bool):
                raise TypeError(f"{self.task_id}: tag {key!r} should be int, got bool")
            if not isinstance(value, expected):
                raise TypeError(
                    f"{self.task_id}: tag {key!r} should be "
                    f"{getattr(expected, '__name__', expected)}, got "
                    f"{type(value).__name__}"
                )
        if self.ticket_type not in VALID_TICKET_TYPES:
            raise ValueError(
                f"{self.task_id}: ticket_type {self.ticket_type!r} not in "
                f"{sorted(VALID_TICKET_TYPES)}"
            )
        # is_feature exists for convenient slicing, so it must not disagree with
        # the field it summarises.
        if self.is_feature != (self.ticket_type == "feature"):
            raise ValueError(
                f"{self.task_id}: is_feature={self.is_feature} contradicts "
                f"ticket_type={self.ticket_type!r}"
            )
        if self.commit_date is None:
            raise ValueError(
                f"{self.task_id}: commit_date is required -- report/ derives the "
                f"per-model contamination flag from it"
            )
