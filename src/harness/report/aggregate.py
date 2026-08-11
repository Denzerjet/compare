"""Turn run directories into comparable numbers.

Reads only what is on disk, so a completed run can be re-aggregated after a
reporting fix without re-running anything.

Two decisions here carry the weight of the whole comparison:

  - **`loc_ratio` is averaged over RESOLVED attempts only.** The ratio of a patch
    that didn't work measures something else entirely.
  - **Cost is reported twice** -- total across all tasks, and per *solved* task. A
    model solving 40% cheaply can beat one solving 60% expensively on cost-per-solve,
    and that is invisible if only one figure is shown.

`harness_error` counts are surfaced next to the resolve rate rather than in an
appendix: they are the one failure type that can manufacture a model difference out
of our own defects, so a materially uneven rate invalidates the comparison until
explained.
"""

from __future__ import annotations

import json
import statistics as stats
from dataclasses import dataclass, field
from pathlib import Path

from ..schema import Task

HARNESS_ROOT = Path(__file__).resolve().parents[3]
RESULTS = HARNESS_ROOT / "results"
TASKS = HARNESS_ROOT / "tasks"

# Slicing dimensions. Each maps a Task to a bucket label; every one is a tag recorded
# at mining time precisely so filtering happens here rather than being baked into the
# task set.
def _loc_band(t: Task) -> str:
    n = t.loc_changed
    return "1-5" if n <= 5 else "6-15" if n <= 15 else "16-29" if n <= 29 else "30+"


def _hunk_band(t: Task) -> str:
    return "1 site" if t.hunks_changed <= 1 else "2 sites" if t.hunks_changed == 2 else "3+ sites"


def _stmt_band(t: Task) -> str:
    return "<600ch" if t.statement_chars < 600 else "600-1500ch" if t.statement_chars < 1500 else "1500ch+"


DIMENSIONS: dict[str, callable] = {
    "ticket_type": lambda t: t.ticket_type,
    "has_reproduction": lambda t: "yes" if t.has_reproduction else "no",
    "loc_changed": _loc_band,
    "edit_sites": _hunk_band,
    "statement_len": _stmt_band,
    "statement_edited": lambda t: "yes" if t.tags.get("statement_needs_review") else "no",
    "area": lambda t: t.area,
}


@dataclass
class ModelRun:
    run_id: str
    model_key: str
    model_id: str
    n_tasks: int
    rows: dict = field(default_factory=dict)   # task_id -> merged grade.json

    @property
    def scored(self) -> dict:
        return {k: v for k, v in self.rows.items() if v.get("scorable")}

    @property
    def resolved(self) -> set[str]:
        return {k for k, v in self.rows.items()
                if v.get("grade") and v["grade"].get("resolved")}


def load_runs(run_ids: list[str] | None = None, results_dir: Path | None = None) -> list[ModelRun]:
    """Load runs. With no ids, pick the largest run per model -- which naturally
    excludes the 1-task smoke tests without needing to special-case tags."""
    results_dir = Path(results_dir or RESULTS)
    found: list[ModelRun] = []
    for d in sorted(results_dir.iterdir()) if results_dir.exists() else []:
        meta_path = d / "run.json"
        if not d.is_dir() or not meta_path.exists():
            continue
        if run_ids and d.name not in run_ids:
            continue
        meta = json.loads(meta_path.read_text())
        rows = {}
        for td in sorted(p for p in d.iterdir() if p.is_dir()):
            gp = td / "grade.json"
            if gp.exists():
                rows[td.name] = json.loads(gp.read_text())
        found.append(ModelRun(
            run_id=d.name, model_key=meta.get("model_key", "?"),
            model_id=(meta.get("model") or {}).get("model_id", "?"),
            n_tasks=len(rows), rows=rows,
        ))
    if run_ids:
        return found
    best: dict[str, ModelRun] = {}
    for r in found:
        if r.model_key not in best or r.n_tasks > best[r.model_key].n_tasks:
            best[r.model_key] = r
    return sorted(best.values(), key=lambda r: r.model_key)


