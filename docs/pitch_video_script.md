# Pitch Video Script — Chargeback Evidence Responder
Razorpay AI Buildathon · Track: AI Risk Manager
Narrator: Dhwani Agarwal · Format: live demo walkthrough, solo · Target runtime: 5:00

A Word version of this script (`pitch_video_script.docx`) lives alongside this file.

---

## INTRO — 0:00 → 0:25 (~25s)

*(Face on camera, before switching to screen share)*

> "Hi, I'm Dhwani Agarwal. I built the Chargeback Evidence Responder for the Razorpay AI Buildathon, on the AI Risk Manager track.
>
> Fintech risk decisions are what actually pulled me into this track — not the model, the decision. Most 'AI risk' demos are a black-box score with a confidence number and nothing else. I wanted to build the opposite: a system that's bounded by an explicit rule, shows every number it used to decide, and is honest about exactly how good it is. That's what I'm going to show you."

---

## PAGE 1 — Overview (0:25 → 1:25, ~60s)

*Sidebar nav item already active on load: "Overview" (top item, marked active). No click needed to arrive here.*

**☞ CLICK:** Point at / hover the "Financial Impact" panel (left column) while you say the three numbers.

> "When a chargeback lands, a merchant has one decision to make: fight it, or eat the loss. Fight a case you'll lose, you waste money and staff time. Concede a case you would've won, you leave money on the table. Most merchants do this by gut feel — and both directions bleed money.
>
> Right here on the Overview — Financial Impact — three strategies, same 100-case test set. Concede everything: 301,000 rupees lost. Represent everything: 280,000. This system: 255,000. It beats both naive baselines."

**☞ CLICK:** Move to the "How the decision works" panel (right column, numbered steps 01–05) and trace down it with your cursor as you list the five steps.

> "And the five-step pipeline on the right: evidence collected, coverage evaluated, win probability calculated, expected value calculated, then represent or concede. Nothing hidden — every step is inspectable. Let's go look at an actual case."

---

## PAGE 2 — Disputes (table view) (1:25 → 1:55, ~30s)

**☞ CLICK:** Sidebar → click "Disputes" (under the "Operations" group label).

*You land on the dispute queue table: columns Dispute, Reason, Amount, Evidence, Win Prob, Expected Value, Recommendation, Status.*

**☞ CLICK (optional):** Click filter pill "Represent" briefly to show filtering works, then click "All" again before moving on.

> "This is the dispute queue — every test-set case, pre-scored: reason code, amount, evidence coverage, win probability, expected value, and the recommendation already sitting next to it. I can filter by Represent, Concede, Needs Review. Let's open a strong case first."

---

## PAGE 2A — Dispute Detail: the Represent case (1:55 → 3:10, ~75s)

**☞ CLICK:** Click any row where Evidence coverage is high and Recommendation reads "Represent." The detail panel opens on the right side of the screen.

**☞ CLICK:** Point at the top line of the detail panel, labeled with the rule text (`rule_applied`), as you explain the EV math.

> "Here's the decision workspace for one case. Top of the panel: `rule_applied` — the actual expected-value math, real numbers, no black box. Effective win probability times dispute amount, minus representment cost, checked against the minimum-worth-fighting threshold. You can read exactly why the system decided what it decided."

**☞ CLICK:** Point at the coverage ring (circular indicator), then scroll to the evidence checklist just below it.

**☞ CLICK:** Expand ONE checked evidence item (shows the grounded sentence), then expand ONE unchecked item (shows the "not present" note) — do this side by side so the contrast is visible on camera.

> "This coverage ring is evidence coverage for this reason code. Below it, the evidence checklist, item by item. Where a checkmark is present, there's grounded language behind it — I can expand it and see the actual sentence tied to that field. Where it's not present, it says so plainly: 'not present in this case's evidence file, so this sentence is NOT included in the letter.'"

**☞ CLICK:** Scroll down to the letter box (the rendered representment letter) and highlight/select one sentence with your cursor as you say it traces to a field.

> "And here's the letter itself, generated from only the checked items. Every sentence traces back to a field on this record. There's no LLM writing free text here — nothing to hallucinate."

