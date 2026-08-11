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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mine", help="build validated tasks from django history")
    m.add_argument("--target", type=int, default=100)
    m.add_argument("--tasks-dir", default=None)
    m.set_defaults(func=cmd_mine)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
