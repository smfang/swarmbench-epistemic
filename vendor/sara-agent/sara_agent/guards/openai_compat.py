"""One HTTP client for every OpenAI-compatible chat-completions endpoint.

Extracted from kimi.py's `_kimi_call_fn`, which was already generic over
(model, endpoint, api_key_env, max_tokens) but private to that module and
named after one provider. Anything speaking the OpenAI chat-completions
shape — Moonshot, a vLLM server, a Modal deployment, an Ollama bridge —
differs only in those four values, so copying the body per provider would be
four chances for the error handling to drift apart.

Stdlib only (urllib), consistent with sara-agent's CORE promise.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from sara_agent.guards.prompted import ModelCallFn

DEFAULT_TIMEOUT_S = 60


def openai_chat_call_fn(
    model: str,
    endpoint: str,
    api_key_env: str | None = None,
    max_tokens: int = 1500,
    *,
    temperature: float = 0.0,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    backend_label: str = "openai-compatible",
) -> ModelCallFn:
    """A (system_prompt, user_prompt) -> raw text caller.

    `api_key_env=None` is for endpoints that need no auth — a vLLM server on a
    private network, or a local Ollama. A *named* env var that is unset is a
    different situation and raises: the caller asked for authentication, so
    proceeding without it would silently hit an endpoint unauthenticated.

    `temperature=0.0` by default because determinism is what makes an eval
    harness reproducible. Providers that reject it (kimi-k2.6 allows only 1)
    pass their own value and document why.
    """

    def _call(system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if api_key_env:
            api_key = os.environ.get(api_key_env)
            if not api_key:
                raise RuntimeError(
                    f"{backend_label}: {api_key_env} is not set. Export it or "
                    f"select a different guard backend — never a silent fallback."
                )
            headers["Authorization"] = f"Bearer {api_key}"

        body = json.dumps({
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode()

        req = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                payload = json.loads(resp.read())
        except urllib.error.URLError as exc:
            # Named explicitly: a cold-starting serverless GPU (Modal et al.)
            # looks exactly like an outage until it finishes loading weights,
            # and "request failed" alone sends people debugging the wrong thing.
            raise RuntimeError(
                f"{backend_label}: request to {endpoint} failed: {exc}. "
                f"If this is a scale-to-zero deployment the first call may "
                f"exceed timeout_s={timeout_s} while the model loads."
            ) from exc

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"{backend_label}: response from {endpoint} was not in "
                f"OpenAI chat-completions shape: {str(payload)[:200]!r}"
            ) from exc

    return _call