---

## PAGE 2B — Dispute Detail: the Concede case (3:10 → 3:50, ~40s)

**☞ CLICK:** Click back to the Disputes table (left panel is still visible — just click a different row), pick a row with LOW evidence coverage and Recommendation "Concede."

**☞ CLICK:** Point at the coverage ring again — now visibly lower — then scroll straight to the memo box (same position the letter box was in for the previous case).

> "Now a thin-evidence case, same reason code. Coverage's low, so the model's confidence gets discounted, and expected value comes out negative. The decision: concede.
>
> And this is the part I want to be clear about — instead of a letter, the system writes an internal memo, clearly labeled, explaining why fighting this one doesn't pencil out. This isn't a fallback path. A system that only ever says 'fight' isn't managing risk, it's just optimism. This one knows when to say no."

---

## PAGE 2C — Audit trail (3:50 → 4:10, ~20s)

**☞ CLICK:** Scroll to the bottom of the detail panel — click the "View decision audit →" link.

*This expands the audit replay box in place; no page change.*

> "Every decision has an audit ID, and it's replayable — click here, and you get back the exact inputs, the rule that fired, the score, all of it. Nothing is a black box after the fact either."

---

## PAGE 3 — Risk Analytics (4:10 → 4:50, ~40s)

**☞ CLICK:** Sidebar → click "Risk Analytics" (under the "Analytics" group label).

**☞ CLICK:** Point across the four KPI tiles left to right (Precision, Recall, F1, AUC) as you read each number.

> "Here's the part that actually matters for this track: precision 0.483, recall 0.368, F1 0.418, AUC 0.62, on a 100-case held-out set. Modest, on purpose — a system this simple, working off noisy merchant records, shouldn't predict issuer arbitration with high accuracy, and it doesn't pretend to."

**☞ CLICK:** Move to the Confusion Matrix panel (left side of the analytics grid) and point at the FP and FN cells specifically — they have the plain-English explanations.

> "The confusion matrix shows exactly where it's wrong — false positives that waste a filing cost, false negatives that leave money on the table. And these labels aren't leaked from the same signal the model uses to decide — they're sampled independently in the data generator, so this number means something."

**☞ CLICK:** Scroll down to the Precision/Recall vs. probability threshold chart (the image at the bottom of the page) and point at its caption line.

> "This curve underneath is diagnostic only — it sweeps a plain probability cutoff, not the actual production rule. The real decision always goes through the EV math you saw a minute ago."

---

## CLOSE (4:50 → 5:00, ~10s)

**☞ CLICK:** Either scroll back up to the top of Risk Analytics, or click "Overview" in the sidebar to end on the same page you opened with.

> "Chargeback Evidence Responder — bounded, evidence-grounded, honestly evaluated. Live at the URL on screen, repo's public. Thanks for watching."

---

## Navigation cheat-sheet (all clicks, in order)

1. Start on Overview (default active view — no click).
2. Sidebar → "Disputes."
3. (Optional) Click filter pill "Represent," then click "All" again.
4. Click a high-coverage / "Represent" row → detail panel opens.
5. In detail panel: point at `rule_applied` line → coverage ring → expand one checked evidence item → expand one unchecked item → scroll to letter box.
6. Click a different, low-coverage / "Concede" row in the table → detail panel updates.
7. In detail panel: point at coverage ring → scroll to memo box.
8. Scroll to bottom of detail panel → click "View decision audit →" link.
9. Sidebar → "Risk Analytics."
10. Point across KPI tiles → Confusion Matrix (FP/FN cells) → scroll to PR curve image + caption.
11. End: Sidebar → "Overview" (or stay on Risk Analytics).

## Timing notes
- Full read sums to ~5:00 at a normal pace, including the intro.
- If a page load or click stalls on camera, trim first from Page 1 (Overview) or the Concede case section — both compress without losing the point.
- If you want more buffer, cut the "expand a grounded evidence item" beat in Page 2A — it's the single most skippable action.
- If running short, the Risk Analytics section can absorb another 10–15 seconds by reading one extra confusion-matrix cell aloud.
