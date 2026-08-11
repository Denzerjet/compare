# Working log

Last updated: 2026-08-10. Companion to [README.md](README.md) — the README is the
spec, this is the running state and the open questions.

## Where we are

**Step 1 (grading) complete.** 20 tests green via
`./.venv/bin/python -m unittest discover -s tests -t .`

**Step 2 (mining) — 82 valid tasks on disk**, manifest rebuilt, all loadable under
strict tag validation. The sweep stopped because **code.djangoproject.com went
unreachable**, not because of a harness fault: github/pypi/www.djangoproject.com
all answered in <1s while Trac returned zero bytes. A circuit breaker now aborts
after 5 consecutive Trac failures instead of grinding through the pool.

**DO NOT hammer Trac.** It is community-run and was down as of last check. Wait
for it to recover before resuming; the 100 cached tickets in `repo/.trac-cache/`
are reused, so a resume only fetches what it still needs.

Composition against target:

| bucket | have | target | pool remaining |
|---|---|---|---|
| large (>=50 LOC) | 5 | 25 | 35 candidates, early rejection rate looked high (3/3) |
| representative | 77 | 75 | met |
| total | 82 | 100 | |

**The total is not the real gap.** 82 vs 100 is a ~9% difference in error bars.
The large-patch slice at 5/25 is the meaningful shortfall, and it may not be
reachable: the >=50 LOC pool is only 40 candidates and big commits reject more
often (`no_passing_tests` -- every test in the label fails at base, plausible when
a commit restructures test infrastructure). Options if it stays short: relax to
>=30 LOC (141 candidates) or cut the slice target.

Resume with:

```bash
PYTHONPATH=src ./.venv/bin/python -m harness.cli mine --target 100
```

Two passes, resumable: task ids on disk are counted toward their bucket and
skipped, so this continues rather than restarting.

**Step 3 (`run/`, `report/`) not started.** No model has been run; no LLM API call
has been made at any point in this project.

## Decisions made

**Loop constants** ([config/run.yaml](config/run.yaml)) — frozen by policy: they
are part of the task definition, not tuning knobs, and are not to be adjusted in
response to observed results.

| | |
|---|---|
| `max_steps` | **50 in the file — 25 proposed, still unconfirmed** |
| `attempts` | 1 |
| `allow_test_execution` | false |
| `reveal_test_names` | false |
| `reveal_step_budget` | false |
| `prompt_caching` | true |
| `context_compaction` / `context_editing` | false |
| `task_budget` | none (injects a countdown the model can read) |

The model-facing prompt is a frozen artifact at
[config/system_prompt.md](config/system_prompt.md); it tells the model to treat
the existing test suite as correct and confine changes to `django/`.

**Mining policy** ([config/mining.yaml](config/mining.yaml)) — governing
principle is **flag, don't reject**. Only hard exclusions are cases we cannot
grade trustworthily (GIS/postgres/selenium/memcached/redis, deprecation-gated
tests, >120s labels). No quotas of any kind: no difficulty stratification, no
subsystem balancing. 24-month window. Everything else is a recorded tag for
analysis-time slicing, which puts the burden on `report/` to surface the
breakdowns by default.

**Validation is 2 runs per task, not 4.** Runs 3 and 4 (the determinism repeat)
were dropped — see Reasoning below.

## Scoring design

**One task set, every metric on all 100 tasks.** An earlier proposal split the
100 into four 25-task buckets, one per metric. Rejected because LOC and token
count are recorded for free on every task — they are properties of the output,
not separate experiments — so partitioning costs 4x the statistical power for
identical spend. At n=25 a model scoring 60% has a 95% CI of roughly +/-19
points, which cannot rank anything.

**Three axes, scored on every attempt:**

| Axis | Field | Aggregate over |
|---|---|---|
| Correctness (primary) | `resolved` / `outcome` | all tasks |
| Surgical-ness | `loc_ratio` = model LOC / reference LOC | **RESOLVED only** |
| Efficiency | tokens, cost | both: total across all, and median per solved |

`loc_ratio` is aggregated over solved attempts only — the ratio of a patch that
didn't work measures something else. Cost is reported both ways on purpose: a
model solving 40% cheaply may beat one solving 60% expensively on
cost-per-solve, and that is invisible if only one figure is shown.

**Both LOC figures come from the same function** (`grade.diff_loc`) applied to
diff text. A ratio between two differently-computed numbers is meaningless. Note
it counts formatting churn as change (django is black-formatted at 88 cols), so
read the ratio as a distribution, not a threshold.

