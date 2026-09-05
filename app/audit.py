"""Append-only audit trail.

Called by: app/main.py (POST /disputes/{id}/decide and /respond call
record_audit(); GET /audit/{id} calls get_audit()), tests/test_smoke.py
(replay() determinism test).

Appends one JSON line per decision to audit_log.jsonl at the project
root (gitignored -- generated at runtime, not a schema deliverable).
Each line captures enough to reproduce and re-check a past decision:
audit_id, timestamp, dispute_id, the exact input record snapshot, the
rule_applied string, decision, win_probability, evidence_coverage.

DEPLOYMENT NOTE (Vercel / any read-only-filesystem serverless host):
Vercel's function filesystem is read-only except /tmp, and /tmp is not
guaranteed to persist across invocations or across scaled-out instances
-- it's a best-effort warm-instance cache, not durable storage. When the
VERCEL env var is set (Vercel sets this automatically at build/run time),
the log is written to /tmp instead of the project root. Audit replay
still works within a single warm invocation (which is what one browser
session driving the demo will normally hit), but is NOT a durable audit
trail once deployed serverless -- running the app locally (`uvicorn
app.main:app`) is what actually demonstrates persistent, cross-restart
replay. This tradeoff is documented in README.md.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

if os.environ.get("VERCEL"):
    AUDIT_LOG_PATH = Path("/tmp/audit_log.jsonl")
else:
    AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent / "audit_log.jsonl"


def record_audit(record: dict, decision: dict) -> str:
    """Appends an audit line and returns the new audit_id."""
    audit_id = uuid.uuid4().hex
    entry = {
        "audit_id": audit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dispute_id": record["dispute_id"],
        "inputs": record,
        "rule_applied": decision["rule_applied"],
        "decision": decision["decision"],
        "win_probability": decision["win_probability"],
        "evidence_coverage": decision["evidence_coverage"],
        "expected_value_inr": decision["expected_value_inr"],
    }
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return audit_id


def get_audit(audit_id: str):
    """Returns the matching audit entry dict, or None if not found or the
    log file doesn't exist yet.
    """
    if not AUDIT_LOG_PATH.exists():
        return None
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("audit_id") == audit_id:
                return entry
    return None


def replay(audit_id: str) -> dict:
    """Re-runs decide() on the stored inputs for `audit_id` and asserts the
    result matches the stored decision. Returns the freshly computed
    decision dict. Raises if no such audit entry exists, or if replay
    disagrees with the recorded decision (non-determinism / drift).
    """
    # Imported lazily to avoid a circular import (decision -> scoring is
    # fine, but audit is imported by main.py alongside decision).
    from app.decision import decide
    from app.scoring import get_model

    entry = get_audit(audit_id)
    if entry is None:
        raise ValueError(f"No audit entry found for audit_id={audit_id!r}")

    model, feature_columns = get_model()
    result = decide(entry["inputs"], model, feature_columns)

    assert result["decision"] == entry["decision"], (
        f"Replay mismatch for {audit_id}: stored decision "
        f"{entry['decision']!r} != replayed {result['decision']!r}"
    )
    return result
