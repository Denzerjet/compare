"""Anthropic adapter: neutral history -> Messages API."""

from __future__ import annotations

from typing import Any

from . import Reply

# Normalise provider stop reasons onto the loop's vocabulary.
STOP_MAP = {
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
    "model_context_window_exceeded": "context_exceeded",
    "stop_sequence": "end_turn",
    "pause_turn": "tool_use",
}


class AnthropicAdapter:
    provider = "anthropic"

    def __init__(self, model_cfg: dict, api_key: str | None = None):
        import anthropic

        self.cfg = model_cfg
        self.model_id = model_cfg["model_id"]
        self.max_output = int(model_cfg.get("max_output_tokens", 8192))
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def _tools(self, tools: list[dict]) -> list[dict]:
        return tools  # the neutral schema already matches Anthropic's shape

    def _messages(self, history: list[dict]) -> list[dict]:
        out: list[dict] = []
        for turn in history:
            if turn["role"] == "user":
                out.append({"role": "user", "content": [{"type": "text", "text": turn["text"]}]})
            elif turn["role"] == "assistant":
                # Echoed verbatim: editing or rebuilding content blocks makes the API
                # reject the turn, and breaks signatures on thinking models.
                out.append({"role": "assistant", "content": turn["raw"]})
            else:
                out.append({"role": "user", "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": r["id"],
                        "content": r["content"],
                        **({"is_error": True} if r.get("is_error") else {}),
                    }
                    for r in turn["results"]
                ]})
        self._mark_cache(out)
        return out

    @staticmethod
    def _mark_cache(messages: list[dict]) -> None:
        """One rolling breakpoint on the newest user content block.

        With the system-block breakpoint that is 2 of the 4 allowed. One rolling
        marker is enough for sequential steps: each step appends ~2 blocks, so the
        previous request's breakpoint stays well inside the 20-block lookback window.
        It would NOT suffice for a turn appending 20+ blocks at once, which is why
        parallel tool use is left off.
        """
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict):
                        block.pop("cache_control", None)
        for msg in reversed(messages):
            if msg["role"] == "user" and isinstance(msg.get("content"), list) and msg["content"]:
                last = msg["content"][-1]
                if isinstance(last, dict):
                    last["cache_control"] = {"type": "ephemeral"}
                return

    def send(self, system: str, history: list[dict], tools: list[dict]) -> Reply:
        resp = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.max_output,
            # cache_control here is what makes the stable prefix -- frozen prompt plus
            # deterministic tool list -- bill at cache-read rates from step 2 onward.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=self._tools(tools),
            messages=self._messages(history),
        )
        u = resp.usage
        return Reply(
            raw=[self._to_dict(b) for b in resp.content],
            text="".join(b.text for b in resp.content if b.type == "text"),
            tool_calls=[
                {"id": b.id, "name": b.name, "input": b.input}
                for b in resp.content if b.type == "tool_use"
            ],
            stop_reason=STOP_MAP.get(resp.stop_reason or "", resp.stop_reason or ""),
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )

    @staticmethod
    def _to_dict(block: Any) -> dict:
        if hasattr(block, "model_dump"):
            return block.model_dump(exclude_none=True)
        return dict(block)
