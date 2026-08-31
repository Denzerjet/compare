| Metric             | Haiku 4.5 | GPT-5 Nano | Gemini-3.5-flash-lite |
| ------------------ | --------: | ---------: | --------------------: |
| Solved             |     8/100 |     13/100 |                14/100 |
| Cost               |     $6.25 |      $0.43 |                 $2.81 |
| Stopped            |        97 |         72 |                    90 |
| LOC_Ratio (median) |      0.96 |       1.00 |                  1.00 |

# compare

This is a small evaluation harness for comparing coding models on real
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

## Evaluation policy

The current loop allows at most 10 model steps per task. Test execution, test names, and the step budget are hidden from the model. Tool output is bounded, and edits are restricted to the django/ package. These settings are treated as part of the benchmark definition so results remain comparable between models.

See README_claude.md for some details on design rationale, NOTES.md works as well. README_codex.md provides a semblance of build instructions.
