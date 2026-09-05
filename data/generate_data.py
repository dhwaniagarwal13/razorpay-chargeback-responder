"""Synthetic chargeback-dispute generator.

Called by: run directly (`python data/generate_data.py`) to (re)produce
`data/disputes_train.json` and `data/disputes_test.json`, which are then
consumed by app/scoring.py (training), eval/evaluate.py (evaluation),
and app/main.py (browsable test-set disputes at API startup).

THE LEAKAGE TRAP (read this before touching anything below):
--------------------------------------------------------------
There are two parallel worlds for each dispute:

  1. The HIDDEN/LATENT world: `true_<field>` booleans, `case_difficulty`,
     `issuer_strictness`, `evidence_strength_true`, `win_prob_true`. These
     represent "what actually happened" and are used ONLY to sample the
     outcome label `would_win_if_represented`. They are never written to
     the output JSON and never shown to the model or the app.

  2. The OBSERVED world: `evidence` (the `observed_<field>` booleans,
     stored under plain field names) -- this is what the merchant *has
     on file* / can present to the issuer. This is the ONLY evidence
     input the ML model (app/scoring.py) and the decision engine ever
     see.

`would_win_if_represented` is generated from the HIDDEN facts (truth),
not from `evidence` (what's on file) or from the coverage() formula the
scorer/decision engine computes over `evidence`. Because the label's
causal parents (true_<field>, issuer_strictness, case_difficulty) are
never fed to the model as features, and the model only ever sees the
noisy `evidence` dict, there is a structural gap between "what predicts
the label during generation" and "what the model is allowed to use to
predict it". That gap is exactly what keeps the trained
precision/recall/AUC in a realistic (not-100%) range -- see
eval/evaluate.py's sanity check.

To spell it out once more: using `would_win_if_represented` as the
*training label* is fine and is NOT leakage -- a label is supposed to be
downstream of ground truth. Leakage would mean feeding something
downstream of (or equal to) the label's own generating process back in
as an *input feature*. We never do that: the only features are
`evidence` (noisy observations of `true_*`, not `true_*` itself) plus
amount/tenure/prior-chargeback-count, none of which are inputs to the
win_prob_true sigmoid.
"""

import json
import random
import sys
from pathlib import Path

import numpy as np

# Allow `python data/generate_data.py` (run directly, not as `-m`) to find
# the `app` package by putting the project root on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.reason_codes import REASON_CODES

SEED = 42
N_TOTAL = 400
N_TRAIN = 300
N_TEST = 100

DATA_DIR = Path(__file__).resolve().parent

REASON_CODE_LIST = list(REASON_CODES.keys())
# Slight upweighting of the two most common real-world reason codes
# (not received / not as described) -- purely for realism, not required.
REASON_CODE_WEIGHTS = {
    "10.4": 0.15,
    "13.1": 0.22,
    "13.3": 0.22,
    "13.6": 0.15,
    "13.2": 0.13,
    "UPI_UNAUTHORIZED": 0.13,
}


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def gen_dispute(idx: int, rng: np.random.Generator) -> dict:
    dispute_id = f"D{idx:04d}"
    order_id = f"O{idx:05d}"

    reason_code = random.choices(
        REASON_CODE_LIST,
        weights=[REASON_CODE_WEIGHTS[c] for c in REASON_CODE_LIST],
        k=1,
    )[0]
    fields = REASON_CODES[reason_code].evidence_fields

    # dispute amount: lognormal draw, clipped to [300, 15000], rounded to 10
    raw_amount = rng.lognormal(mean=7.8, sigma=0.7)
    amount = float(np.clip(raw_amount, 300, 15000))
    amount = round(amount / 10.0) * 10

    customer_tenure_days = int(random.randint(0, 1500))
    prior_chargeback_count = int(np.clip(rng.poisson(0.3), 0, 5))

    # ---- HIDDEN LATENTS (never written to output) ----
    case_difficulty = float(rng.beta(2, 2))
    issuer_strictness = float(rng.normal(0, 1))

    base_rate = 0.6
    effective_rate = base_rate * (1 - 0.5 * case_difficulty)
    effective_rate = float(np.clip(effective_rate, 0.05, 0.95))

    true_facts = {}
    observed = {}
    for f in fields:
        true_val = bool(rng.random() < effective_rate)
        true_facts[f] = true_val
        if true_val:
            observed_val = bool(rng.random() < 0.90)  # 10% under-recording
        else:
            observed_val = bool(rng.random() < 0.05)  # 5% false positive
        observed[f] = observed_val

    evidence_strength_true = (
        sum(1 for v in true_facts.values() if v) / len(true_facts) if true_facts else 0.0
    )

    win_prob_true = sigmoid(
        4 * (evidence_strength_true - 0.5)
        - 1.0 * issuer_strictness
        - 1.5 * case_difficulty
        + rng.normal(0, 0.3)
    )
    would_win_if_represented = bool(rng.random() < win_prob_true)

    return {
        "dispute_id": dispute_id,
        "order_id": order_id,
        "reason_code": reason_code,
        "dispute_amount_inr": amount,
        "customer_tenure_days": customer_tenure_days,
        "prior_chargeback_count": prior_chargeback_count,
        "evidence": observed,
        "would_win_if_represented": would_win_if_represented,
    }


def main():
    np.random.seed(SEED)
    random.seed(SEED)
    rng = np.random.default_rng(SEED)

    records = [gen_dispute(i, rng) for i in range(1, N_TOTAL + 1)]
    random.shuffle(records)

    train = records[:N_TRAIN]
    test = records[N_TRAIN : N_TRAIN + N_TEST]

    with open(DATA_DIR / "disputes_train.json", "w", encoding="utf-8") as f:
        json.dump(train, f, indent=2)
    with open(DATA_DIR / "disputes_test.json", "w", encoding="utf-8") as f:
        json.dump(test, f, indent=2)

    def balance(split, name):
        n = len(split)
        pos = sum(1 for r in split if r["would_win_if_represented"])
        pct = 100.0 * pos / n if n else 0.0
        print(f"{name}: n={n}, would_win_if_represented=True: {pos} ({pct:.1f}%)")

    print("Generated data/disputes_train.json and data/disputes_test.json")
    balance(train, "train")
    balance(test, "test")


if __name__ == "__main__":
    main()
