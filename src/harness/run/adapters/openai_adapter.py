"""OpenAI adapter: neutral history -> Chat Completions.

Chat Completions rather than the Responses API on purpose: it is the shape every
OpenAI-compatible host speaks (Groq, Together, OpenRouter, Cerebras, vLLM), so this
one adapter also covers open-weight models behind a `base_url`.
"""

from __future__ import annotations

import json

from . import Reply

STOP_MAP = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "length": "max_tokens",
    "content_filter": "refusal",
}


class OpenAIAdapter:
    provider = "openai"

    def __init__(self, model_cfg: dict, api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI

        self.cfg = model_cfg
        self.model_id = model_cfg["model_id"]
        self.max_output = int(model_cfg.get("max_output_tokens", 8192))
        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        # base_url lets the same adapter drive an OpenAI-compatible host.
        url = base_url or model_cfg.get("base_url")
        if url:
            kwargs["base_url"] = url
        self.client = OpenAI(**kwargs)

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    @staticmethod
    def _messages(system: str, history: list[dict]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for turn in history:
            if turn["role"] == "user":
                out.append({"role": "user", "content": turn["text"]})
            elif turn["role"] == "assistant":
                # `raw` holds the SDK's own tool_calls list, echoed back unchanged.
                msg: dict = {"role": "assistant", "content": turn.get("text") or None}
                if turn.get("raw"):
                    msg["tool_calls"] = turn["raw"]
                out.append(msg)
            else:
                # One `tool` message per result, keyed by tool_call_id. OpenAI has no
                # is_error flag, so the marker goes inline -- otherwise a failed call
                # is indistinguishable from a successful one that returned an
                # error-looking string.
                for r in turn["results"]:
                    body = r["content"]
                    if r.get("is_error"):
                        body = f"[tool error] {body}"
                    out.append({"role": "tool", "tool_call_id": r["id"], "content": body})
        return out

    def send(self, system: str, history: list[dict], tools: list[dict]) -> Reply:
        resp = self.client.chat.completions.create(
            model=self.model_id,
            # GPT-5 models reject `max_tokens`; the parameter was renamed.
            max_completion_tokens=self.max_output,
            messages=self._messages(system, history),
            tools=self._tools(tools),
        )
        choice = resp.choices[0]
        msg = choice.message
        calls = []
        for tc in msg.tool_calls or []:
            # Arguments arrive as a JSON *string*, unlike Anthropic's parsed dict. A
            # model can emit malformed JSON here, so a parse failure is reported as a
            # tool call with no arguments rather than crashing the run -- the loop
            # then surfaces it as a tool error the model can recover from.
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__malformed_arguments__": tc.function.arguments}
            calls.append({"id": tc.id, "name": tc.function.name, "input": args})

        u = resp.usage
        cached = 0
        if u is not None:
            details = getattr(u, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", 0) or 0
        prompt_tokens = (u.prompt_tokens if u else 0) or 0
        return Reply(
            raw=[tc.model_dump(exclude_none=True) for tc in (msg.tool_calls or [])] or None,
            text=msg.content or "",
            tool_calls=calls,
            stop_reason=STOP_MAP.get(choice.finish_reason or "", choice.finish_reason or ""),
            # OpenAI reports cached tokens INSIDE prompt_tokens, unlike Anthropic which
            # reports them separately. Subtracting keeps the cost calculation from
            # charging the same tokens twice.
            input_tokens=max(0, prompt_tokens - cached),
            output_tokens=(u.completion_tokens if u else 0) or 0,
            cache_read_tokens=cached,
            cache_write_tokens=0,  # no separate write charge on OpenAI
        )
