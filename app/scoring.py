"""Win-probability scoring model.

Called by: app/decision.py (decide()), app/main.py (API endpoints), and
eval/evaluate.py (offline evaluation). Trains a real scikit-learn
LogisticRegression on the synthetic training split produced by
data/generate_data.py -- deliberately not a hand-tuned rule, so the
resulting AUC is a defensible number rather than a formula that
trivially matches its own labels.

Feature inputs are strictly the OBSERVED fields on a dispute record
(record["evidence"], amount, tenure, prior_chargeback_count) -- never
the hidden generation-time latents. See data/generate_data.py's module
docstring for the full leakage-safety argument.
"""

import json
from pathlib import Path

from sklearn.linear_model import LogisticRegression

from app.reason_codes import REASON_CODES, all_evidence_fields

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

REASON_CODE_LIST = sorted(REASON_CODES.keys())
EVIDENCE_FIELDS = sorted(all_evidence_fields())
NUMERIC_FIELDS = ["dispute_amount_inr", "customer_tenure_days", "prior_chargeback_count"]


def build_feature_vector(record: dict) -> dict:
    """One-hot reason_code (6 cols) + every evidence field across all
    reason codes (present-for-this-record's-reason-code fields taken
    from record['evidence'] as 0/1, all other reason codes' fields fixed
    at 0) + the numeric fields. Column order is stable: sorted reason
    codes, then sorted evidence fields, then the numeric fields -- reused
    identically at train and predict time.
    """
    evidence = record.get("evidence", {})
    vec = {}
    for rc in REASON_CODE_LIST:
        vec[f"reason_code_{rc}"] = 1 if record.get("reason_code") == rc else 0
    for f in EVIDENCE_FIELDS:
        vec[f"evidence_{f}"] = 1 if evidence.get(f) is True else 0
    for f in NUMERIC_FIELDS:
        vec[f] = record.get(f, 0)
    return vec


def _feature_column_order() -> list:
    return (
        [f"reason_code_{rc}" for rc in REASON_CODE_LIST]
        + [f"evidence_{f}" for f in EVIDENCE_FIELDS]
        + list(NUMERIC_FIELDS)
    )


def train_model(train_records: list):
    """Returns (fitted LogisticRegression, feature_column_order list[str])."""
    columns = _feature_column_order()
    X = [[build_feature_vector(r)[c] for c in columns] for r in train_records]
    y = [1 if r["would_win_if_represented"] else 0 for r in train_records]

    model = LogisticRegression(max_iter=5000)
    model.fit(X, y)
    return model, columns


def predict_win_probability(model, feature_columns: list, record: dict) -> float:
    vec = build_feature_vector(record)
    x = [[vec[c] for c in feature_columns]]
    return float(model.predict_proba(x)[0][1])


_MODEL = None
_FEATURE_COLUMNS = None


def get_model():
    """Module-level singleton: trains once from data/disputes_train.json
    on first call and caches in memory. Training 300 rows of logistic
    regression is effectively instant, so no pickle persistence is
    needed for this project's scope.
    """
    global _MODEL, _FEATURE_COLUMNS
    if _MODEL is None:
        train_path = DATA_DIR / "disputes_train.json"
        with open(train_path, "r", encoding="utf-8") as f:
            train_records = json.load(f)
        _MODEL, _FEATURE_COLUMNS = train_model(train_records)
    return _MODEL, _FEATURE_COLUMNS
