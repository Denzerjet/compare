"""Google Gemini adapter: neutral history -> generate_content.

The shape differs more from the other two than they do from each other: turns are
`contents` with `parts`, the assistant role is called `model`, tool results are
`function_response` parts rather than a distinct role, and there are no per-call ids
-- responses are matched to calls **by function name**.
"""

from __future__ import annotations

from . import Reply

STOP_MAP = {
    "STOP": "end_turn",
    "MAX_TOKENS": "max_tokens",
    "SAFETY": "refusal",
    "PROHIBITED_CONTENT": "refusal",
    "BLOCKLIST": "refusal",
    "RECITATION": "refusal",
    "MALFORMED_FUNCTION_CALL": "invalid_tool_call",
}

# JSON Schema keys Gemini's function declarations reject. Ours are simple enough that
# stripping is safe, but silently sending them yields a 400 rather than a warning.
UNSUPPORTED_SCHEMA_KEYS = ("additionalProperties", "$schema", "default", "examples")


def _clean_schema(schema: dict) -> dict:
    out = {}
    for k, v in schema.items():
        if k in UNSUPPORTED_SCHEMA_KEYS:
            continue
        if isinstance(v, dict):
            out[k] = _clean_schema(v)
        elif isinstance(v, list):
            out[k] = [_clean_schema(i) if isinstance(i, dict) else i for i in v]
        else:
            out[k] = v
    return out


class GeminiAdapter:
    provider = "google"

    def __init__(self, model_cfg: dict, api_key: str | None = None):
        from google import genai

        self.cfg = model_cfg
        self.model_id = model_cfg["model_id"]
        self.max_output = int(model_cfg.get("max_output_tokens", 8192))
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        return [{
            "function_declarations": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": _clean_schema(t["input_schema"]),
                }
                for t in tools
            ]
        }]

    @staticmethod
    def _contents(history: list[dict]) -> list[dict]:
        out: list[dict] = []
        for turn in history:
            if turn["role"] == "user":
                out.append({"role": "user", "parts": [{"text": turn["text"]}]})
            elif turn["role"] == "assistant":
                out.append({"role": "model", "parts": turn["raw"]})
            else:
                # No tool_call_id in this API: a function_response is matched to its
                # call by NAME. That is why the loop carries `name` on every result --
                # dropping it would make results unattributable when a model issues
                # two calls in one turn.
                out.append({"role": "user", "parts": [
                    {"function_response": {
                        "name": r["name"],
                        "response": {"error" if r.get("is_error") else "result": r["content"]},
                    }}
                    for r in turn["results"]
                ]})
        return out

    def send(self, system: str, history: list[dict], tools: list[dict]) -> Reply:
        resp = self.client.models.generate_content(
            model=self.model_id,
            contents=self._contents(history),
            config={
                "system_instruction": system,
                "max_output_tokens": self.max_output,
                "tools": self._tools(tools),
                # Without this the SDK auto-executes function calls internally, which
                # would run tools outside our loop -- no trajectory, no step counting,
                # no bounds enforcement.
                "automatic_function_calling": {"disable": True},
            },
        )

        parts, calls, texts = [], [], []
        cand = (resp.candidates or [None])[0]
        finish = getattr(cand, "finish_reason", None) if cand else None
        if cand and cand.content and cand.content.parts:
            for i, part in enumerate(cand.content.parts):
                parts.append(part.model_dump(exclude_none=True) if hasattr(part, "model_dump") else part)
                if getattr(part, "text", None):
                    texts.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    # Synthesise an id: Gemini has none, but the loop and trajectory
                    # are keyed by id across all providers.
                    calls.append({
                        "id": f"{fc.name}-{i}",
                        "name": fc.name,
                        "input": dict(fc.args or {}),
                    })

        u = getattr(resp, "usage_metadata", None)
        cached = getattr(u, "cached_content_token_count", 0) or 0 if u else 0
        prompt = getattr(u, "prompt_token_count", 0) or 0 if u else 0
        finish_name = getattr(finish, "name", str(finish) if finish else "")
        return Reply(
            raw=parts,
            text="".join(texts),
            tool_calls=calls,
            stop_reason=STOP_MAP.get(finish_name, finish_name.lower()),
            # Like OpenAI, cached tokens are counted inside prompt_token_count, so
            # they are subtracted to avoid billing them twice.
            input_tokens=max(0, prompt - cached),
            output_tokens=(getattr(u, "candidates_token_count", 0) or 0) if u else 0,
            cache_read_tokens=cached,
            cache_write_tokens=0,
        )
