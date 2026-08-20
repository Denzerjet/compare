# django-eval

`django-eval` is a small evaluation harness for comparing coding models on real
bug fixes mined from Django's git history. Each task contains a bug report and a
repository checkout; the model must locate and patch the defect, and the harness
then grades the patch against tests derived from Django's original fix.

The harness keeps the evaluation consistent across providers by giving every
model the same prompt, tool set, step limit, and grading process. Agents may read,
search, list, and edit repository files, but they cannot run the test suite or
access the network during a task.

## Repository layout

- `config/` — model definitions and frozen mining/run settings
- `src/harness/mine/` — discovers and constructs tasks from Django commits
- `src/harness/run/` — provider-neutral agent loop, tools, and API adapters
- `src/harness/grade/` — applies and tests candidate patches
- `src/harness/report/` — aggregates results
- `tasks/` — committed benchmark tasks and manifest
- `tests/` — tests for the harness itself
- `results/` — generated model trajectories, patches, grades, and reports

## Requirements

- Python 3.10 or newer
- Docker with a running daemon
- A local clone of `django/django` at `repo/django`
- An API key for the provider used when running a model

## Setup

```bash
git clone https://github.com/django/django.git repo/django
python3 -m venv .venv
./.venv/bin/pip install -e .
docker build -t harness/django:py313-v1 \
  -f src/harness/env/Dockerfile src/harness/env/
```

Install the appropriate optional provider SDK before running a model. For
example:

```bash
./.venv/bin/pip install -e '.[anthropic]'
```

## Usage

Run the harness tests:

```bash
./.venv/bin/python -m unittest discover -s tests -t . -v
```

Mine and validate tasks:

```bash
./.venv/bin/harness mine --target 100
```

Run a configured model over a small task sample:

```bash
./.venv/bin/harness run --model MODEL_KEY --limit 5
```

Model keys and provider settings live in `config/models.yaml`. Set the matching
provider environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or
`GEMINI_API_KEY`) before starting a run.

Generate an aggregate report:

```bash
./.venv/bin/harness report
```

## Evaluation policy

The current loop allows at most 10 model steps per task. Test execution, test
names, and the step budget are hidden from the model. Tool output is bounded,
and edits are restricted to the `django/` package. These settings are treated as
part of the benchmark definition so results remain comparable between models.

See `README_claude.md` for the detailed design rationale and `NOTES.md` for the
project's working log and operational notes.
