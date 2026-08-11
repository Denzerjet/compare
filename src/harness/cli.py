"""Command line entry point.

    harness mine --target 100     scan -> statement -> validate -> write tasks/

Mining runs in two passes, because the large-patch slice has to be *targeted*
rather than encountered: recent django commits are overwhelmingly small (median
loc_changed is 10), so a single newest-first walk fills the target almost entirely
with small fixes. The >=50 LOC candidates are scattered across the whole pool.

Resumable by design. Task ids already on disk are counted toward their bucket and
skipped, so an interrupted sweep continues rather than restarting -- which matters
because Trac is flaky and the container runs are the expensive part.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

from .mine import emit, statement as stmt_mod
from .mine.scan import Candidate, load_config, scan
from .mine.split import split
from .schema import Task
from .validate import validate

# Trac (code.djangoproject.com) goes unreachable for stretches. Grinding through
# hundreds of 30s timeouts helps nobody and is rude to community infrastructure,
# so abort the sweep after this many consecutive failures.
MAX_CONSECUTIVE_TRAC_FAILURES = 5


class TracDown(Exception):
    pass


def _existing_tasks(tasks_dir: Path) -> dict[str, int]:
    """task_id -> loc_changed for everything already written."""
    out: dict[str, int] = {}
    if not tasks_dir.exists():
        return out
    for d in sorted(tasks_dir.iterdir()):
        if d.is_dir() and (d / "task.yaml").exists():
            try:
                out[d.name] = Task.load(d, require_tags=True).loc_changed
            except Exception:
                pass  # a half-written dir shouldn't block a resume
    return out


def _mine_pass(
    label: str,
    cands: list[Candidate],
    target: int,
    already: int,
    skip: set[str],
    state: dict,
) -> None:
    print(f"\n--- {label}: {already} already on disk, need {max(0, target - already)} "
          f"of {target} (pool {len(cands)}) ---", flush=True)
    written = already
    for cand in cands:
        if written >= target:
            break
        if cand.task_id in skip:
            continue
        prefix = f"[{label[:5]}] {written:>3}/{target} #{cand.ticket:<6}"

        try:
            st = stmt_mod.build(cand.ticket)
            state["trac_fails"] = 0
        except Exception as exc:
            state["trac_fails"] += 1
            state["errors"].append((cand.ticket, f"trac: {exc!r}"[:90]))
            print(f"{prefix} TRAC-ERROR ({state['trac_fails']}) {exc!r}"[:110], flush=True)
            if state["trac_fails"] >= MAX_CONSECUTIVE_TRAC_FAILURES:
                raise TracDown(
                    f"{state['trac_fails']} consecutive Trac failures -- "
                    f"code.djangoproject.com looks unreachable"
                )
            continue

        sp = split(cand)
        val = validate(cand, sp)
        if not val.ok:
            state["rejects"].append((cand.ticket, val.reject.value))
            print(f"{prefix} reject:{val.reject.value}", flush=True)
            continue

        try:
            emit.write_task(
                cand, sp, val,
                statement=st.to_markdown(),
                statement_source=st.source,
                ticket_type=st.ticket_type,
                statement_meta={
                    "needs_review": st.needs_review,
                    "truncated_at": st.truncated_at,
                    "stripped_parens": st.stripped_parens,
                    "stripped_diff_blocks": st.stripped_diff_blocks,
                    "unfollowable_links": st.unfollowable_links,
                    "residual_leaks": st.residual_leaks,
                },
            )
        except Exception as exc:
            state["errors"].append((cand.ticket, f"emit: {exc!r}"[:90]))
            print(f"{prefix} EMIT-ERROR {exc!r}"[:110], flush=True)
            continue

        written += 1
        skip.add(cand.task_id)
        state["written"].append(cand.task_id)
        if st.needs_review:
            state["review"].append(cand.task_id)
        print(
            f"{prefix} OK {st.ticket_type:<7} f2p={len(val.fail_to_pass):<3} "
            f"p2p={len(val.pass_to_pass):<4} loc={val.reference_loc:<4} "
            f"{val.graded_runtime_sec:>5.1f}s"
            + ("  REVIEW" if st.needs_review else ""),
            flush=True,
        )
    print(f"--- {label}: {written}/{target} ---", flush=True)


def cmd_mine(args: argparse.Namespace) -> int:
    cfg = load_config()
    cands = scan(config=cfg)
    tasks_dir = Path(args.tasks_dir) if args.tasks_dir else emit.TASKS_DIR

    slice_cfg = (cfg.get("sampling") or {}).get("large_patch_slice") or {}
    lp_target = int(slice_cfg.get("count", 0))
    lp_min = int(slice_cfg.get("min_source_loc", 50))
    rep_target = max(0, args.target - lp_target)

    existing = _existing_tasks(tasks_dir)
    skip = set(existing)
    have_large = sum(1 for loc in existing.values() if loc >= lp_min)
    have_rep = len(existing) - have_large

    large = [c for c in cands if c.source_loc >= lp_min]
    rest = [c for c in cands if c.source_loc < lp_min]

    print(f"{len(cands)} candidates after metadata filters (newest first)")
    print(f"on disk: {len(existing)} tasks ({have_large} large, {have_rep} representative)")
    print(f"target : {lp_target} large (>={lp_min} LOC) + {rep_target} representative "
          f"= {args.target}")
    if len(large) < lp_target:
        print(f"WARNING: only {len(large)} candidates have >={lp_min} LOC; the large "
              f"slice cannot reach {lp_target} even if all validate")

    state = {"written": [], "review": [], "rejects": [], "errors": [], "trac_fails": 0}
    t0 = time.time()
    aborted = ""
    try:
        if lp_target <= 0:
            # Slice targeting off: one pass over every candidate. Bucketing here
            # would be wrong, not just redundant -- the representative pool
            # excludes large candidates, so it would mine past the target.
            _mine_pass("all", cands, args.target, len(existing), skip, state)
        else:
            _mine_pass("large-patch", large, lp_target, have_large, skip, state)
            _mine_pass("representative", rest, rep_target, have_rep, skip, state)
    except TracDown as exc:
        aborted = str(exc)

    n = emit.rebuild_manifest(tasks_dir)
    total = len(_existing_tasks(tasks_dir))
    final = _existing_tasks(tasks_dir)
    large_now = sum(1 for loc in final.values() if loc >= lp_min)

    print(f"\n{'=' * 70}")
    if aborted:
        print(f"ABORTED: {aborted}")
        print("Re-run when it recovers -- cached tickets and existing tasks are reused.\n")
    print(f"tasks on disk : {total}  ({large_now} large, {total - large_now} representative)")
    print(f"manifest rows : {n}")
    print(f"written now   : {len(state['written'])}   in {(time.time()-t0)/60:.1f} min")
    print(f"need review   : {len(state['review'])}")
    print(f"rejected      : {len(state['rejects'])}")
    for reason, c in collections.Counter(r for _, r in state["rejects"]).most_common():
        print(f"  {reason:24} {c}")
    if state["errors"]:
        print(f"errors        : {len(state['errors'])}")
        for tk, e in state["errors"][:5]:
            print(f"  #{tk} {e}")
    return 0 if total >= args.target and not aborted else 1


def cmd_resync(args: argparse.Namespace) -> int:
    """Recompute statement-derived tags from what is on disk, rebuild the manifest.

    Needed after a hand edit: `statement_chars` and `has_reproduction` are computed
    at emit time, so editing the statement leaves them stale and the integrity
    audit fails on drift. Touches no containers and re-validates nothing -- the
    statement is model-facing only and cannot affect a verdict.
    """
    import yaml
    from .mine.emit import HAND_EDITED_MARKER, has_reproduction, rebuild_manifest

    tasks_dir = Path(args.tasks_dir) if args.tasks_dir else emit.TASKS_DIR
    changed = []
    for d in sorted(tasks_dir.iterdir()):
        if not d.is_dir() or not (d / "task.yaml").exists():
            continue
        stmt = (d / "problem_statement.md").read_text()
        spec = yaml.safe_load((d / "task.yaml").read_text())
        tags = spec["tags"]
        before = (tags.get("statement_chars"), tags.get("has_reproduction"),
                  tags.get("statement_source"))
        tags["statement_chars"] = len(stmt)
        tags["has_reproduction"] = has_reproduction(stmt)
        if HAND_EDITED_MARKER in stmt:
            tags["statement_source"] = "hand_edited"
        after = (tags["statement_chars"], tags["has_reproduction"],
                 tags["statement_source"])
        if before != after:
            (d / "task.yaml").write_text(
                "# Generated by mine/. Do not hand-edit: re-mining overwrites it.\n"
                + yaml.safe_dump(spec, sort_keys=False, default_flow_style=False, width=88)
            )
            Task.load(d, require_tags=True)
            changed.append((d.name, before, after))

    n = rebuild_manifest(tasks_dir)
    print(f"resynced {len(changed)} task(s); manifest rebuilt ({n} rows)")
    for name, b, a in changed:
        print(f"  {name}: chars {b[0]}->{a[0]}  repro {b[1]}->{a[1]}  src {b[2]}->{a[2]}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run one model over N tasks and grade each result."""
    import hashlib
    import os
    import subprocess
    import yaml

    from .grade import grade
    from .run.adapters import build as build_adapter
    from .run.loop import Termination, run_task
    from .run.tools import ToolLimits

    root = Path(__file__).resolve().parents[2]
    mcfg = yaml.safe_load((root / "config" / "models.yaml").read_text())
    rcfg = yaml.safe_load((root / "config" / "run.yaml").read_text())
    if args.model not in mcfg["models"]:
        print(f"unknown model {args.model!r}; known: {sorted(mcfg['models'])}")
        return 2
    model_cfg = mcfg["models"][args.model]
    limits = ToolLimits(**mcfg["tool_limits"])
    system_prompt = _system_prompt(root / rcfg["system_prompt"])
    max_steps = int(rcfg["max_steps"])

    tasks = sorted(p for p in Path("tasks").iterdir() if p.is_dir())
    tasks = [Task.load(p, require_tags=True) for p in tasks][: args.limit]
    if not tasks:
        print("no tasks found")
        return 2

    harness_sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True).stdout.strip() or "uncommitted"
    cfg_hash = hashlib.sha256(
        json.dumps({"run": rcfg, "model": model_cfg, "limits": mcfg["tool_limits"]},
                   sort_keys=True).encode()
    ).hexdigest()[:8]
    run_id = f"{args.model}-{cfg_hash}" + (f"-{args.tag}" if args.tag else "")
    run_dir = root / "results" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # Frozen inputs, so a cost or score can always be reproduced after the fact.
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": run_id, "harness_sha": harness_sha, "model_key": args.model,
        "model": model_cfg, "run_config": rcfg, "tool_limits": mcfg["tool_limits"],
        "n_tasks": len(tasks), "task_ids": [t.task_id for t in tasks],
    }, indent=2) + "\n")

    key_env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
               "google": "GEMINI_API_KEY"}[model_cfg["provider"]]
    if not os.environ.get(key_env):
        print(f"No {key_env} set for provider {model_cfg['provider']!r}. "
              f"Export one and re-run; nothing has been spent.")
        return 2
    adapter = build_adapter(model_cfg, api_key=os.environ[key_env])

    print(f"run_id     : {run_id}")
    print(f"model      : {model_cfg['model_id']}   max_steps={max_steps}")
    print(f"tasks      : {len(tasks)}")
    print(f"read bound : {limits.max_read_lines} lines\n", flush=True)

    rows, spend = [], 0.0
    out_of_credit = False
    for i, task in enumerate(tasks, 1):
        out = run_dir / task.task_id
        if out_of_credit:
            # No further requests: every remaining task would fail identically. Written
            # as a real row so the model still has a verdict on all 100 tasks, which
            # the paired comparison requires.
            out.mkdir(parents=True, exist_ok=True)
            (out / "model.patch").write_text("")
            (out / "grade.json").write_text(json.dumps({
                "task_id": task.task_id, "model": model_cfg["model_id"],
                "termination": "no_credit", "scorable": True, "steps": 0,
                "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
                "cache_write_tokens": 0, "cost_usd": 0.0, "wall_clock_sec": 0.0,
                "tool_calls": {}, "detail": "skipped: credit exhausted earlier in the run",
                "grade": {"outcome": "no_credit", "resolved": False, "status": "ok",
                          "loc_ratio": None, "patch_loc": 0},
            }, indent=2) + "\n")
            print(f"[{i}/{len(tasks)}] {task.task_id:26} no_credit      (skipped)", flush=True)
            continue
        r = run_task(task, adapter, model_cfg, system_prompt=system_prompt,
                     max_steps=max_steps, limits=limits, out_dir=out, repo=None)
        if r.termination is Termination.NO_CREDIT:
            out_of_credit = True
            print(f"    !! credit exhausted: {r.detail[:120]}", flush=True)
        spend += r.cost_usd
        g = grade(task, r.patch) if r.scorable else None
        merged = r.to_dict()
        merged["grade"] = g.to_dict() if g else None
        (out / "grade.json").write_text(json.dumps(merged, indent=2) + "\n")
        verdict = (g.outcome.value if g else r.termination.value)
        cache_pct = (r.cache_read_tokens / max(1, r.input_tokens + r.cache_read_tokens)) * 100
        print(f"[{i}/{len(tasks)}] {task.task_id:26} {verdict:14} "
              f"steps={r.steps:<3} ${r.cost_usd:.3f} cache={cache_pct:>4.0f}% "
              f"{r.wall_clock_sec:>5.0f}s  {r.termination.value}", flush=True)
        rows.append((task.task_id, r, g))

    solved = [x for x in rows if x[2] and x[2].resolved]
    print(f"\n{'=' * 70}")
    print(f"resolved      : {len(solved)}/{len(rows)}")
    print(f"total cost    : ${spend:.2f}   mean ${spend/max(1,len(rows)):.3f}/task")
    print(f"projected 100 : ${spend/max(1,len(rows))*100:.2f}")
    steps = [r.steps for _, r, _ in rows]
    print(f"steps         : min={min(steps)} median={sorted(steps)[len(steps)//2]} max={max(steps)}")
    trunc = sum(1 for _, r, _ in rows if r.termination is Termination.TRUNCATED)
    print(f"truncated     : {trunc}  (hit the {max_steps}-step cap)")
    unscored = [t for t, r, _ in rows if not r.scorable]
    if unscored:
        print(f"NOT SCORED    : {len(unscored)} {unscored}")
    if out_of_credit:
        done = len(rows)
        print(f"CREDIT EXHAUSTED after {done} tasks; {len(tasks) - done} marked "
              f"no_credit (scored as failures, flagged separately in the report)")
    return 0