**Recorded on failures too.** A 400-line diff that broke tests, a 2-line diff
that fixed nothing, and an empty diff are three different findings that a bare
`resolved=False` flattens into one.

**Outcome taxonomy** (`grade.Outcome`) — what makes those aggregates readable.
Without it, `no_patch` registers as LOC 0 and reads as "admirably surgical":

`resolved` / `regression` (target fixed, broke something else) / `tests_failed` /
`no_patch` (empty diff) / `unapplyable` (not a valid diff) / `baseline` (a
validation run, no candidate) / `harness_error` (not scored).

**Rejected criteria, and why** — both were reasonable goals with brittle
encodings:

- *Fail if model LOC > reference LOC.* The reference is one implementation's
  length, not a correctness threshold; a legitimately more defensive fix can be
  longer. Knife-edge at +/-1 line, and formatting alone moves the count. Kept as
  a continuous ratio instead.
- *Least-tokens-passes, rest fail.* Relative, so a model's score stops being a
  property of the model and adding a 4th model retroactively changes earlier
  results — which breaks the staged-budget pooling plan. Fixes the pass rate at
  1/3 by construction. And tokenizers differ across providers, so raw
  cross-provider token counts measure tokenization as much as efficiency; use
  cost or wall-clock for cross-vendor comparison.
- *Point totals across categories.* Mixes zero-sum scoring (token ranking) with
  absolute, and sums different definitions of "pass". Per-axis table is good; the
  total is not interpretable. If one headline number is wanted, sum **ranks**
  (Borda), keeping components visible.

**Tokens/cost live in `run/`, not `grade/`.** Grading is a pure function of
`(task, patch)` with no knowledge of models — that is what keeps verdicts
identical across models and old runs re-gradable. Token counts and termination
reason are agent-loop properties, recorded by `run/` and merged into
`grade.json` at that layer.

**Composition:** ~75 representative + ~25 deliberately sampled at >=50 LOC for a
multi-line-reasoning slice (88 candidates available at that threshold — needs
`source_loc_range` in mining.yaml raised from `[1, 80]`). This is a deliberate
reversal of the earlier no-stratification call, for a stated purpose rather than
difficulty balancing.

**Task ordering: latest commit first.** Contamination means the fix is already in
training data, so the *newest* commits are the cleanest. An earlier plan to sort
earliest-first would have maximised exposure. 239 of 573 candidates are from
2025-10-01 onward.

## Implemented

**Grading (step 1)** — outcome taxonomy, `patch_loc`/`reference_loc`/`loc_ratio`,
grade-time retry (`RETRIABLE` x2, `TIMEOUT` x1, `harness_retries` recorded),
regression confirmation via a second run with non-reproducing failures recorded in
`flaky_tests`, `PYTHONHASHSEED=0` baked into the image and guarded by a test.

**Mining (step 2)** — all new this session:

- `mine/scan.py` — git log -> candidates, metadata filters only, newest first.
  485 candidates from the 24-month window.
- `mine/split.py` — commit -> test.patch / solution.patch, and test-label
  derivation (module-level where possible; a supporting file falls back to its
  package only if no test module in that package was touched).
- `mine/statement.py` — Trac `?format=tab` gives structured fields including
  `type`, so ticket_type is real data. Title + description only; never comments.
- `mine/emit.py` — writes task.yaml / patches / problem_statement.md /
  provenance.json, then loads the task back with strict tag validation so a task
  that cannot round-trip never reaches the manifest. Manifest is *rebuilt* from
  disk, never appended, so re-mining is idempotent.
- `validate.py` — the two criteria, with typed rejection reasons.
- `cli.py` — `harness mine --target N`.
- `schema.py` — required tags validated on load (lenient by default so the
  hand-written fixture still loads, strict for mined tasks).

**`REGRESSION` is untested, by decision.** The code path exists in `_reclassify`
and is load-bearing (flaky-test confirmation depends on regressions being
distinguishable from target-test failures), so it stays. No test covers it and
none is planned: the suite asserts only what it automates.

## Findings from the mining pilot

**`fail_to_pass` is observed, never inferred from the diff.** This was the single
most valuable design change. Run 1 records which tests actually fail at
base_commit; `fail_to_pass` is `passes-after minus passes-before`. Every hazard we
had worried about dissolves: modified-existing-tests (the fixture is one), tests
added for already-working behaviour, and multi-commit tickets whose parent already
contains the fix all resolve themselves. Survival went from a predicted ~50% to a
measured 95%.

