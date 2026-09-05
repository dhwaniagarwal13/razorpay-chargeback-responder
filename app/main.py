"""FastAPI application wiring the evidence-assembly -> scoring ->
decision -> letter -> audit pipeline together, and serving the demo UI.

Run with: uvicorn app.main:app --reload  (from the project root).

Endpoints:
    GET  /disputes                    list test-set disputes, each pre-scored
                                       with decision/coverage/win_probability/
                                       EV/needs_review/status (see _enrich())
    GET  /disputes/{id}               one dispute's raw record
    POST /disputes/{id}/decide        runs coverage + score + EV decision
    POST /disputes/{id}/respond       runs decide() then generates letter/memo + audit id
    POST /disputes/{id}/resolve       marks a case resolved (in-memory only, see note)
    GET  /audit                       list all audit entries (Audit Log page)
    GET  /audit/{id}                  one audit entry
    GET  /audit/{id}/replay           replay an audit record
    GET  /metrics                     serves eval/report.json
    GET  /pr-curve.png                serves eval/pr_curve.png
    /                                 static demo page (app/static/, mounted last)

Only the TEST split (data/disputes_test.json) is loaded as the
browsable dispute set at startup. The TRAIN split stays internal to
app/scoring.py, used only to fit the model.

CASE STATUS NOTE: `_CASE_STATUS` is an in-memory dict, not a database --
consistent with this project's "no real database" scope (see README's
cut list). It resets on every server restart / cold start. This is
fine for a demo: it lets the UI show an open->resolved workflow without
adding real persistence infrastructure this project doesn't otherwise
need. It is NOT meant to survive redeploys.
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.audit import get_audit, list_audit, record_audit, replay as audit_replay
from app.decision import decide, get_config
from app.letters import TemplateGenerator, sentence_for
from app.reason_codes import REASON_CODES
from app.scoring import get_model

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EVAL_DIR = ROOT / "eval"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Not a real ML model registry -- just a fixed label for the decision
# engine's current logic version, shown in the UI/audit trail so a
# decision can be tied to "which rule made this call". Bump by hand
# whenever app/decision.py's rule or app/scoring.py's feature set changes.
MODEL_VERSION = "lr-v1.0"

app = FastAPI(title="Razorpay Chargeback Evidence Responder")

_letter_generator = TemplateGenerator()

with open(DATA_DIR / "disputes_test.json", "r", encoding="utf-8") as f:
    _TEST_DISPUTES = json.load(f)

_DISPUTES_BY_ID = {r["dispute_id"]: r for r in _TEST_DISPUTES}

# In-memory case status -- see module docstring's CASE STATUS NOTE.
_CASE_STATUS: dict = {}


def _get_record_or_404(dispute_id: str) -> dict:
    record = _DISPUTES_BY_ID.get(dispute_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No such dispute: {dispute_id}")
    return record


def _needs_review(record: dict, result: dict) -> bool:
    """A dispute is 'needs review' (vs. a confident auto-decision) when the
    win-probability is close to a coin flip, or evidence coverage is right
    at the edge of the reason code's floor -- both are honest signals of
    genuine uncertainty, not a fabricated status field. Thresholds are
    heuristic (not in config.yaml, since they don't affect the actual
    represent/concede decision -- purely a UI triage signal).
    """
    cfg = get_config()
    floor = cfg["evidence_coverage_floor"][record["reason_code"]]
    prob_borderline = 0.40 <= result["win_probability"] <= 0.60
    coverage_borderline = floor <= result["evidence_coverage"] < floor + 0.15
    return prob_borderline or coverage_borderline


def _enrich(record: dict, model, feature_columns: list) -> dict:
    """One dispute's list-row shape: identity fields + the full decision
    the engine would make right now, pre-computed so the Overview/Queue
    views don't need 100 separate API calls to populate their tables.
    """
    result = decide(record, model, feature_columns)
    return {
        "dispute_id": record["dispute_id"],
        "order_id": record["order_id"],
        "reason_code": record["reason_code"],
        "reason_description": REASON_CODES[record["reason_code"]].description,
        "dispute_amount_inr": record["dispute_amount_inr"],
        "decision": result["decision"],
        "win_probability": result["win_probability"],
        "evidence_coverage": result["evidence_coverage"],
        "expected_value_inr": result["expected_value_inr"],
        "needs_review": _needs_review(record, result),
        "status": _CASE_STATUS.get(record["dispute_id"], "open"),
    }


@app.get("/disputes")
def list_disputes():
    model, feature_columns = get_model()
    return [_enrich(r, model, feature_columns) for r in _TEST_DISPUTES]


@app.get("/disputes/{dispute_id}")
def get_dispute(dispute_id: str):
    return _get_record_or_404(dispute_id)


@app.post("/disputes/{dispute_id}/decide")
def decide_dispute(dispute_id: str):
    record = _get_record_or_404(dispute_id)
    model, feature_columns = get_model()
    result = decide(record, model, feature_columns)
    result["model_version"] = MODEL_VERSION
    result["needs_review"] = _needs_review(record, result)
    return result


@app.post("/disputes/{dispute_id}/respond")
def respond_dispute(dispute_id: str):
    record = _get_record_or_404(dispute_id)
    model, feature_columns = get_model()
    result = decide(record, model, feature_columns)
    result["model_version"] = MODEL_VERSION
    result["needs_review"] = _needs_review(record, result)

    letter_text = _letter_generator.generate(record, result, record.get("evidence", {}))
    audit_id = record_audit(record, result)

    rc = REASON_CODES[record["reason_code"]]
    evidence_checklist = [
        {
            "field": f,
            "checked": record.get("evidence", {}).get(f) is True,
            "detail": sentence_for(record["reason_code"], f, record),
        }
        for f in rc.evidence_fields
    ]

    return {
        "dispute_id": dispute_id,
        "decision": result,
        "evidence_checklist": evidence_checklist,
        "letter": letter_text,
        "audit_id": audit_id,
        "status": _CASE_STATUS.get(dispute_id, "open"),
    }


@app.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str):
    """Marks a case resolved -- the UI action behind "Send to processor"
    and "Record concession". This does not call any real payment
    processor or network (no such integration exists in this project,
    by design -- see README's cut list); it records that the analyst
    completed the workflow step for this case. In-memory only, see
    module docstring.
    """
    _get_record_or_404(dispute_id)  # 404s if the id doesn't exist
    _CASE_STATUS[dispute_id] = "resolved"
    return {"dispute_id": dispute_id, "status": "resolved"}


@app.get("/audit")
def list_audit_entries():
    return list_audit()


@app.get("/audit/{audit_id}")
def get_audit_entry(audit_id: str):
    entry = get_audit(audit_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No such audit entry: {audit_id}")
    return entry


@app.get("/audit/{audit_id}/replay")
def replay_audit_entry(audit_id: str):
    try:
        result = audit_replay(audit_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@app.get("/metrics")
def get_metrics():
    report_path = EVAL_DIR / "report.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="eval/report.json not found -- run `python eval/evaluate.py` first",
        )
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/pr-curve.png")
def get_pr_curve():
    png_path = EVAL_DIR / "pr_curve.png"
    if not png_path.exists():
        raise HTTPException(
            status_code=404,
            detail="eval/pr_curve.png not found -- run `python eval/evaluate.py` first",
        )
    return FileResponse(png_path, media_type="image/png")


# Mounted last so the API routes above take precedence over static "/".
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
