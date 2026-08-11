"""Render an aggregate into markdown.

Two things this deliberately does NOT hide:

  - **Config drift between runs.** Every run's `max_steps` is printed, and a warning
    fires when they differ. Comparing a 50-step run against a 10-step run is not a
    model comparison, and that has to be visible in the artefact rather than
    remembered.
  - **Sample size.** Resolve rates are printed with their raw counts and, where the
    sample is small, an explicit note that the number cannot support a ranking.
"""

from __future__ import annotations

import json
from pathlib import Path

# Below this, a resolve-rate difference is indistinguishable from noise. At n=25 a
# 60% rate carries a 95% CI of roughly +/-19 points.
MIN_N_FOR_RANKING = 30


def _pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({part / whole:.0%})" if whole else f"{part}/0 (n/a)"


def render(agg: dict, run_meta: dict[str, dict]) -> str:
    L: list[str] = ["# Model comparison", ""]
    models = agg["models"]
    if not models:
        return "# Model comparison\n\nNo runs with results found.\n"

    # --- config consistency, first, because it gates everything below ------------
    steps = {m["model_key"]: run_meta.get(m["run_id"], {}).get("max_steps") for m in models}
    if len(set(steps.values())) > 1:
        L += [
            "> **These runs are NOT comparable.** `max_steps` differs between them: "
            + ", ".join(f"`{k}`={v}" for k, v in steps.items())
            + ". The step cap is the dominant driver of both cost and outcome, so "
              "differences below reflect configuration as much as model. Re-run under "
              "one config before drawing any conclusion.",
            "",
        ]
    small = [m for m in models if m["n_tasks"] < MIN_N_FOR_RANKING]
    if small:
        L += [
            f"> **Sample too small to rank.** "
            + ", ".join(f"`{m['model_key']}`: n={m['n_tasks']}" for m in small)
            + f". Below ~{MIN_N_FOR_RANKING} tasks a resolve-rate difference cannot be "
              "distinguished from noise; treat everything here as a smoke test of the "
              "harness rather than a measurement of the models.",
            "",
        ]

    # --- headline ---------------------------------------------------------------
    L += ["## Headline", "",
          "| model | steps | tasks | resolved | cost | $/task | $/solved | med steps | trunc | harness err |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        cps = f"${m['cost_per_solved']:.3f}" if m["cost_per_solved"] is not None else "—"
        L.append(
            f"| `{m['model_key']}` | {steps.get(m['model_key'], '?')} | {m['n_tasks']} | "
            f"{_pct(m['n_resolved'], m['n_tasks'])} | ${m['cost_total']:.3f} | "
            f"${m['cost_per_task']:.4f} | {cps} | {m['median_steps']} | "
            f"{m['truncated']} | {m['harness_errors']} |"
        )
    L.append("")
    L += ["`$/solved` is blank when nothing was solved — a zero there would read as "
          "\"free\" when it actually means the denominator is empty.", ""]

    # --- surgical-ness ----------------------------------------------------------
    L += ["## Patch size (solved tasks only)", ""]
    any_ratio = False
    for m in models:
        if m["median_loc_ratio"] is not None:
            any_ratio = True
            L.append(f"- `{m['model_key']}`: median `loc_ratio` "
                     f"{m['median_loc_ratio']:.2f} (1.00 = same size as django's own fix)")
    if not any_ratio:
        L.append("_No solved tasks, so no ratio to report. Aggregating this over failed "
                 "patches would measure something else._")
    L.append("")

    # --- outcome / termination taxonomy -----------------------------------------
    L += ["## Why runs ended", "",
          "Termination is how the loop stopped; outcome is what grading found. "
          "`no_credit` is scored as a failure but is not a model property.", ""]
    for m in models:
        L.append(f"**`{m['model_key']}`** — terminations: "
                 + ", ".join(f"{k}={v}" for k, v in m["terminations"].items())
                 + "; outcomes: " + ", ".join(f"{k}={v}" for k, v in m["outcomes"].items()))
    L.append("")

    # --- head to head -----------------------------------------------------------
    L += ["## Head-to-head (discordant pairs)", "",
          "The meaningful comparison is tasks where two models *disagree*, not the "
          "difference of two rates: both ran the identical set, so paired counts are "
          "what carry signal.", ""]
    if agg["head_to_head"]:
        L += ["| pair | shared | both | neither | discordant |", "|---|---|---|---|---|"]
        for pair, d in agg["head_to_head"].items():
            L.append(f"| {pair} | {d['shared']} | {d['both_solved']} | {d['neither']} | "
                     f"{d['discordant']} |")
    else:
        L.append("_Fewer than two runs; nothing to pair._")
    L.append("")

    # --- slices -----------------------------------------------------------------
    L += ["## Resolve rate by task property", "",
          "Every dimension here is a tag recorded at mining time, so filtering happens "
          "at analysis rather than being baked into the task set.", ""]
    for dim, buckets in agg["dimensions"].items():
        rows = [(k, v) for k, v in buckets.items() if v["n"] > 0][:8]
        if not rows:
            continue
        keys = [m["model_key"] for m in models]
        L += [f"### {dim}", "", "| bucket | tasks | " + " | ".join(f"`{k}`" for k in keys) + " |",
              "|---" * (len(keys) + 2) + "|"]
        for label, b in rows:
            cells = []
            for k in keys:
                c = b["models"].get(k, {"resolved": 0, "seen": 0})
                cells.append(_pct(c["resolved"], c["seen"]) if c["seen"] else "—")
            L.append(f"| {label} | {b['n']} | " + " | ".join(cells) + " |")
        L.append("")
    return "\n".join(L) + "\n"


def write(agg: dict, run_meta: dict[str, dict], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(agg, run_meta))
    (out.parent / "report.json").write_text(json.dumps(agg, indent=2) + "\n")
    return out
