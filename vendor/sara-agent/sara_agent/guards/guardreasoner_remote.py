"""GuardReasoner over HTTP — for a Modal / vLLM / any OpenAI-compatible host.

`VLLMGuardReasoner` (guardreasoner.py) calls `vllm.LLM(model=...)`, which
loads weights IN-PROCESS and needs a local GPU. It is not an HTTP client, so
registering `guardreasoner-8b` and pointing it at a remote endpoint cannot
work — there is nowhere to put the URL, and the import fails without `vllm`
installed.

This is the other seam: the same instruction template and the same parser,
reached over `openai_chat_call_fn`. A GuardReasoner served by vLLM's
OpenAI-compatible server (which is what Modal's vLLM recipe exposes) is then
a config value, not a code change.

Reused unchanged, deliberately:
  INSTRUCTION_TEMPLATE        guardreasoner.py — same prompt the local backend sends
  parse_guardreasoner_output  guardreasoner.py — already a free function

Not imported by sara_agent.guards's __init__ — a caller opts in explicitly,
so CORE stays network-free by default.
"""

from __future__ import annotations

from sara_agent.guards.base import GuardVerdict
from sara_agent.guards.guardreasoner import (
    DEFAULT_MODEL,
    INSTRUCTION_TEMPLATE,
    parse_guardreasoner_output,
)
from sara_agent.guards.openai_compat import openai_chat_call_fn
from sara_agent.guards.registry import register

#: A scale-to-zero GPU deployment pays cold-start on the first call while
#: weights load. That is fine for batch eval and fatal for per-message
#: moderation; the default is generous because a timeout here is
#: indistinguishable from an outage and sends people debugging the wrong thing.
DEFAULT_TIMEOUT_S = 300


class RemoteGuardReasoner:
    """GuardReasoner hosted behind an OpenAI-compatible endpoint.

    `endpoint` is the full chat-completions URL, e.g.
    `https://<workspace>--guardreasoner.modal.run/v1/chat/completions`.

    `api_key_env=None` suits a private endpoint with no auth. Naming an env
    var that is then unset raises rather than calling unauthenticated.
    """

    # Defaulted to "" rather than required-positional so a caller who omits it
    # gets the explanation below instead of a bare TypeError from the registry
    # factory, which says nothing about what an endpoint is or why there is no
    # default for it.
    def __init__(self, endpoint: str = "", model: str = DEFAULT_MODEL,
                 api_key_env: str | None = None, max_tokens: int = 512,
                 timeout_s: int = DEFAULT_TIMEOUT_S):
        if not endpoint:
            raise ValueError(
                "RemoteGuardReasoner needs an endpoint — e.g. "
                "get_guard('guardreasoner-remote', endpoint='https://.../v1/chat/completions'). "
                "There is no default: a wrong guess would classify against "
                "whatever happened to answer."
            )
        self._model = model
        self._endpoint = endpoint
        self._call = openai_chat_call_fn(
            model=model, endpoint=endpoint, api_key_env=api_key_env,
            max_tokens=max_tokens, temperature=0.0, timeout_s=timeout_s,
            backend_label=f"guardreasoner-remote:{model}",
        )

    @property
    def backend_name(self) -> str:
        return f"guardreasoner-remote:{self._model}"

    def classify(self, prompt: str, response: str | None = None) -> GuardVerdict:
        # The local backend applies the model's chat template via
        # AutoTokenizer; an OpenAI-compatible server does that itself from the
        # messages array, so the instruction goes in as the user turn and the
        # system turn stays empty rather than inventing one GuardReasoner was
        # not fine-tuned on.
        instruction = INSTRUCTION_TEMPLATE.format(prompt=prompt)
        raw = self._call("", instruction)
        return parse_guardreasoner_output(raw, backend=self.backend_name)


register("guardreasoner-remote", lambda **cfg: RemoteGuardReasoner(**cfg))
