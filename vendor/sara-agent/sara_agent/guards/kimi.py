"""
KimiGuard — a PromptedGuard backend calling Moonshot's kimi-k2.6 over its
OpenAI-compatible chat-completions endpoint (matches the monorepo's own
provider preset, src/agent/config.py). Stdlib only (urllib) — no new
third-party dependency, consistent with sara-agent's CORE promise.

Not imported by sara_agent.guards's __init__ — a caller opts in explicitly
(`import sara_agent.guards.kimi`) so CORE stays network-free by default.
Missing MOONSHOT_API_KEY raises a clear error at classify() time, never a
silent fallback to another backend.
"""

from __future__ import annotations


from sara_agent.guards.openai_compat import openai_chat_call_fn
from sara_agent.guards.prompted import ModelCallFn, PromptedGuard
from sara_agent.guards.registry import register

MOONSHOT_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"


def _kimi_call_fn(model: str, endpoint: str, api_key_env: str, max_tokens: int,
                  timeout_s: int = 180) -> ModelCallFn:
    """Kept as a thin wrapper over the shared client.

    The body used to live here and was already generic over
    (model, endpoint, api_key_env, max_tokens) — it just carried one
    provider's name and a hardcoded 60s timeout. That timeout is what made a
    policy-driven sweep fail: kimi-k2.6 spends tokens on invisible
    reasoning_content before any visible content, so a longer policy prompt
    plus a raised max_tokens runs past 60s and every call dies with
    TimeoutError.

    temperature=1 because kimi-k2.6 rejects temperature=0 ("only 1 is allowed
    for this model") — so unlike the other GuardModel backends, this one is
    NOT perfectly deterministic run-to-run.
    """
    return openai_chat_call_fn(
        model=model, endpoint=endpoint, api_key_env=api_key_env,
        max_tokens=max_tokens, temperature=1, timeout_s=timeout_s,
        backend_label="KimiGuard",
    )


class KimiGuard(PromptedGuard):
    def __init__(self, model: str = "kimi-k2.6", endpoint: str = MOONSHOT_ENDPOINT,
                 api_key_env: str = "MOONSHOT_API_KEY", max_tokens: int = 1500,
                 timeout_s: int = 180):
        # kimi-k2.6 spends tokens on invisible reasoning_content before any
        # visible content — a low cap starves the answer (finish_reason
        # "length" with content=""). 1500 leaves headroom; still ~$0.006/call
        # worst case at $4/M output tokens.
        super().__init__(_kimi_call_fn(model, endpoint, api_key_env, max_tokens, timeout_s),
                          backend_name=f"kimi:{model}")


register("kimi-k2.6", lambda **cfg: KimiGuard(**cfg))
