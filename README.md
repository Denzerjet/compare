# django-eval

A harness for comparing coding models on real bug-fixing work, using
[django/django](https://github.com/django/django) as the task source.

Status: **step 1 of 3 complete.** Grading works end to end and is covered by
tests against a real fixture task. No mining and no model runs yet. See
[Build order](#build-order).

---

## Goal

Produce a defensible ranking of coding models on their ability to fix real bugs
in a large, unfamiliar Python codebase.

"Defensible" is doing work in that sentence. The output is not a set of sample
transcripts to read and judge by feel — it is a machine-checkable resolve rate
per model, over 100 tasks, with every model run under provably identical
conditions. The design below is mostly in service of two threats to that:
**grading that doesn't mean what it claims**, and **differences between models
that are really differences between harnesses**.

### What this measures

Given a bug report and a repository, can the model locate the defect and patch
it correctly, reasoning from the source alone?

### What this deliberately does not measure

Debugging persistence. The model cannot run the test suite (see
[Loop policy](#loop-policy)), so there is no edit → test → revise cycle. This
is a code-comprehension eval, not an iterate-to-green eval. That is a real
narrowing of scope and should be stated whenever results are reported.

---

## Running what exists

Requires a running docker daemon. Local Python only needs to run the harness —
django itself never runs on the host (it requires 3.12+; the container has
3.13).

```bash
git clone https://github.com/django/django.git repo/django
python3 -m venv .venv && ./.venv/bin/pip install pyyaml
docker build -t harness/django:py313-v1 -f src/harness/env/Dockerfile src/harness/env/
./.venv/bin/python -m unittest discover -s tests -t . -v
```

## Task construction

Tasks are mined from django's own git history rather than authored by hand.

The pattern: find a commit that both fixes a bug *and* adds tests covering the
fix. Split it — tests on one side, source change on the other. The model is
given the repository at the parent commit plus the new tests applied, and must
make those tests pass without breaking any that already passed.

This buys three things hand-authoring can't. Ground truth is free: the real fix
is right there in `solution.patch`. The pass/fail signal is objective, so
scoring involves no judgment. And the bugs are real ones that really shipped,
with the natural difficulty distribution that follows.

### Contamination

Django is heavily represented in every current model's training data, and
SWE-bench-Verified — which is largely django — is a widely published benchmark.
Mining commits from before a model's training cutoff risks measuring
memorization instead of capability.

Mitigation, in two parts:

1. Mine a window **wider** than any plausible cutoff (~18 months proposed, not
   yet locked; see [Open questions](#open-questions)). A wide window is also
   what's needed to yield 100 tasks that survive validation, so the two
   pressures point the same way.
2. Record `commit_date` on every task and slice results by it at analysis time.

Part 2 is what makes model selection deferrable: adding a model with a later
cutoff costs a filter argument, not a re-mine.

### Validation is the load-bearing step

Mining produces a large fraction of garbage — commits that touch tests
incidentally, tests that were already passing, fixes that can't run in this
image. Nothing enters [tasks/manifest.jsonl](tasks/manifest.jsonl) until
[src/harness/validate.py](src/harness/validate.py) confirms, in **two runs**:

1. At `base_commit` + `test.patch`: every `fail_to_pass` test **fails**, every
   `pass_to_pass` test **passes**.
2. With `solution.patch` additionally applied: **all** of them pass.

Rejections are logged with a reason. Skipping this step is the most common way
an eval ends up measuring noise, and no amount of care elsewhere recovers from
it.

**Why each run earns its place**, since they're asymmetric:

Run 1 is high-yield. If `fail_to_pass` already passes before any fix, the model
gets credit for doing nothing — and in the grading output that is *indis­
tinguishable* from a real solve. Its `pass_to_pass` half also establishes the
regression baseline, which is what makes a later `pass_to_pass` failure
attributable to the model's source change rather than to test-population effects
from applying `test.patch`.

Run 2 is low-yield but high-consequence. django won't merge a red commit, so the
reference fix passes by construction *in django's CI* — but `solution.patch` is
the output of our own `mine/split.py`, and run 2 is the only thing that ever
exercises that code. A bad split, or a fix needing something absent from this
sqlite-only image, produces a task that fails 100% of models while looking
exactly like a very hard one.

**There is deliberately no third criterion.** An earlier design re-ran both
states to reject non-deterministic tasks. Dropped: `unittest` order is
deterministic, so an identical re-run cannot detect order dependence, and the one
thing it did sample — per-process hash-seed variation — is eliminated outright by
`PYTHONHASHSEED=0` in the image. Reproducibility is now a property of the
environment rather than something each task is tested for. Genuine flakiness is
caught where it matters instead: an unexpected `pass_to_pass` failure is
confirmed by a second run at *grade* time before being recorded as a regression.

---

## Loop policy

Every model runs under the identical scaffolding in
[src/harness/run/loop.py](src/harness/run/loop.py): same tool schemas, same
system prompt, same constants. The only variable across runs is the model
itself. These values live in [config/run.yaml](config/run.yaml) and are copied
into every `results/<run_id>/run.json`.

| Constant | Value | Rationale |
|---|---|---|
| `max_steps` | 50 | Runaway backstop. Hitting it is a failure to solve. |
| `allow_test_execution` | false | No verification signal; the model reasons from source. |
| `reveal_test_names` | false | Test names point straight at the bug location. |
| `reveal_step_budget` | false | Not the number, and not that a budget exists. |
| `attempts` | 3 | Single-shot rates over 100 tasks have rankings-inverting error bars. |

### These constants are frozen

They are part of the task definition, not tuning knobs. In particular: **if
models cluster at the step ceiling, the ceiling does not move.** Adjusting a
constant in response to observed results makes runs mutually incomparable and
converts the exercise into a harness comparison. A model that exhausts its
budget has failed to solve the task and is scored as such.

The corollary is that the constants were chosen blind, before any model was
run, and `max_steps` in particular is sized generously — from the exploration
depth the reference solutions imply, not from any model's behaviour.

### What a step is

One round trip of the conversation. The model cannot request a file and receive
its contents within a single inference call, so each step converts one piece of
newly discovered information into one next action. History is append-only:
step N's input is the full transcript of steps 1..N-1 plus the latest tool
result. A clean single-file fix runs ~8–12 steps; the tail is consumed by
wrong hypotheses and multi-file call-chain tracing.

Because context accumulates, cost per task grows roughly quadratically in step
count. `max_total_tokens` and `wall_clock_timeout_sec` bound that; both are
safety backstops, not fairness levers.

---

## Architecture

```
config/          harness constants and model registry — frozen per run
repo/            django/django clone (git-ignored)
tasks/           the benchmark itself — committed, reviewable in a diff
src/harness/
  mine/          git history → candidate tasks
  validate.py    candidate tasks → trusted tasks
  env/           hermetic per-task container + worktree
  run/           agent loop, tools, and one thin adapter per provider
  grade/         (task, patch) → pass/fail
  report/        results → resolve rates, CIs, agreement matrix
results/         per-run outputs (git-ignored)
tests/           tests for the harness — grading must itself be trustworthy
```

Three properties of this split matter more than the file names:

**`grade/` never sees the model.** Grading is a pure function of
`(task, patch)`. This keeps scoring bit-identical across models and lets old
runs be re-graded after a grader bug fix, without re-running any inference.

**Adapters are leaves.** All scaffolding — tools, prompt, step accounting —
lives in `run/loop.py`. Each `run/adapters/*.py` is a thin translation to one
provider's API. Per-model tuning would live here, and doesn't exist by design.

**`tasks/` is a committed artifact; `repo/` and `results/` are not.** The
benchmark should be reviewable, diffable, and stable across runs.

### Task layout

```
tasks/<task_id>/
  task.yaml              spec — see below
  problem_statement.md   what the model sees
  test.patch             tests from the fix commit, applied before eval
  solution.patch         reference fix — withheld from the model
  provenance.json        sha, date, author, Trac ticket, mining rationale
```

```yaml
task_id: django__django-37198
base_commit: ea6b17b4815d36f6cc7780fdec303d27997eca49
django_version: "6.1.dev"
env_image: harness/django:py313-v1
test_labels: [utils_tests.test_http]          # what runtests.py is handed
fail_to_pass: [utils_tests.test_http.ContentDispositionHeaderTests.test_basic]
pass_to_pass: [...]                           # 51 further ids, enumerated
commit_date: 2026-07-27
tags: {area: utils.http, loc_changed: 2, files_changed: 1, difficulty: easy}
```

Two schema points that cost real debugging time to get right:

**Test ids are always method-level** (`module.Class.method`), never bare method
names. A single django test module frequently defines the same method name in
several classes — `utils_tests.test_http` has four separate `test_basic`
methods — so a bare name silently matches the wrong test.

**`fail_to_pass` tests are not necessarily new.** Django commits often fix a bug
by adding cases to an *existing* parameterised test, so the named method already
exists and passes at `base_commit`. Mining must not assume the test is absent
before `test.patch`; the only thing that defines a task is the fail→pass
transition.

There is no `install` step: django is put on `PYTHONPATH` rather than
pip-installed, so nothing is written into the mounted worktree (an `egg-info`
directory would pollute the `git diff` used to extract the model's patch) and
graded runs need no network.

### How grading works

`grade(task, patch)` performs a fixed sequence, and the order is
load-bearing:

1. Fresh git worktree at `base_commit`.
2. Apply the candidate patch (a model's output, or `solution.patch`).
3. **Revert `tests/`** — discards any test edits the patch made.
4. Apply the task's `test.patch`.
5. Run the task's `test_labels` in the container, network disabled.

Step 3 is why a patch cannot buy a pass by weakening the tests it is judged by.
`tests/test_grading.py` verifies this with a sabotage patch that neuters the
failing assertions, plus a negative control confirming that sabotage *does*
succeed when step 3 is skipped — so the test is known to have teeth rather than
passing vacuously.

**Outcomes are collected, not parsed.** The obvious approach — run
`--verbosity 2` and regex the `... ok / FAIL` lines — misgrades django's
`subTest`-based tests, and the fixture task is one of them. Observed output for
a method whose subtests fail:

```
test_basic (....ContentDispositionHeaderTests.test_basic) ...          <- blank
  test_basic (....test_basic) (is_attachment=True, filename='\n') ... FAIL
```

The enclosing method's status line is empty, and the failures appear only under
synthetic ids carrying parameter suffixes that match no `fail_to_pass` entry. A
regex parser reads that method as passing or absent. So instead
[env/inject/harness_runner.py](src/harness/env/inject/harness_runner.py) hooks
`unittest`'s `TestResult` — selected through `TEST_RUNNER` in an injected
settings module — and writes JSON keyed by method id, aggregating subtest
results so that any failing subtest makes the method `failed`.

The test-suite **exit code is deliberately ignored** when grading. A non-zero
exit is the normal, expected state of a task before it is fixed, so verdicts are
computed from individual test outcomes.

Runs that produce no trustworthy answer — timeout, crash before collection, a
half-written result file — are reported as their own status and never collapsed
into "unresolved". Scoring infrastructure failure as model failure is the
quietest way for an eval to start lying.

### Result layout

```
results/<run_id>/
  run.json               frozen config + harness git sha
  summary.json
  <task_id>/
    trajectory.jsonl     full message and tool trace
    model.patch          what the model produced
    grade.json           per-test outcomes, tokens, cost, wall time, step count
```

`run_id` is derived from timestamp, model, and a hash of the resolved config,
so a config change cannot silently overwrite or pool with an earlier run.

---

## Build order

1. ~~**Trustworthy grading.**~~ **Done.** Container image, worktree setup,
   result collector, `grade/`, and the `django__django-37198` fixture. 14 tests
   green in ~18s.
2. **The benchmark.** `mine/` and `validate.py` → 100 validated tasks.
   `validate.py` enforces exactly the three criteria already asserted against
   the fixture, so it is largely a matter of applying them at scale.
3. **The comparison.** `run/`, adapters, `report/`.

Deliberately in this order: a bug in step 1 invalidates everything downstream,
and 100 tasks is days of mining and validation to regenerate.

Throughput is not a current concern, so the runner may be sequential and
per-task containers need no pooling.

---

## Open questions

- **Model set** — not chosen. Deferred by design; nothing before step 3
  references a model. The only real coupling is that the earliest training
  cutoff in the set determines the contamination floor, which the wide mining
  window plus `commit_date` already absorbs.
- **Mining window** — ~18 months proposed, not locked. Should be settled from
  `mine/scan.py`'s actual candidate counts: expect to need roughly 400–800
  candidates to clear 100 survivors.
- **Termination reason in `grade.json`** — whether to record *why* a run ended
  (model declared done vs. hit the step cap). No effect on scoring; both are
  simply unsolved. Diagnostic value is in separating a wrong hypothesis from
  running out of room.
