// Vanilla JS demo page for the Chargeback Evidence Responder.
// No build step, no framework. Fetches from the same-origin FastAPI app.

const disputesUl = document.getElementById("disputes-ul");
const detailPanel = document.getElementById("dispute-detail");
const metricsContent = document.getElementById("metrics-content");

const tabDisputesBtn = document.getElementById("tab-disputes");
const tabMetricsBtn = document.getElementById("tab-metrics");
const viewDisputes = document.getElementById("view-disputes");
const viewMetrics = document.getElementById("view-metrics");

function showTab(name) {
  const disputesActive = name === "disputes";
  tabDisputesBtn.classList.toggle("active", disputesActive);
  tabMetricsBtn.classList.toggle("active", !disputesActive);
  viewDisputes.classList.toggle("active", disputesActive);
  viewMetrics.classList.toggle("active", !disputesActive);
  if (!disputesActive) loadMetrics();
}

tabDisputesBtn.addEventListener("click", () => showTab("disputes"));
tabMetricsBtn.addEventListener("click", () => showTab("metrics"));

async function loadDisputes() {
  const res = await fetch("/disputes");
  const disputes = await res.json();
  disputesUl.innerHTML = "";
  for (const d of disputes) {
    const li = document.createElement("li");
    li.dataset.id = d.dispute_id;
    li.innerHTML = `
      <div class="dispute-id">${d.dispute_id} &middot; ${d.reason_code}</div>
      <div class="dispute-meta">${d.reason_description} &mdash; INR ${d.dispute_amount_inr}</div>
    `;
    li.addEventListener("click", () => selectDispute(d.dispute_id, li));
    disputesUl.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function selectDispute(disputeId, liEl) {
  document.querySelectorAll("#disputes-ul li").forEach((el) => el.classList.remove("selected"));
  liEl.classList.add("selected");

  detailPanel.innerHTML = `<p class="placeholder">Running decision pipeline for ${disputeId}...</p>`;

  const respondRes = await fetch(`/disputes/${disputeId}/respond`, { method: "POST" });
  if (!respondRes.ok) {
    detailPanel.innerHTML = `<p class="placeholder">Error running pipeline for ${disputeId}.</p>`;
    return;
  }
  const data = await respondRes.json();
  const decision = data.decision;
  const isRepresent = decision.decision === "represent";

  const checklistHtml = data.evidence_checklist
    .map(
      (item) =>
        `<li class="${item.checked ? "checked" : "unchecked"}">${escapeHtml(item.field)}</li>`
    )
    .join("");

  detailPanel.innerHTML = `
    <h2>${disputeId}</h2>
    <span class="decision-badge ${isRepresent ? "represent" : "concede"}">${decision.decision}</span>
    <div class="rule-applied">${escapeHtml(decision.rule_applied)}</div>
    <p>
      win_probability: <strong>${decision.win_probability.toFixed(3)}</strong> &middot;
      evidence_coverage: <strong>${decision.evidence_coverage.toFixed(3)}</strong> &middot;
      expected_value_inr: <strong>${decision.expected_value_inr.toFixed(2)}</strong>
    </p>

    <h3 class="section-title">Evidence checklist</h3>
    <ul class="checklist">${checklistHtml}</ul>

    <h3 class="section-title">${isRepresent ? "Rebuttal letter" : "Concede memo"}</h3>
    <div class="letter-box ${isRepresent ? "represent-letter" : "concede-memo"}">${escapeHtml(data.letter)}</div>

    <p class="audit-id">audit_id: ${data.audit_id}</p>
  `;
}

async function loadMetrics() {
  metricsContent.innerHTML = `<p class="placeholder">Loading metrics...</p>`;
  const res = await fetch("/metrics");
  if (!res.ok) {
    metricsContent.innerHTML = `<p class="placeholder">No eval/report.json found. Run: python eval/evaluate.py</p>`;
    return;
  }
  const report = await res.json();
  const cm = report.confusion_matrix;
  const money = report.money;

  metricsContent.innerHTML = `
    <div class="metrics-grid">
      <div>
        <h3 class="section-title">Confusion matrix (positive = "represent")</h3>
        <table class="metrics-table">
          <tr><th></th><th>Actual: would win</th><th>Actual: would lose</th></tr>
          <tr><th>Predicted: represent</th><td>TP ${cm.tp}</td><td>FP ${cm.fp}</td></tr>
          <tr><th>Predicted: concede</th><td>FN ${cm.fn}</td><td>TN ${cm.tn}</td></tr>
        </table>
        <table class="metrics-table">
          <tr><th>Precision</th><td>${report.precision.toFixed(3)}</td></tr>
          <tr><th>Recall</th><td>${report.recall.toFixed(3)}</td></tr>
          <tr><th>F1</th><td>${report.f1.toFixed(3)}</td></tr>
          <tr><th>AUC</th><td>${report.auc.toFixed(3)}</td></tr>
          <tr><th>n_test</th><td>${report.n_test}</td></tr>
        </table>

        <h3 class="section-title">Money vs. baselines (total loss, INR, lower is better)</h3>
        <table class="metrics-table">
          <tr><th>Strategy</th><th>Total loss (INR)</th></tr>
          <tr><td>concede_everything</td><td>${money.concede_everything_inr.toLocaleString()}</td></tr>
          <tr><td>represent_everything</td><td>${money.represent_everything_inr.toLocaleString()}</td></tr>
          <tr><td>this_system</td><td><strong>${money.this_system_inr.toLocaleString()}</strong></td></tr>
        </table>
        <p>
          Savings vs. concede_everything: <strong>${money.savings_vs_concede_everything_inr.toLocaleString()} INR</strong><br/>
          Savings vs. represent_everything: <strong>${money.savings_vs_represent_everything_inr.toLocaleString()} INR</strong>
        </p>
      </div>
      <div>
        <h3 class="section-title">Precision / Recall vs. probability threshold</h3>
        <p class="placeholder">Diagnostic curve only -- not the production EV decision rule.</p>
        <img id="pr-curve-img" src="/pr-curve.png?t=${Date.now()}" alt="Precision/Recall vs threshold curve" />
      </div>
    </div>
  `;
}

loadDisputes();
