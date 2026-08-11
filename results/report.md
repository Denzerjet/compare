# Model comparison

## Headline

| model | steps | tasks | resolved | cost | $/task | $/solved | med steps | trunc | harness err |
|---|---|---|---|---|---|---|---|---|---|
| `gemini-3-5-flash-lite` | 10 | 100 | 14/100 (14%) | $2.811 | $0.0281 | $0.201 | 10.0 | 90 | 0 |
| `gpt-5-nano` | 10 | 100 | 13/100 (13%) | $0.425 | $0.0042 | $0.033 | 10.0 | 72 | 0 |
| `haiku-4-5` | 10 | 100 | 8/100 (8%) | $6.250 | $0.0625 | $0.781 | 10.0 | 97 | 0 |

`$/solved` is blank when nothing was solved — a zero there would read as "free" when it actually means the denominator is empty.

## Patch size (solved tasks only)

- `gemini-3-5-flash-lite`: median `loc_ratio` 1.00 (1.00 = same size as django's own fix)
- `gpt-5-nano`: median `loc_ratio` 1.00 (1.00 = same size as django's own fix)
- `haiku-4-5`: median `loc_ratio` 0.96 (1.00 = same size as django's own fix)

## Why runs ended

Termination is how the loop stopped; outcome is what grading found. `no_credit` is scored as a failure but is not a model property.

**`gemini-3-5-flash-lite`** — terminations: declared_done=10, truncated=90; outcomes: no_patch=72, regression=1, resolved=14, tests_failed=13
**`gpt-5-nano`** — terminations: declared_done=25, max_tokens=3, truncated=72; outcomes: harness_error=5, no_patch=59, resolved=13, tests_failed=23
**`haiku-4-5`** — terminations: declared_done=2, max_tokens=1, truncated=97; outcomes: no_patch=86, resolved=8, tests_failed=6

## Head-to-head (discordant pairs)

The meaningful comparison is tasks where two models *disagree*, not the difference of two rates: both ran the identical set, so paired counts are what carry signal.

| pair | shared | both | neither | discordant |
|---|---|---|---|---|
| gemini-3-5-flash-lite vs gpt-5-nano | 100 | 9 | 82 | 9 |
| gemini-3-5-flash-lite vs haiku-4-5 | 100 | 4 | 82 | 14 |
| gpt-5-nano vs haiku-4-5 | 100 | 5 | 84 | 11 |

## Resolve rate by task property

Every dimension here is a tag recorded at mining time, so filtering happens at analysis rather than being baked into the task set.

### ticket_type

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| bug | 61 | 9/61 (15%) | 10/61 (16%) | 6/61 (10%) |
| cleanup | 25 | 5/25 (20%) | 3/25 (12%) | 1/25 (4%) |
| feature | 14 | 0/14 (0%) | 0/14 (0%) | 1/14 (7%) |

### has_reproduction

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| yes | 64 | 11/64 (17%) | 11/64 (17%) | 5/64 (8%) |
| no | 36 | 3/36 (8%) | 2/36 (6%) | 3/36 (8%) |

### loc_changed

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| 1-5 | 36 | 12/36 (33%) | 8/36 (22%) | 6/36 (17%) |
| 6-15 | 31 | 2/31 (6%) | 4/31 (13%) | 1/31 (3%) |
| 30+ | 18 | 0/18 (0%) | 1/18 (6%) | 1/18 (6%) |
| 16-29 | 15 | 0/15 (0%) | 0/15 (0%) | 0/15 (0%) |

### edit_sites

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| 1 site | 39 | 11/39 (28%) | 8/39 (21%) | 6/39 (15%) |
| 3+ sites | 33 | 2/33 (6%) | 2/33 (6%) | 0/33 (0%) |
| 2 sites | 28 | 1/28 (4%) | 3/28 (11%) | 2/28 (7%) |

### statement_len

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| 600-1500ch | 50 | 5/50 (10%) | 3/50 (6%) | 3/50 (6%) |
| 1500ch+ | 40 | 7/40 (18%) | 9/40 (22%) | 4/40 (10%) |
| <600ch | 10 | 2/10 (20%) | 1/10 (10%) | 1/10 (10%) |

### statement_edited

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| no | 84 | 13/84 (15%) | 13/84 (15%) | 7/84 (8%) |
| yes | 16 | 1/16 (6%) | 0/16 (0%) | 1/16 (6%) |

### area

| bucket | tasks | `gemini-3-5-flash-lite` | `gpt-5-nano` | `haiku-4-5` |
|---|---|---|---|---|
| django/contrib/admin | 14 | 2/14 (14%) | 3/14 (21%) | 1/14 (7%) |
| django/db/models | 14 | 0/14 (0%) | 0/14 (0%) | 0/14 (0%) |
| django/contrib/auth | 8 | 0/8 (0%) | 1/8 (12%) | 0/8 (0%) |
| django/utils | 7 | 1/7 (14%) | 1/7 (14%) | 0/7 (0%) |
| django/http | 7 | 1/7 (14%) | 1/7 (14%) | 1/7 (14%) |
| django/forms | 6 | 2/6 (33%) | 0/6 (0%) | 0/6 (0%) |
| django/test | 6 | 1/6 (17%) | 0/6 (0%) | 1/6 (17%) |
| django/core/cache | 4 | 2/4 (50%) | 1/4 (25%) | 0/4 (0%) |