**Two silent bugs, both found only by running things.** Worth remembering that
this code path produced plausible-looking tasks with the wrong tests:

1. Keying "still failing" on run 1's test ids. A module whose new tests reference
   an API the fix introduces cannot import at base, so unittest emits one
   synthetic `unittest.loader._FailedTest.<module>` id that ceases to exist once
   the import succeeds -- so a good task looked permanently unresolved. Fixed by
   the set-difference definition.
2. That synthetic id carries the module's SHORT name, so stripping the prefix
   yielded `test_parallel` instead of `test_runner.test_parallel`. django matched
   nothing, and 26 tests vanished from the task with no error. Fixed by
   `resolve_modules()`, which reconciles against the commit's own touched test
   files, plus an `UNRESOLVED_LABEL` rejection so an unrunnable label can never
   pass quietly again.

**Module scoping, measured.** Narrowing labels to the modules containing failures
cut #37210 from 129s to 2.4s and #37233 from 39.8s to 2.0s. It does *not* shrink
single-huge-module tasks (`admin_views.tests` stays ~18s with 389 p2p) -- the 60s
rule governs those. `pass_to_pass` set size is therefore still large in places;
runtime, not test count, is the constraint.

**Trac statement quality, over 100 tickets fetched.** 100/100 fetched, 0 errors.
59 bug / 28 cleanup / 13 feature. Description median 1,185 chars, none empty, 65
carry a reproduction. Leak handling took two corrections:

- Descriptions often paste the fix as **raw unfenced diff text**, which
  fence-based stripping missed. A second pass now consumes unified-diff line runs;
  residual leak markers went 15 -> 0.
- A `/pull/` or `/commit/` URL is **not** a leak here: the agent loop has no
  network and no fetch tool, so a link it cannot follow reveals nothing. Counting
  those had inflated the leak figure.

Genuine review list is the statements we *altered* -- ~6 of 100 (analysis-section
truncation, code-bearing parenthetical stripped, or a pasted patch removed). Each
carries `statement_needs_review: true` in task.yaml with detail in
provenance.json, so the list is queryable rather than trusted.

**A caution about my own estimates.** Several were wrong by large factors and were
corrected only by measuring: validation cost (~30s/run predicted, 1.3-2.3s
actual), leak incidence (66% then 8%, actually ~6% after proper stripping), and
survival rate (50% predicted, 95% actual). Treat unmeasured figures in this file
as provisional.

## Open questions

1. `max_steps` — 50 in the file, 25 proposed. Budget no longer forces it: with
   caching on, 50 vs 25 is ~1.35x on cost, not the ~2x I claimed earlier. So this
   is now purely a measurement decision — a lower cap truncates more runs, and
   truncation scores as failure.
2. Task count — 100, or keep everything that validates and pick the eval subset
   at run time.
3. Whether to freeze the reporting spec (per-flag total/passes/rate tables per
   model plus aggregate, with discordant-pair counts) in `config/report.yaml`.
4. `schema.py` needs the new `mining.yaml` tag fields (`ticket_type`,
   `is_feature`, `statement_chars`, `has_reproduction`, `area`) before mining can
   write tasks.
5. Model set — **tabled.** Haiku 4.5 was briefly chosen then reverted; nothing was
   written, `config/models.yaml` is still empty. Constraints noted if it comes
   back: 200K context (makes the bounded-read requirement load-bearing, not just a
   cost lever), 4096-token cache minimum so early steps don't cache, and no
   adaptive thinking or `effort` — those error on 4.5, so a thinking policy would
   have to be agreed across a mixed-generation model set.
6. Run-side outcome taxonomy — `truncated`, `refused`, `invalid_tool_call`,
   `context_exceeded`, and the harness-vs-transport split. Discussed, not settled.
   Agreed so far: harness errors that survive retry score as failures, with a
   per-model count as the audit trail, and no manual intervention.

## Closed

- **`grade.json` termination-reason field** — keep it. Part of the failure
  taxonomy that makes the LOC and cost aggregates readable. Lives in `run/` (a
  loop property), merged into `grade.json` at that layer.
- **Validation: 1 run instead of 2?** — **No, staying at 2.** Deferring the
  `solution.patch` check to only unsolved tasks would trade ~10 min of free local
  compute for API spend, since a broken task wouldn't be discovered until after
  tokens had been spent on it. Wrong direction under a tight budget.
