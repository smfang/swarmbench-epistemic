"""
In-package rule store — stdlib sqlite3 (no ClickHouse, no third-party deps).

Replaces the monorepo's ClickHouse-backed OspreyUIStore. Same method surface the
gate/authoring path needs: save_rule / get_rule / list_rules_for_org. An in-memory
DB (":memory:") is the default so tests and `sara classify` need no files.
"""

from __future__ import annotations

import json
import sqlite3
import threading

from sara_agent.models import PolicyRule


class RuleStore:
    def __init__(self, path: str = ":memory:"):
        # check_same_thread=False + a lock so the CLI/server can share one store.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY,
                org_id  TEXT NOT NULL,
                data    TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at_ms INTEGER NOT NULL
            )
        """)
        self._db.commit()

    def save_rule(self, rule: PolicyRule) -> None:
        """Upsert. On update, bump version (part of the audit trail)."""
        with self._lock:
            existing = self._db.execute(
                "SELECT version FROM rules WHERE rule_id=?", (rule.rule_id,)
            ).fetchone()
            if existing is not None:
                rule.version = int(existing[0]) + 1
            self._db.execute(
                "INSERT OR REPLACE INTO rules (rule_id, org_id, data, version, created_at_ms) "
                "VALUES (?,?,?,?,?)",
                (rule.rule_id, rule.org_id, json.dumps(rule.to_dict()),
                 rule.version, rule.created_at_ms),
            )
            self._db.commit()

    def get_rule(self, rule_id: str) -> PolicyRule | None:
        row = self._db.execute(
            "SELECT data FROM rules WHERE rule_id=?", (rule_id,)
        ).fetchone()
        return PolicyRule(**json.loads(row[0])) if row else None

    def list_rules_for_org(self, org_id: str) -> list[PolicyRule]:
        rows = self._db.execute(
            "SELECT data FROM rules WHERE org_id=? ORDER BY created_at_ms", (org_id,)
        ).fetchall()
        return [PolicyRule(**json.loads(r[0])) for r in rows]

    def close(self) -> None:
        self._db.close()
