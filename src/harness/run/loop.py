"""The agent loop. Identical scaffolding for every model.

Everything that could bias a comparison lives here rather than in an adapter: the
frozen system prompt, the tool schemas, the step cap, cache placement, and the
termination taxonomy. The adapters only translate wire formats.

Three things in here are easy to get silently wrong, so each is asserted or
recorded rather than assumed:

  - **Cache placement.** A single trailing breakpoint stops hitting cache once the
    transcript passes the 20-block lookback window, with no error -- just a 10x
    input bill. `cache_read_tokens` is recorded per step and surfaced.
  - **Patch extraction.** `git diff` alone misses files the model *created*, so a
    model that adds a module would silently get no credit. Uses `git add -A` then
    `git diff --cached`.
  - **Incremental persistence.** The trajectory and patch are written as the run
    proceeds. A crash at step 40 must not discard 40 steps of paid work.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from ..env import workspace
from ..schema import Task
from .tools import ToolLimits, Tools, tool_schemas


# Substrings that mean "this key cannot pay for more requests" -- as opposed to a
# rate limit, which is transient. Matched case-insensitively against the exception
# text because none of the three SDKs exposes a single portable code for this.
NO_CREDIT_MARKERS = (
    "insufficient_quota", "exceeded your current quota", "credit balance is too low",
    "billing", "quota exceeded", "resource_exhausted", "check your plan",
)


class Termination(str, Enum):
    """How the loop ended. Distinct from the grade outcome.

    Only HARNESS_ERROR and API_ERROR are excluded from scoring, and not out of
    leniency: harness bugs are not evenly distributed across models, so scoring
    them would let our defects invent a model difference.
    """

    DECLARED_DONE = "declared_done"        # model stopped calling tools
    INVALID_TOOL_CALL = "invalid_tool_call"  # couldn't emit a usable call -> failure
    TRUNCATED = "truncated"                # hit the step cap -> scored as failure
    REFUSED = "refused"                    # model declined -> scored as failure
    CONTEXT_EXCEEDED = "context_exceeded"  # filled its own window -> failure
    MAX_TOKENS = "max_tokens"              # single response hit the output cap
    NO_CREDIT = "no_credit"                # quota/billing exhausted -> scored as failure
    HARNESS_ERROR = "harness_error"        # our bug -> not scored
    API_ERROR = "api_error"                # transport/provider -> not scored


@dataclass
class RunResult:
    task_id: str
    model: str
    termination: Termination
    steps: int = 0
    patch: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    wall_clock_sec: float = 0.0
    tool_calls: dict = field(default_factory=dict)
    detail: str = ""

    @property
    def scorable(self) -> bool:
        """NO_CREDIT counts as a failure, deliberately.

        A paired comparison needs a verdict for every model on every task, so leaving
        credit-exhausted tasks unscored would silently shrink the shared task set. It
        is marked distinctly rather than merged into the model's real failures: every
        such task fails identically for a reason that has nothing to do with the
        model, so the count must be readable next to the resolve rate.
        """
        return self.termination not in (Termination.HARNESS_ERROR, Termination.API_ERROR)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["termination"] = self.termination.value
        d["scorable"] = self.scorable
        d.pop("patch")  # stored separately as model.patch; would bloat the json
        return d


def cost_of(model_cfg: dict, r: RunResult) -> float:
    """Dollar cost from recorded token counts.

    Cache reads and writes are priced separately -- at ~0.1x and ~1.25x input --
    so folding them into `input_tokens` would overstate spend several-fold.
    """
    m = 1_000_000
    return (
        r.input_tokens * model_cfg["price_input_per_mtok"] / m
        + r.output_tokens * model_cfg["price_output_per_mtok"] / m
        + r.cache_read_tokens * model_cfg["price_cache_read_per_mtok"] / m
        + r.cache_write_tokens * model_cfg["price_cache_write_per_mtok"] / m
    )


def extract_patch(tree: Path) -> str:
    """The model's changes, including files it created.

    `git add -A` first: a plain `git diff` shows only tracked modifications, so a
    new module would be invisible and the model would get no credit for it.
    """
    subprocess.run(["git", "add", "-A"], cwd=tree, check=True, capture_output=True)
    return subprocess.run(
        ["git", "diff", "--cached"], cwd=tree, check=True, capture_output=True, text=True
    ).stdout


def run_task(
    task: Task,
    adapter,
    model_cfg: dict,
    *,
    system_prompt: str,
    max_steps: int,
    limits: ToolLimits,
    out_dir: Path,
    repo: Path | None = None,
) -> RunResult:
    """One model, one task. Writes trajectory.jsonl and model.patch as it goes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    traj = out_dir / "trajectory.jsonl"
    traj.write_text("")
    patch_path = out_dir / "model.patch"

    res = RunResult(task_id=task.task_id, model=model_cfg["model_id"],
                    termination=Termination.HARNESS_ERROR)
    tools = tool_schemas()
    started = time.monotonic()

    def log(record: dict) -> None:
        with traj.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

    # The worktree is at base_commit with NO test.patch: the model must not see the
    # tests that will grade it. grade() applies test.patch itself, afterwards.
    with workspace.worktree(task.base_commit, repo=repo) as tree:
        tk = Tools(tree, limits)
        # Provider-neutral history; each adapter renders it into its own wire shape.
        history: list[dict] = [{"role": "user", "text": task.problem_statement}]
        log({"step": 0, "role": "user", "content": task.problem_statement})

        try:
            for step in range(1, max_steps + 1):
                res.steps = step
                reply = adapter.send(system_prompt, history, tools)

                res.input_tokens += reply.input_tokens
                res.output_tokens += reply.output_tokens
                res.cache_read_tokens += reply.cache_read_tokens
                res.cache_write_tokens += reply.cache_write_tokens
                log({
                    "step": step, "role": "assistant", "stop_reason": reply.stop_reason,
                    "text": reply.text,
                    "tool_calls": [{"name": c["name"], "input": c["input"]} for c in reply.tool_calls],
                    "usage": {
                        "input": reply.input_tokens, "output": reply.output_tokens,
                        "cache_read": reply.cache_read_tokens,
                        "cache_write": reply.cache_write_tokens,
                    },
                })

                # Stop reasons are normalised by the adapters onto one vocabulary, so
                # this branch is identical for every provider.
                if reply.stop_reason == "refusal":
                    res.termination = Termination.REFUSED
                    break
                if reply.stop_reason == "context_exceeded":
                    res.termination = Termination.CONTEXT_EXCEEDED
                    break
                if reply.stop_reason == "invalid_tool_call":
                    res.termination = Termination.INVALID_TOOL_CALL
                    break
                if reply.stop_reason == "max_tokens" and not reply.tool_calls:
                    res.termination = Termination.MAX_TOKENS
                    break

                history.append({
                    "role": "assistant", "raw": reply.raw,
                    "text": reply.text, "tool_calls": reply.tool_calls,
                })

                if not reply.tool_calls:
                    res.termination = Termination.DECLARED_DONE
                    break

                results = []
                for call in reply.tool_calls:
                    text, is_error = tk.dispatch(call["name"], call["input"])
                    # `name` is carried as well as `id` because Gemini matches a
                    # function_response to its call by NAME, not by id.
                    results.append({"id": call["id"], "name": call["name"],
                                    "content": text, "is_error": is_error})
                    log({"step": step, "role": "tool_result", "tool": call["name"],
                         "is_error": is_error, "content": text[:2000]})
                history.append({"role": "tool_results", "results": results})

                # Persist every step: a crash must not discard paid work.
                patch_path.write_text(extract_patch(tree))
            else:
                res.termination = Termination.TRUNCATED
        except Exception as exc:  # noqa: BLE001 - classified below, never swallowed
            name = type(exc).__name__
            blob = f"{name}: {exc}".lower()
            if any(m in blob for m in NO_CREDIT_MARKERS):
                res.termination = Termination.NO_CREDIT
            elif name.startswith(("APIError", "APIStatus", "APIConnection", "RateLimit",
                                  "Authentication", "BadRequest", "Internal", "Overloaded",
                                  "ClientError", "ServerError", "PermissionDenied")):
                res.termination = Termination.API_ERROR
            else:
                res.termination = Termination.HARNESS_ERROR
            res.detail = f"{name}: {exc}"[:500]
            log({"role": "error", "termination": res.termination.value, "detail": res.detail})

        res.patch = extract_patch(tree)
        patch_path.write_text(res.patch)

    res.wall_clock_sec = time.monotonic() - started
    res.cost_usd = cost_of(model_cfg, res)
    res.tool_calls = {n: tk.calls.count(n) for n in sorted(set(tk.calls))}
    return res
