"""
The Sheila seam — optional, injected, null by default.

Sara-in-a-Box never invokes a judge on the core classify/gate path (verified in
the monorepo: no PurpleTeam call sites in src/sarabox or src/osprey_ui). This
module makes the seam explicit so Sheila can be ATTACHED later without the
standalone ever importing it.

- NullPurpleTeam: the default — .judge() is a benign no-op, .run_session() a no-op.
- A2AClient: implements PurpleTeam by calling a remote Sheila over A2A IFF
  SHEILA_A2A_URL is set. Requires the [a2a] extra; unavailable in CORE.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class PurpleTeam(Protocol):
    def judge(self, prompt: str, response: str | None = None) -> dict: ...
    def run_session(self, *args, **kwargs) -> dict: ...


class NullPurpleTeam:
    """Default judge: no Sheila, no network. Benign no-ops."""

    def judge(self, prompt: str, response: str | None = None) -> dict:
        return {"decision": "clean", "category": None, "confidence": 0.0,
                "source": "null-judge"}

    def run_session(self, *args, **kwargs) -> dict:
        return {"status": "noop", "source": "null-judge"}


def default_purpleteam() -> PurpleTeam:
    """NullPurpleTeam unless SHEILA_A2A_URL is set AND the [a2a] extra is available."""
    url = os.getenv("SHEILA_A2A_URL")
    if not url:
        return NullPurpleTeam()
    try:
        from sara_agent.a2a_client import A2AClient  # optional [a2a] extra
    except ImportError:
        raise RuntimeError(
            "SHEILA_A2A_URL is set but the [a2a] extra is not installed. "
            "Install `sara-agent[a2a]` to attach a remote Sheila, or unset the var "
            "to use the null judge."
        )
    return A2AClient(url)
