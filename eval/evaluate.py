"""Evaluation harness -- the actual deliverable for the buildathon track
(the rebuttal letter is just the visible artifact on top of this).

Called by: run directly (`python eval/evaluate.py`) to produce
eval/report.json (served by GET /metrics in app/main.py) and
eval/pr_curve.png (served by GET /pr-curve.png and shown in the demo
page's Metrics section).

Computes, over data/disputes_test.json:
  - confusion matrix / precision / recall / F1 for the actual production
    decision rule (decide() in app/decision.py), positive class =
    "represent"
  - AUC of the raw win_probability model output vs. the ground-truth
    would_win_if_represented label
  - a precision/recall-vs-threshold sweep using ONLY the win-probability
    model output thresholded directly (NOT the EV rule) -- a diagnostic
    curve, see app/decision.py's module docstring for why this is kept
    separate from the production rule
  - a money table comparing three strategies' total loss over the whole
    test set: concede_everything, represent_everything, this_system.

IMPORTANT SANITY CHECK (do not skip): precision/recall/F1 must NOT be
~1.0 -- that would indicate label leakage snuck back into the generator
(see data/generate_data.py's docstring). A realistic outcome lands
roughly in the 0.65-0.90 precision/recall range with AUC roughly
0.75-0.88. We report the actual numbers produced by this run below,
whatever they are -- the generator is not tuned to hit a "nicer" number.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.decision import decide, get_config
from app.scoring import get_model, predict_win_probability

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EVAL_DIR = ROOT / "eval"


def load_test_records():
    with open(DATA_DIR / "disputes_test.json", "r", encoding="utf-8") as f:
        return json.load(f)


def confusion_matrix_metrics(records, model, feature_columns):
    tp = fp = fn = tn = 0
    decisions = []
    for r in records:
        result = decide(r, model, feature_columns)
        decisions.append((r, result))
        pred_positive = result["decision"] == "represent"
        actual_positive = r["would_win_if_represented"]
        if pred_positive and actual_positive:
            tp += 1
        elif pred_positive and not actual_positive:
            fp += 1
        elif not pred_positive and actual_positive:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "decisions": decisions,
    }


def threshold_sweep(records, model, feature_columns):
    """Sweep win_probability_threshold from 0.1 to 0.9 step 0.05, using
    ONLY the raw model probability (ignoring EV/coverage), to produce a
    diagnostic precision/recall-vs-threshold curve. See module docstring.
    """
    probs = [predict_win_probability(model, feature_columns, r) for r in records]
    labels = [1 if r["would_win_if_represented"] else 0 for r in records]

    thresholds = [round(0.1 + 0.05 * i, 2) for i in range(0, 17)]  # 0.10..0.90
    precisions, recalls = [], []
    for t in thresholds:
        tp = fp = fn = 0
        for p, y in zip(probs, labels):
            pred = p >= t
            if pred and y:
                tp += 1
            elif pred and not y:
                fp += 1
            elif not pred and y:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        precisions.append(precision)
        recalls.append(recall)

    return thresholds, precisions, recalls, probs, labels


def plot_pr_curve(thresholds, precisions, recalls, out_path: Path):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(thresholds, precisions, marker="o", label="Precision")
    ax.plot(thresholds, recalls, marker="s", label="Recall")
    ax.set_xlabel("win_probability_threshold (diagnostic cutoff, not the production rule)")
    ax.set_ylabel("score")
    ax.set_title("Precision / Recall vs. probability threshold (test set)")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def money_table(decisions, representment_cost_inr):
    concede_everything = 0.0
    represent_everything = 0.0
    this_system = 0.0

    for record, result in decisions:
        amount = record["dispute_amount_inr"]
        would_win = record["would_win_if_represented"]

        # concede_everything: always concede
        concede_everything += amount

        # represent_everything: always represent
        if would_win:
            represent_everything += representment_cost_inr
        else:
            represent_everything += amount + representment_cost_inr

        # this_system: use the actual EV-rule decision
        if result["decision"] == "represent":
            if would_win:
                this_system += representment_cost_inr
            else:
                this_system += amount + representment_cost_inr
        else:
            this_system += amount

    return {
        "concede_everything_inr": concede_everything,
        "represent_everything_inr": represent_everything,
        "this_system_inr": this_system,
        "savings_vs_concede_everything_inr": concede_everything - this_system,
        "savings_vs_represent_everything_inr": represent_everything - this_system,
    }


def main():
    cfg = get_config()
    representment_cost = cfg["representment_cost_inr"]

    records = load_test_records()
    model, feature_columns = get_model()

    cm_metrics = confusion_matrix_metrics(records, model, feature_columns)
    decisions = cm_metrics.pop("decisions")

    thresholds, precisions, recalls, probs, labels = threshold_sweep(
        records, model, feature_columns
    )
    EVAL_DIR.mkdir(exist_ok=True)
    plot_pr_curve(thresholds, precisions, recalls, EVAL_DIR / "pr_curve.png")

    auc = roc_auc_score(labels, probs)

    money = money_table(decisions, representment_cost)

    report = {
        "confusion_matrix": cm_metrics["confusion_matrix"],
        "precision": cm_metrics["precision"],
        "recall": cm_metrics["recall"],
        "f1": cm_metrics["f1"],
        "auc": auc,
        "money": money,
        "n_test": len(records),
    }

    with open(EVAL_DIR / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 60)
    print("CONFUSION MATRIX (positive class = 'represent')")
    print(cm_metrics["confusion_matrix"])
    print(f"Precision: {cm_metrics['precision']:.3f}")
    print(f"Recall:    {cm_metrics['recall']:.3f}")
    print(f"F1:        {cm_metrics['f1']:.3f}")
    print(f"AUC:       {auc:.3f}")
    print()
    print("SANITY CHECK: precision/recall/F1 should NOT be ~1.0 (would imply")
    print("label leakage). Expected realistic range ~0.65-0.90, AUC ~0.75-0.88.")
    print()
    print("THRESHOLD SWEEP (diagnostic only, not the production rule):")
    for t, p, r in zip(thresholds, precisions, recalls):
        print(f"  threshold={t:.2f}  precision={p:.3f}  recall={r:.3f}")
    print()
    print("MONEY TABLE (total loss in INR over test set, lower is better):")
    for k, v in money.items():
        print(f"  {k}: {v:,.2f}")
    print()
    print(f"Wrote {EVAL_DIR / 'report.json'} and {EVAL_DIR / 'pr_curve.png'}")


if __name__ == "__main__":
    main()
