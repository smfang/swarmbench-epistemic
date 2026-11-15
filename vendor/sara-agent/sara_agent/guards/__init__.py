"""Guard registry + backends. Importing this self-registers the builtin backend."""
from sara_agent.guards import builtin  # noqa: F401  (self-registers "builtin")
from sara_agent.guards import windowed  # noqa: F401  (self-registers "windowed")
from sara_agent.guards.base import AgentAction, GuardModel, GuardVerdict
from sara_agent.guards.registry import get_guard, list_guards, register
from sara_agent.guards.windowed import WindowedGuard

__all__ = ["AgentAction", "GuardModel", "GuardVerdict", "WindowedGuard",
           "get_guard", "list_guards", "register"]