def _system_prompt(path: Path) -> str:
    """Strip the HTML comment header from config/system_prompt.md.

    That header documents the constraints the text must respect; it is for us, not
    the model, and shipping it would leak that a step budget exists.
    """
    text = path.read_text()
    if text.lstrip().startswith("<!--"):
        text = text.split("-->", 1)[1]
    return text.strip()


def cmd_report(args: argparse.Namespace) -> int:
    """Aggregate finished runs into a markdown report. Reads disk only, costs nothing."""
    from .report.aggregate import build, load_runs
    from .report.render import write

    root = Path(__file__).resolve().parents[2]
    runs = load_runs(args.runs or None)
    runs = [r for r in runs if r.n_tasks > 0]
    if not runs:
        print("no runs with results found under results/")
        return 2

    # max_steps per run, so the renderer can warn when runs are not comparable.
    meta: dict[str, dict] = {}
    for r in runs:
        cfg = json.loads((root / "results" / r.run_id / "run.json").read_text())
        meta[r.run_id] = {"max_steps": (cfg.get("run_config") or {}).get("max_steps")}

    agg = build([r.run_id for r in runs])
    out = write(agg, meta, root / "results" / "report.md")
    print(f"runs included : {', '.join(r.run_id for r in runs)}")
    for m in agg["models"]:
        print(f"  {m['model_key']:24} {m['n_resolved']:>3}/{m['n_tasks']:<4} resolved  "
              f"${m['cost_total']:.3f}")
    print(f"\nwrote {out}")
    print(f"wrote {out.parent / 'report.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mine", help="build validated tasks from django history")
    m.add_argument("--target", type=int, default=100)
    m.add_argument("--tasks-dir", default=None)
    m.set_defaults(func=cmd_mine)
    r = sub.add_parser("resync", help="recompute statement-derived tags after a hand edit")
    r.add_argument("--tasks-dir", default=None)
    r.set_defaults(func=cmd_resync)
    ru = sub.add_parser("run", help="run a model over tasks and grade the results")
    ru.add_argument("--model", required=True, help="key from config/models.yaml")
    ru.add_argument("--limit", type=int, default=5, help="how many tasks")
    ru.add_argument("--tag", default=None, help="suffix for the run id")
    ru.set_defaults(func=cmd_run)
    rp = sub.add_parser("report", help="aggregate runs into results/report.md")
    rp.add_argument("--runs", nargs="*", default=None, help="run ids; default = largest per model")
    rp.set_defaults(func=cmd_report)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
