# Pitch Video Script — Chargeback Evidence Responder
Razorpay AI Buildathon · Track: AI Risk Manager · Solo narration, live demo walkthrough
Target runtime: 5:00

---

## [0:00–0:30] Hook — the dilemma

**(Face or voiceover over the app's landing page, no clicking yet)**

"When a chargeback lands, a merchant has one decision to make: fight it, or eat the loss.

Fight a case you'll lose, you waste money and staff time on a representment package that goes nowhere. Concede a case you would've won, you leave money on the table you didn't have to lose.

Most merchants do this by gut feel, or a blanket rule — 'always fight,' or 'never fight anything under a thousand rupees.' Both directions bleed money, quietly, every month.

This is a system that makes that call from evidence — bounded by an explicit rule, with every number it used shown next to the decision — and it's honest about how good it actually is, because that's what this track is graded on."

---

## [0:30–1:00] Pipeline overview

**(Cut to architecture diagram or fast scroll through docs/architecture.md)**

"Five stages. A dispute and its order record come in. First, evidence assembly — a reason-code checklist, what's required versus what's actually on file. Second, a win-probability score from a logistic regression model trained on observed features. Third, a bounded decision — expected value, discounted by evidence coverage, against thresholds that live in one config file. Fourth, a letter or an internal memo, template-only, every claim tied to a source field. Fifth, an audit trail — every input, every rule fired, replayable."

---

## [1:00–2:15] Live demo — the represent path

**(Screen: submit a dispute with strong evidence — pick a 13.1 "not received" case with tracking + delivery confirmation on file)**

"Let's run one. This is a reason-code 13.1 dispute — goods not received — for [amount]. The merchant has tracking confirmation and a signed delivery receipt on file.

[Submit.]

Here's the evidence checklist — required items for this reason code versus what's observed. Coverage is high.

Here's the win-probability score from the model — [X]%.

And here's the decision. Represent. And critically — here's `rule_applied`: the exact expected-value math, real numbers, no black box. Effective win probability times dispute amount, minus representment cost, compared against the minimum-worth-fighting threshold. You can read exactly why the system decided what it decided.

And here's the letter it generated — every sentence cites the evidence field it's grounded in. If a field isn't observed `True`, that sentence doesn't get written. There's no LLM in this path — nothing to hallucinate."

---

## [2:15–2:45] Live demo — the concede path

**(Screen: submit a second dispute — weak/missing evidence)**

"Now the other case. Thin evidence, same reason code.

[Submit.]

Coverage is low here — the model's confidence gets discounted by that gap. Expected value comes out negative.

The decision: concede. And this is the part I want to be clear about — this isn't a fallback, it's a first-class output. Instead of a customer-facing letter, the system writes an internal memo explaining exactly why fighting this one doesn't pencil out. A system that only ever tells you to fight isn't managing risk, it's just optimism. This one knows when to say no."

---

## [2:45–3:45] The honest evaluation story

**(Screen: README results table, or eval/pr_curve.png)**

"Here's the part that actually matters for this track: how do you know any of this works, without the model just grading its own homework?

The failure mode here is label leakage — if your evaluation labels come from the same signal your model uses to decide, your precision and recall come out looking amazing and mean nothing.

So the synthetic data is built in layers. Every dispute gets hidden, latent 'true' evidence facts — what actually happened. The observed evidence — the only thing the model or the app ever sees — is those true facts passed through independent recording noise, because real merchant record-keeping is imperfect. And the outcome label is sampled from the true facts plus an independent issuer-strictness draw and case-difficulty draw — a process that never touches the feature vector the model trains on.

Result: precision 0.48, recall 0.37, F1 0.42, AUC 0.62, on a 100-record held-out set. That's a real, honestly modest number — not a suspicious near-1.0. A system this simple, working off noisy merchant-side records, shouldn't be able to predict issuer arbitration with high accuracy. And it doesn't.

But modest metrics still beat blind policy. Concede everything: 301,000 rupees lost. Represent everything: 280,000. This system: 255,000. It beats both naive baselines, on the same batch — 45,000 saved versus conceding blind, 25,000 saved versus fighting blind."

---

## [3:45–4:20] Defense-only by construction

**(Screen: app/letters.py, brief scroll — or just narrate over the demo UI)**

"One more thing worth saying plainly. This system can't fabricate, infer, or embellish evidence. Every sentence in a generated letter binds to a specific field that has to be observed `True` on the record. There's no free-text generation in this path — no LLM, so nothing to hallucinate a claim that isn't there. The concede path exists specifically to catch the case where evidence is too thin to responsibly represent."

---

## [4:20–4:45] Scope, deliberately cut

**(Screen: README "What's not built" section)**

"What's not here, on purpose: auth, a real database, multi-tenant support, real payment-processor integration, an actual LLM drafting the final prose. All cut deliberately, tonight, to keep the scope on the one thing that actually matters — a decision that's honestly measured, not surface area."

---

## [4:45–5:00] Close

**(Back to face, or landing page)**

"Chargeback Evidence Responder — bounded, evidence-grounded, honestly evaluated. Live at [vercel URL], repo's public, and everything you just saw, the audit log can replay. Thanks for watching."

---

## Timing notes
- Budget ~10–15 seconds of slack across sections for demo load times / re-takes — the block above sums to ~4:45 of read time at a normal pace.
- If running long, cut first from **[3:45–4:20]** (defense-only) — it's the most restatable in one sentence during the close instead.
- If running short, extend **[2:45–3:45]** — this is the emphasis you chose; it can absorb another 15–20 seconds of the report.json numbers or a quick pan across `eval/pr_curve.png`.