def headline(run: ModelRun) -> dict:
    rows = run.rows
    n = len(rows)
    resolved = run.resolved
    scored = run.scored
    cost = sum(v.get("cost_usd", 0.0) for v in rows.values())
    steps = [v.get("steps", 0) for v in rows.values()]
    terms: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    for v in rows.values():
        terms[v.get("termination", "?")] = terms.get(v.get("termination", "?"), 0) + 1
        oc = (v.get("grade") or {}).get("outcome", "not_scored")
        outcomes[oc] = outcomes.get(oc, 0) + 1
    ratios = [
        v["grade"]["loc_ratio"] for k, v in rows.items()
        if k in resolved and (v.get("grade") or {}).get("loc_ratio") is not None
    ]
    return {
        "run_id": run.run_id, "model_key": run.model_key, "model_id": run.model_id,
        "n_tasks": n, "n_scored": len(scored),
        "n_resolved": len(resolved),
        "resolve_rate": len(resolved) / n if n else 0.0,
        "cost_total": cost,
        "cost_per_task": cost / n if n else 0.0,
        # None rather than 0 when nothing was solved: a zero here would read as "free",
        # when it actually means the denominator is empty.
        "cost_per_solved": (cost / len(resolved)) if resolved else None,
        "median_steps": stats.median(steps) if steps else 0,
        "truncated": terms.get("truncated", 0),
        "harness_errors": terms.get("harness_error", 0) + terms.get("api_error", 0),
        "terminations": dict(sorted(terms.items())),
        "outcomes": dict(sorted(outcomes.items())),
        "median_loc_ratio": stats.median(ratios) if ratios else None,
        "total_tokens": sum(
            v.get("input_tokens", 0) + v.get("output_tokens", 0)
            + v.get("cache_read_tokens", 0) + v.get("cache_write_tokens", 0)
            for v in rows.values()
        ),
    }


def by_dimension(runs: list[ModelRun], tasks: dict[str, Task]) -> dict:
    """resolve counts per bucket per model, for every recorded slicing dimension."""
    out: dict = {}
    for dim, fn in DIMENSIONS.items():
        buckets: dict[str, dict] = {}
        for task_id, task in tasks.items():
            label = fn(task)
            b = buckets.setdefault(label, {"n": 0, "models": {}})
            b["n"] += 1
            for r in runs:
                cell = b["models"].setdefault(r.model_key, {"resolved": 0, "seen": 0})
                if task_id in r.rows:
                    cell["seen"] += 1
                    if task_id in r.resolved:
                        cell["resolved"] += 1
        # Largest bucket first; `area` has a long tail that is noise below a few tasks.
        out[dim] = dict(sorted(buckets.items(), key=lambda kv: -kv[1]["n"]))
    return out


def discordant_pairs(runs: list[ModelRun]) -> dict:
    """Head-to-head on tasks where two models DISAGREE.

    This is the statistically meaningful comparison, not the difference of two
    resolve rates: both models ran the identical task set, so the paired counts are
    what carry signal. Two models at 40% and 43% could differ on 3 tasks or on 30 --
    the rates cannot tell you which, and only the second is evidence.
    """
    out: dict = {}
    for i, a in enumerate(runs):
        for b in runs[i + 1:]:
            shared = set(a.rows) & set(b.rows)
            a_only = sorted(t for t in shared if t in a.resolved and t not in b.resolved)
            b_only = sorted(t for t in shared if t in b.resolved and t not in a.resolved)
            both = sorted(t for t in shared if t in a.resolved and t in b.resolved)
            out[f"{a.model_key} vs {b.model_key}"] = {
                "shared": len(shared), "both_solved": len(both),
                "neither": len(shared) - len(both) - len(a_only) - len(b_only),
                f"only_{a.model_key}": len(a_only),
                f"only_{b.model_key}": len(b_only),
                "discordant": len(a_only) + len(b_only),
                "examples": {f"only_{a.model_key}": a_only[:5], f"only_{b.model_key}": b_only[:5]},
            }
    return out


def load_tasks(tasks_dir: Path | None = None) -> dict[str, Task]:
    tasks_dir = Path(tasks_dir or TASKS)
    return {
        d.name: Task.load(d, require_tags=True)
        for d in sorted(tasks_dir.iterdir()) if d.is_dir() and (d / "task.yaml").exists()
    }


def build(run_ids: list[str] | None = None) -> dict:
    runs = load_runs(run_ids)
    tasks = load_tasks()
    return {
        "models": [headline(r) for r in runs],
        "dimensions": by_dimension(runs, tasks),
        "head_to_head": discordant_pairs(runs),
        "n_tasks_available": len(tasks),
    }
