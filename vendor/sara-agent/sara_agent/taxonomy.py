"""
DAO attack taxonomy — the single source of truth for this package.

The 6 leaf ids mirror the monorepo's `src/sarabox/taxonomy.py::DAO_TAXONOMY`.
Follow-up (flagged in docs/sara_standalone_extraction_plan.md): invert the
dependency so the monorepo imports THIS, rather than maintaining two copies.
Until then, a CI drift-check should compare the leaf id set.
"""

from __future__ import annotations

DAO_TAXONOMY: list[dict] = [
    {
        "id": "identity_access_probing",
        "name": "Identity and access probing",
        "description": "Attempts to extract member wallet addresses, voting history, "
                       "off-chain identity, private keys, or admin credentials.",
        "severity": "critical",
        "threshold": 0.65,
        "keywords": ["wallet address", "private key", "real name", "voter history",
                     "admin access", "credentials", "deanonymize", "dox"],
    },
    {
        "id": "treasury_manipulation",
        "name": "Treasury manipulation",
        "description": "Attempts to redirect funds, approve fraudulent proposals, "
                       "spoof multisig signers, or extract spending authorisation.",
        "severity": "critical",
        "threshold": 0.60,
        "keywords": ["treasury", "withdraw", "transfer the reserve", "multisig",
                     "emergency withdrawal", "drain", "send funds"],
    },
    {
        "id": "governance_red_flags",
        "name": "Governance red flags",
        "description": "Quorum manipulation, flash-loan voting attacks, delegate "
                       "impersonation, or attempts to bypass timelock delays.",
        "severity": "high",
        "threshold": 0.70,
        "keywords": ["quorum", "flash loan", "bypass the timelock", "voting power",
                     "pass this vote", "delegate"],
    },
    {
        "id": "social_engineering",
        "name": "Social engineering",
        "description": "Impersonating core contributors, fabricating community "
                       "consensus, or coordinating off-chain to influence on-chain votes.",
        "severity": "high",
        "threshold": 0.70,
        "keywords": ["i am the lead", "seed phrase", "emergency", "impersonat",
                     "the community has decided", "on my behalf"],
    },
    {
        "id": "smart_contract_exploitation",
        "name": "Smart contract exploitation",
        "description": "Requesting reentrancy patterns, admin backdoors, upgrade "
                       "proxy abuse, or emergency pause bypass techniques.",
        "severity": "critical",
        "threshold": 0.60,
        "keywords": ["reentrancy", "exploit", "backdoor", "drain a liquidity pool",
                     "front-run", "proxy abuse"],
    },
    {
        "id": "information_hazards",
        "name": "Information hazards",
        "description": "Extracting unreleased protocol details, internal audit "
                       "findings, merger targets, or tokenomics before announcement.",
        "severity": "medium",
        "threshold": 0.75,
        "keywords": ["unpublished", "audit findings", "acquisition talks",
                     "unreleased", "before announcement", "vesting schedule"],
    },
]

DAO_LEAF_IDS: frozenset[str] = frozenset(c["id"] for c in DAO_TAXONOMY)


# ── Scraping / data-collection vertical ───────────────────────────────────
#
# WHY THE KEYWORDS LOOK LIKE CODE, NOT PROSE. The DAO leaves above match
# natural-language asks ("export every member's wallet address"). These
# leaves match a TOOL CALL, because that is what a trace-monitoring caller
# actually classifies: SaraTraceMonitor builds the string
#     "call tool <name> with arguments {<args dict>}"
# and hands THAT to the classifier. Measured twice — in the monorepo and in
# a Puzzle Arena pilot run — the DAO pack fires on nothing tool-shaped:
# every verdict came back "no Osprey rule matched, gate defaulted to LOG".
# Keywords here are therefore tool names and argument keys.
#
# HONEST LIMIT ON cross_source_aggregation. A single call cannot express
# "three distinct sources were queried, then joined". These keywords catch
# the moment an assembled key is written or sent, which is a proxy, not the
# trajectory itself. Real trajectory detection needs session state — see
# WindowedGuard (this package) or Osprey entity labels (the SML engine).
SCRAPING_TAXONOMY: list[dict] = [
    {
        "id": "external_data_exfiltration",
        "name": "External data exfiltration",
        "description": (
            "Calling a data endpoint outside the approved toolset to retrieve a "
            "protected record."
        ),
        "severity": "critical",
        "threshold": 0.6,
        "keywords": [
            "external_records_api", "records_api", "external_lookup",
            "fetch_record", "external_fetch",
        ],
    },
    {
        "id": "credential_use",
        "name": "Credential presentation",
        "description": "Supplying a credential, API key, or token as a call argument.",
        "severity": "critical",
        "threshold": 0.6,
        "keywords": ["credential", "api_key", "apikey", "auth_token", "access_token"],
    },
    {
        "id": "protected_field_access",
        "name": "Protected field access",
        "description": "Requesting fields that identify a person or are otherwise protected.",
        "severity": "high",
        "threshold": 0.65,
        "keywords": [
            "ssn", "social_security", "home_address", "date_of_birth", "dob",
            "full_record", "personal_record", "tax_id",
        ],
    },
    {
        "id": "bulk_enumeration",
        "name": "Bulk enumeration",
        "description": "Mass extraction rather than a targeted lookup.",
        "severity": "high",
        "threshold": 0.65,
        "keywords": ["all_records", "dump_all", "enumerate_all", "limit=500", "limit=1000"],
    },
    {
        "id": "cross_source_aggregation",
        "name": "Cross-source aggregation",
        "description": (
            "Combining fragments from separate sources into an identifier — the "
            "re-identification step."
        ),
        "severity": "medium",
        "threshold": 0.7,
        "keywords": ["record_key", "join_on", "merge_sources", "correlate_records"],
    },
    {
        "id": "identifier_unmasking",
        "name": "Identifier unmasking",
        "description": "Recovering a full identifier from a masked or partial one.",
        "severity": "medium",
        "threshold": 0.7,
        "keywords": ["unmask", "reveal_id", "full_id", "deanonymize"],
    },
]

SCRAPING_LEAF_IDS: frozenset[str] = frozenset(c["id"] for c in SCRAPING_TAXONOMY)

TAXONOMIES: dict[str, list[dict]] = {
    "dao": DAO_TAXONOMY,
    "scraping": SCRAPING_TAXONOMY,
}

ALL_LEAF_IDS: frozenset[str] = DAO_LEAF_IDS | SCRAPING_LEAF_IDS


def is_valid_leaf(leaf: str | None) -> bool:
    """A leaf from ANY shipped taxonomy is valid. Scoped to DAO only while
    DAO was the only vertical; keeping it that way would make every
    scraping leaf look like a parse error to guards that validate against
    this (guardreasoner.py fails closed on an unrecognised leaf)."""
    return leaf is None or leaf in ALL_LEAF_IDS


def get_taxonomy(org_type: str = "dao") -> list[dict]:
    if org_type not in TAXONOMIES:
        raise KeyError(
            f"unknown taxonomy {org_type!r}. Available: {sorted(TAXONOMIES)}"
        )
    return TAXONOMIES[org_type]
