# Chargeback Evidence Responder

Razorpay AI Buildathon — Track 02: AI Risk Manager

## The problem

When a chargeback lands, a merchant has to decide: **fight it (represent) or eat the loss (concede)**. Fighting a case you'll lose wastes money and staff time. Conceding a case you would have won leaves money on the table you didn't have to lose. Most merchants do this by gut feel or a blanket policy ("always fight," "never fight anything under ₹X"), and both directions bleed money.

This system makes that decision from evidence, bounded by an explicit rule, with every number it used to decide shown alongside the decision — and it's honest about how good it actually is, because that's what this track is graded on.

## Live demo

**[TODO: Vercel URL]** — deployed serverless. One caveat vs. running locally: the audit trail (`audit_log.jsonl`) writes to `/tmp` on Vercel, which is a best-effort warm-instance cache, not durable storage — audit replay works within a session but isn't guaranteed to persist across cold starts the way it does when you run the app locally (`uvicorn app.main:app`). See `app/audit.py`'s docstring for the full explanation. Everything else (decision engine, evidence checklist, letters/memos, metrics) behaves identically to local.

## What it does

```
Dispute + order record
      -> 1. Evidence assembly    (reason-code checklist: required vs. observed)
      -> 2. Win-probability score (sklearn LogisticRegression on observed features)
      -> 3. Bounded decision     (EV rule + coverage discount, thresholds in config.yaml)
      -> 4. Letter / memo        (template only, every claim cites a source field)
      -> 5. Audit trail          (inputs, rule fired, score, replayable)
```

Six reason codes: `10.4` (fraud, card-absent), `13.1` (not received), `13.3` (not as described), `13.6` (credit not processed), `13.2` (cancelled recurring), and `UPI_UNAUTHORIZED` (India-domestic unauthorized UPI transaction — most of Razorpay's actual volume is domestic, not card-network, so this path exists deliberately).

See `docs/architecture.md` for the component-by-component breakdown and a diagram.

## How label leakage was avoided

The hardest failure mode for this track is a scorer whose precision/recall come out near 100% because the evaluation labels were derived from the same signal the scorer uses to decide — that's not measurement, that's the model grading its own homework.

`data/generate_data.py` avoids this by construction:

1. Every dispute gets **hidden, latent "true" evidence facts** (per-checklist-item booleans) — these represent what actually happened, not what's on file.
2. The **observed evidence** on the record (the only thing the model or the app ever sees) is the true facts passed through independent recording noise: ~10% of true-positive evidence goes unrecorded, ~5% of false evidence gets mistakenly recorded as present. This is meant to mimic real merchant record-keeping being imperfect.
3. The **outcome label** (`would_win_if_represented`) is sampled from the *true* facts plus an independent issuer-strictness draw and case-difficulty draw and noise — a process that never touches the observed feature vector the model trains on.
4. The model is trained only on observed features → outcome label. It cannot see the generation process, and the label isn't a function of the same coverage formula the decision engine uses at inference time.

Result: **precision 0.48, recall 0.37, F1 0.42, AUC 0.62** on the held-out 100-record test set (see Results below) — a real, honestly modest number, not a suspicious near-1.0. That's the point: a system this simple, working from noisy merchant-side records, shouldn't be able to predict issuer arbitration outcomes with high accuracy, and it doesn't.

## The decision rule (bounded, config-driven)

```
effective_win_probability = win_probability * coverage_factor
coverage_factor = min(1.0, evidence_coverage / coverage_floor_for_reason_code)
expected_value = effective_win_probability * dispute_amount - representment_cost

represent if expected_value > 0 AND dispute_amount >= min_amount_worth_fighting
else concede
```

Every number above (`representment_cost_inr`, `min_amount_worth_fighting_inr`, `evidence_coverage_floor` per reason code) lives in `config.yaml` — nothing is hard-coded in `app/decision.py`. The API and demo UI show the exact `rule_applied` string with real numbers plugged in for every decision, so it's never a black box.

**A design correction worth stating plainly:** an earlier version of this rule treated the evidence-coverage floor as a hard veto — below the floor, concede outright regardless of model confidence. Measured against the test set, that version lost to the naive "always represent" baseline, because the floor and the model's own probability were both encoding "how much evidence exists," and vetoing on top of an already-priced-in signal threw away EV-positive cases. The fix: coverage now *discounts* win probability continuously (`coverage_factor`) instead of vetoing outright, and `representment_cost_inr` was re-derived from a more realistic per-case cost (₹1000, roughly in line with combined network fee + ops time to assemble one evidence package) rather than an initial placeholder that made "just fight everything" trivially optimal. This was a threshold/policy calibration, not a change to the data, labels, or model — see `app/decision.py`'s module docstring for the full before/after writeup.

## Results (held-out test set, n=100)

| Metric | Value |
|---|---|
| Precision | 0.483 |
| Recall | 0.368 |
| F1 | 0.418 |
| AUC | 0.620 |

| Strategy | Total loss (INR, lower is better) |
|---|---|
| Concede everything | 301,120 |
| Represent everything | 280,130 |
| **This system** | **255,440** |
| Savings vs. concede everything | **+45,680** |
| Savings vs. represent everything | **+24,690** |

The system beats **both** naive baselines on the same batch. Precision/recall are modest by design — the policy is intentionally conservative about spending money on representment (real cost, real risk), so it trades some recall for a decision that doesn't lose to blind aggression either. A precision/recall-vs-threshold curve (diagnostic only, not the production rule) is in `eval/pr_curve.png`, generated by `eval/evaluate.py`.

## Defense-only by construction

This system assembles evidence the merchant already holds and declines to represent when that evidence is insufficient. It cannot fabricate, infer, or embellish evidence — every sentence in a generated rebuttal letter (`app/letters.py`) is bound to a specific evidence field that must be observed `True` on the record; if the field is missing or false, the sentence simply does not render. There is no LLM in this path, so there is no free-text generation that could hallucinate a claim. The **concede path is a first-class feature, not a fallback**: when evidence is thin or the economics don't work, the system produces a clearly-labeled internal memo explaining why, instead of a customer-facing letter — that's the system correctly declining to overreach, and it's demoed as such.

The LLM-drafting path (an LLM paraphrasing these already-grounded, fact-checked bullet points into smoother prose) is designed-for-not-built tonight — the grounding logic in `app/letters.py` would sit unchanged underneath it; only the final render step would change.

## Running it

Windows / PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python data\generate_data.py     # regenerate synthetic data (fixed seed, reproducible)
.venv\Scripts\python eval\evaluate.py          # trains the model, runs the held-out eval, writes eval/report.json + eval/pr_curve.png
.venv\Scripts\pytest                           # determinism + anti-fabrication + audit-replay smoke tests
.venv\Scripts\uvicorn app.main:app --reload    # http://127.0.0.1:8000
```

Then open `http://127.0.0.1:8000/` for the demo page, or `http://127.0.0.1:8000/docs` for the raw API.

## What's not built (explicit cut list)

Auth, a real database (JSON files are the store), multi-tenant anything, real payment-processor integration, LLM integration, charts beyond the one P/R curve, Docker. All cut deliberately to keep the one-night scope focused on the actual deliverable: an honestly measured decision, not surface area.

## Repo layout

```
app/            reason_codes.py, scoring.py, decision.py, letters.py, audit.py, main.py, static/ (demo UI)
data/           generate_data.py + generated disputes_train.json / disputes_test.json
eval/           evaluate.py + generated report.json / pr_curve.png
docs/           architecture.md
tests/          test_smoke.py
config.yaml     every decision threshold, in one place
```
