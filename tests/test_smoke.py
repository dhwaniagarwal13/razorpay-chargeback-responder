"""Smoke tests, kept intentionally light given the timeline.

Covers the three invariants called out in the build brief:
1. determinism -- decide() on the same input+model gives the same result
2. anti-fabrication -- a letter never renders a sentence for a
   False/missing evidence field
3. audit replay -- record_audit() + replay() reproduce the same decision
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.decision import decide
from app.letters import TemplateGenerator
from app.scoring import get_model


def _sample_record():
    return {
        "dispute_id": "D9001",
        "order_id": "O99001",
        "reason_code": "13.1",
        "dispute_amount_inr": 4500,
        "customer_tenure_days": 400,
        "prior_chargeback_count": 0,
        "evidence": {
            "delivery_confirmed": True,
            "tracking_number_present": True,
            "signature_captured": False,
            "shipping_address_matches_billing": True,
            "digital_access_logs_present": False,
        },
        "would_win_if_represented": True,
    }


def test_decide_is_deterministic():
    record = _sample_record()
    model, feature_columns = get_model()

    result1 = decide(record, model, feature_columns)
    result2 = decide(record, model, feature_columns)

    assert result1 == result2


def test_letter_does_not_fabricate_missing_evidence():
    record = _sample_record()
    model, feature_columns = get_model()
    decision = decide(record, model, feature_columns)

    generator = TemplateGenerator()
    letter = generator.generate(record, decision, record["evidence"])

    # signature_captured and digital_access_logs_present are False in
    # this record's evidence -- their backing sentences must not appear,
    # regardless of whether the overall decision was represent or concede.
    assert "signature was captured" not in letter
    assert "access logs confirm" not in letter

    # A field that IS True should have its sentence present only when we
    # actually generated a represent letter (concede memos don't cite
    # per-field sentences at all).
    if decision["decision"] == "represent":
        assert "Delivery of order O99001 is confirmed by the carrier." in letter


def test_letter_never_fabricates_for_any_reason_code_and_missing_fields():
    """Broader anti-fabrication sweep: for every reason code, build a
    record where every evidence field is explicitly False, and assert
    none of that reason code's grounded sentences appear in the letter
    (forcing a concede path is fine -- the memo itself must not contain
    represent-style evidence sentences).
    """
    from app.reason_codes import REASON_CODES
    from app.letters import LETTER_SENTENCES

    model, feature_columns = get_model()
    generator = TemplateGenerator()

    for reason_code, rc in REASON_CODES.items():
        record = {
            "dispute_id": "D9999",
            "order_id": "O99999",
            "reason_code": reason_code,
            "dispute_amount_inr": 2000,
            "customer_tenure_days": 100,
            "prior_chargeback_count": 0,
            "evidence": {f: False for f in rc.evidence_fields},
            "would_win_if_represented": False,
        }
        decision = decide(record, model, feature_columns)
        letter = generator.generate(record, decision, record["evidence"])

        for field_name, template in LETTER_SENTENCES.get(reason_code, []):
            fmt_kwargs = {
                "dispute_id": record["dispute_id"],
                "order_id": record["order_id"],
                "dispute_amount_inr": record["dispute_amount_inr"],
            }
            rendered_sentence = template.format(**fmt_kwargs)
            assert rendered_sentence not in letter


def test_audit_replay_reproduces_decision(tmp_path, monkeypatch):
    import app.audit as audit_module

    # Redirect the audit log to a temp file so this test doesn't pollute
    # (or depend on) the real project-root audit_log.jsonl.
    temp_log = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit_module, "AUDIT_LOG_PATH", temp_log)

    record = _sample_record()
    model, feature_columns = get_model()
    decision = decide(record, model, feature_columns)

    audit_id = audit_module.record_audit(record, decision)
    replayed = audit_module.replay(audit_id)

    assert replayed["decision"] == decision["decision"]