- **Validation: 4 runs down to 2** — done. The determinism repeat couldn't detect
  order dependence and its one real signal (hash-seed variance) is eliminated by
  `PYTHONHASHSEED=0`.

## Measured, not estimated

Everything here replaces an earlier guess of mine.

| Fact | Value |
|---|---|
| Full validation, 1 task (4 runs) | 12.6s → ~6.3s at 2 runs |
| Single test module | 1.3–2.3s |
| Heavy packages (`admin_views`, `migrations`) | 20–22s |
| Worktree creation | ~1.0s |
| Container memory | **103 MiB** — CPU-bound, not RAM-bound |
| Concurrency at N=6 | 0.68s/run (3.2x speedup) |
| Full sweep, 491 tasks @ 4 workers | **~20 min** at 2 runs/task |
| Structural candidates, 24 months | 491 (~20.5/month) |
| Area concentration | 28.3% `django/db/models`, 11.8% admin |
| LOC bands | 1-5: 33%, 6-15: 35%, 16-29: 18%, 30-49: 9%, 50-80: 5% |
| Python 3.13 at oldest window edge | Clean (2024-08-05, django 5.2-alpha) |
| Order independence | 6 modules x 3 shuffle seeds → 0 failures |

**Environment:** M1 MacBook Pro, 8 cores (4P+4E), 8GB RAM. **Docker Desktop**
(context `desktop-linux`) — not OrbStack, which I misidentified earlier. VM gets
8 CPUs / 4.1GB. Image `harness/django:py313-v1` is native arm64.

**Recommend 4 workers, not 6.** `admin_changelist` failed spuriously (`rc=1`, no
results file) when run straight after the 22s `migrations` job, then passed
cleanly alone. Contention, not a flaky test — and the reason the retry item above
matters.

## Reasoning worth not re-deriving

**Why the determinism repeat was dropped.** An identical re-run cannot detect
order dependence — `unittest` order is deterministic, so both runs execute
identically. The only thing it sampled was per-process hash-seed randomization,
which `PYTHONHASHSEED=0` eliminates outright. And criterion 1 already rules out
spurious `pass_to_pass` failures: it confirms that exact test population and
order passes at `base_commit` + `test.patch`, so grading differs by the source
change alone and any failure is correctly attributed to the patch.

**Why validation is needed at all, given django's quality.** It isn't checking
django — it's checking our commit→task split over 491 heterogeneous commits.
Run 1 is high-yield: it catches tasks that were never broken, which hand every
model free credit *indistinguishably from a real solve* in the grading output.
Run 2 is low-yield but high-consequence: it catches tasks impossible in our
reduced environment (sqlite-only, omitted deps), which fail 100% of models.
Neither signal is recoverable from a model's run.

**Why grading can't substitute for validation.** Grading is 1 run and already
does only the after-the-patch check. The 2 validation runs happen once per task
at mining time and observe the two states a model never produces: the repo with
no fix, and the repo with django's reference fix.

**Known pipeline hazards found today.** `fail_to_pass` may be a *modified
existing* test, not a new one (the fixture is), so miners keying on new test
functions mis-specify it. `one_task_per_ticket: true` taking the *last* commit of
a multi-commit ticket can make `base_commit` already contain the fix. Backend-
specific tests are *skipped* on sqlite, not failed.

## How to resume

```bash
cd /Users/kian/Desktop/cs/mirendil/takehome
docker build -t harness/django:py313-v1 -f src/harness/env/Dockerfile src/harness/env/  # picks up PYTHONHASHSEED
./.venv/bin/python -m unittest discover -s tests -t . -v
```

Requires Docker Desktop running and `repo/django` cloned (git-ignored, 354MB).

## Next actions

1. **Read the sweep result** — tasks written, the statement-review list, and the
   rejection breakdown by reason. If it fell short of 100, the reject counts say
   whether to widen the window or loosen a filter.
2. **Decide on statement review** — ~6 altered statements to eyeball, or accept
   them. Leakage inflates absolute resolve rates but is ranking-neutral, since
   every model sees the identical statement.
3. **Confirm `max_steps`** (50 in the file, 25 proposed) — the last frozen
   constant still unresolved, and it must be settled before any model run.
4. **Choose the model set** — Kian asked to sync before any model is run. Nothing
   in steps 1-2 touches an API.
5. Then `run/` (agent loop, adapters) and `report/`.
