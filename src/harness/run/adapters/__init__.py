"""Provider adapters.

Adapters translate wire formats and nothing else. Everything that could bias a
comparison -- the prompt, the tool schemas, the step cap, the read bound -- lives in
loop.py, so the only variable across runs is the model.

The loop keeps a **provider-neutral history** and each adapter renders it into its
own shape on every call. Adapters are therefore stateless: re-rendering from scratch
each turn is slightly wasteful but means a retry or a resume can never desynchronise
adapter state from what the loop believes happened.

Neutral history entries:

    {"role": "user",         "text": str}
    {"role": "assistant",    "raw": Any, "text": str,
                             "tool_calls": [{"id","name","input"}]}
    {"role": "tool_results", "results": [{"id","name","content","is_error"}]}

`raw` carries the provider's own representation of the assistant turn so it can be
echoed back verbatim. That matters: Anthropic content blocks must be returned
unmodified or the turn is rejected, and reconstructing them by hand breaks
signatures on thinking models.

Neutral tool schema is what `run.tools.tool_schemas()` returns -- `name`,
`description`, `input_schema` (JSON Schema). Each adapter maps that to its provider's
spelling.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Reply:
    """One assistant turn, provider-neutral."""

    raw: object = None                 # provider-native assistant content, echoed back
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # {id, name, input}
    stop_reason: str = ""              # normalised: end_turn|tool_use|max_tokens|refusal|context_exceeded
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def build(model_cfg: dict, api_key: str | None = None):
    """Return the adapter for a model config's `provider`."""
    provider = model_cfg["provider"]
    if provider == "anthropic":
        from .anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(model_cfg, api_key=api_key)
    if provider == "openai":
        from .openai_adapter import OpenAIAdapter

        return OpenAIAdapter(model_cfg, api_key=api_key)
    if provider == "google":
        from .gemini_adapter import GeminiAdapter

        return GeminiAdapter(model_cfg, api_key=api_key)
    raise ValueError(f"no adapter for provider {provider!r}")
