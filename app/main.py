"""FastAPI application wiring the evidence-assembly -> scoring ->
decision -> letter -> audit pipeline together, and serving the demo UI.

Run with: uvicorn app.main:app --reload  (from the project root).

Endpoints:
    GET  /disputes                    list test-set disputes (id, reason_code, amount, ...)
    GET  /disputes/{id}               one dispute's full record
    POST /disputes/{id}/decide        runs coverage + score + EV decision
    POST /disputes/{id}/respond       runs decide() then generates letter/memo + audit id
    GET  /audit/{id}                  replay an audit record
    GET  /metrics                     serves eval/report.json
    GET  /pr-curve.png                serves eval/pr_curve.png
    /                                 static demo page (app/static/, mounted last)

Only the TEST split (data/disputes_test.json) is loaded as the
browsable dispute set at startup. The TRAIN split stays internal to
app/scoring.py, used only to fit the model.
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.audit import get_audit, record_audit, replay as audit_replay
from app.decision import decide
from app.letters import TemplateGenerator
from app.reason_codes import REASON_CODES
from app.scoring import get_model

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EVAL_DIR = ROOT / "eval"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Razorpay Chargeback Evidence Responder")

_letter_generator = TemplateGenerator()

with open(DATA_DIR / "disputes_test.json", "r", encoding="utf-8") as f:
    _TEST_DISPUTES = json.load(f)

_DISPUTES_BY_ID = {r["dispute_id"]: r for r in _TEST_DISPUTES}


def _get_record_or_404(dispute_id: str) -> dict:
    record = _DISPUTES_BY_ID.get(dispute_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No such dispute: {dispute_id}")
    return record


@app.get("/disputes")
def list_disputes():
    return [
        {
            "dispute_id": r["dispute_id"],
            "order_id": r["order_id"],
            "reason_code": r["reason_code"],
            "reason_description": REASON_CODES[r["reason_code"]].description,
            "dispute_amount_inr": r["dispute_amount_inr"],
        }
        for r in _TEST_DISPUTES
    ]


@app.get("/disputes/{dispute_id}")
def get_dispute(dispute_id: str):
    return _get_record_or_404(dispute_id)


@app.post("/disputes/{dispute_id}/decide")
def decide_dispute(dispute_id: str):
    record = _get_record_or_404(dispute_id)
    model, feature_columns = get_model()
    result = decide(record, model, feature_columns)
    return result


@app.post("/disputes/{dispute_id}/respond")
def respond_dispute(dispute_id: str):
    record = _get_record_or_404(dispute_id)
    model, feature_columns = get_model()
    result = decide(record, model, feature_columns)

    letter_text = _letter_generator.generate(record, result, record.get("evidence", {}))
    audit_id = record_audit(record, result)

    rc = REASON_CODES[record["reason_code"]]
    evidence_checklist = [
        {"field": f, "checked": record.get("evidence", {}).get(f) is True}
        for f in rc.evidence_fields
    ]

    return {
        "dispute_id": dispute_id,
        "decision": result,
        "evidence_checklist": evidence_checklist,
        "letter": letter_text,
        "audit_id": audit_id,
    }


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
