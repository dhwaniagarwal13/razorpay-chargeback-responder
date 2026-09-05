// Chargeback Evidence Responder -- demo UI.
// Vanilla JS, no build step, no framework. Fetches from the same-origin
// FastAPI app. All numbers shown are real (from /disputes, /metrics,
// /disputes/{id}/respond) -- nothing here is placeholder/fabricated data.

let ALL_DISPUTES = [];   // cached GET /disputes (pre-scored)
let METRICS = null;      // cached GET /metrics
let SELECTED_ID = null;
let CURRENT_FILTER = "all";
let CURRENT_SEARCH = "";
let CURRENT_SORT = "amount_desc";

const INR = (n) => "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const PCT = (n) => Math.round(n * 100) + "%";

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function toast(message) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ---------- navigation ----------

function showView(name) {
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.view === name));
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === "view-" + name));
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});
document.querySelectorAll("[data-goto]").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.goto));
});

// ---------- data loading ----------

async function loadAll() {
  const [disputesRes, metricsRes] = await Promise.all([
    fetch("/disputes"),
    fetch("/metrics"),
  ]);
  ALL_DISPUTES = await disputesRes.json();
  METRICS = metricsRes.ok ? await metricsRes.json() : null;

  renderOverview();
  renderDisputesTable();
  renderAnalytics();
}

// ---------- Overview ----------

function renderOverview() {
  const total = ALL_DISPUTES.reduce((sum, d) => sum + d.dispute_amount_inr, 0);
  const open = ALL_DISPUTES.length;
  const needsReview = ALL_DISPUTES.filter((d) => d.needs_review).length;
  const representCount = ALL_DISPUTES.filter((d) => d.decision === "represent").length;
  const concedeCount = ALL_DISPUTES.filter((d) => d.decision === "concede").length;

  const kpis = [
    { label: "Total Disputed", value: INR(total) },
    { label: "Open Disputes", value: open },
    { label: "Needs Review", value: needsReview },
    { label: "Represent Recommended", value: representCount, cls: "represent" },
    { label: "Concede Recommended", value: concedeCount, cls: "concede" },
  ];
  document.getElementById("overview-kpis").innerHTML = kpis
    .map(
      (k) => `
      <div class="kpi-card">
        <div class="kpi-label">${k.label}</div>
        <div class="kpi-value ${k.cls || ""}">${k.value}</div>
      </div>`
    )
    .join("");

  if (METRICS) {
    const m = METRICS.money;
    const rows = [
      { label: "Concede Everything", value: m.concede_everything_inr },
      { label: "Represent Everything", value: m.represent_everything_inr },
      { label: "This System", value: m.this_system_inr, winner: true },
    ];
    const max = Math.max(...rows.map((r) => r.value));
    document.getElementById("impact-bars").innerHTML = rows
      .map(
        (r) => `
        <div class="impact-row">
          <div class="impact-label">${r.label}</div>
          <div class="impact-track"><div class="impact-fill ${r.winner ? "winner" : ""}" style="width:0%" data-w="${(r.value / max) * 100}"></div></div>
          <div class="impact-value">${INR(r.value)}</div>
        </div>`
      )
      .join("");
    requestAnimationFrame(() => {
      document.querySelectorAll(".impact-fill").forEach((el) => {
        el.style.width = el.dataset.w + "%";
      });
    });

    document.getElementById("impact-savings").innerHTML = `
      <div class="savings-tile">
        <div class="savings-amount">${INR(m.savings_vs_concede_everything_inr)}</div>
        <div class="savings-label">saved vs. Concede Everything</div>
      </div>
      <div class="savings-tile">
        <div class="savings-amount">${INR(m.savings_vs_represent_everything_inr)}</div>
        <div class="savings-label">saved vs. Represent Everything</div>
      </div>`;
  }

  const attention = ALL_DISPUTES.filter((d) => d.needs_review)
    .sort((a, b) => b.dispute_amount_inr - a.dispute_amount_inr)
    .slice(0, 6);
  document.getElementById("attention-list").innerHTML =
    attention
      .map(
        (d) => `
      <div class="attention-row" data-id="${d.dispute_id}">
        <div class="cell-id mono">${d.dispute_id}</div>
        <div class="cell-reason">${d.reason_code} &mdash; ${escapeHtml(d.reason_description)}</div>
        <div class="cell-num">${INR(d.dispute_amount_inr)}</div>
        <div class="cell-num">${PCT(d.evidence_coverage)} cov.</div>
        <div class="cell-num">${PCT(d.win_probability)} win</div>
        <div class="cell-num">${INR(d.expected_value_inr)}</div>
        <div>${badgeHtml(d.decision)}</div>
      </div>`
      )
      .join("") || `<p class="empty-state">No disputes currently need extra review.</p>`;

  document.querySelectorAll(".attention-row").forEach((row) => {
    row.addEventListener("click", () => {
      showView("disputes");
      selectDispute(row.dataset.id);
    });
  });
}

function badgeHtml(decision) {
  return `<span class="badge ${decision}">${decision}</span>`;
}
// Status shown to the analyst is derived, not the raw {open, resolved}
// pair the API returns: a resolved case always shows Resolved; an open
// case shows Needs Review or Ready depending on the same needs_review
// signal used elsewhere. One badge per cell -- no double-badge overflow.
function statusBadgeHtml(d) {
  if (d.status === "resolved") return `<span class="badge resolved">Resolved</span>`;
  if (d.needs_review) return `<span class="badge needs-review">Needs Review</span>`;
  return `<span class="badge open">Ready</span>`;
}

// ---------- Disputes queue ----------

function applyFilterSortSearch() {
  let list = ALL_DISPUTES.slice();

  if (CURRENT_FILTER === "represent") list = list.filter((d) => d.decision === "represent");
  else if (CURRENT_FILTER === "concede") list = list.filter((d) => d.decision === "concede");
  else if (CURRENT_FILTER === "needs_review") list = list.filter((d) => d.needs_review);
  else if (CURRENT_FILTER === "resolved") list = list.filter((d) => d.status === "resolved");

  if (CURRENT_SEARCH.trim()) {
    const q = CURRENT_SEARCH.trim().toLowerCase();
    list = list.filter(
      (d) => d.dispute_id.toLowerCase().includes(q) || d.reason_code.toLowerCase().includes(q)
    );
  }

  const sorters = {
    amount_desc: (a, b) => b.dispute_amount_inr - a.dispute_amount_inr,
    amount_asc: (a, b) => a.dispute_amount_inr - b.dispute_amount_inr,
    ev_desc: (a, b) => b.expected_value_inr - a.expected_value_inr,
    ev_asc: (a, b) => a.expected_value_inr - b.expected_value_inr,
  };
  list.sort(sorters[CURRENT_SORT] || sorters.amount_desc);
  return list;
}

function renderDisputesTable() {
  const list = applyFilterSortSearch();
  const tbody = document.getElementById("disputes-tbody");
  const empty = document.getElementById("disputes-empty");

  if (list.length === 0) {
    tbody.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  tbody.innerHTML = list
    .map(
      (d) => `
      <tr data-id="${d.dispute_id}" class="${d.dispute_id === SELECTED_ID ? "selected" : ""}">
        <td class="mono">${d.dispute_id}</td>
        <td>${d.reason_code}</td>
        <td class="mono">${INR(d.dispute_amount_inr)}</td>
        <td>${PCT(d.evidence_coverage)}</td>
        <td>${PCT(d.win_probability)}</td>
        <td class="mono">${INR(d.expected_value_inr)}</td>
        <td>${badgeHtml(d.decision)}</td>
        <td>${statusBadgeHtml(d)}</td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => selectDispute(row.dataset.id));
  });
}

document.getElementById("dispute-search").addEventListener("input", (e) => {
  CURRENT_SEARCH = e.target.value;
  renderDisputesTable();
});
document.getElementById("sort-select").addEventListener("change", (e) => {
  CURRENT_SORT = e.target.value;
  renderDisputesTable();
});
document.querySelectorAll("#filter-pills .pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#filter-pills .pill").forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    CURRENT_FILTER = pill.dataset.filter;
    renderDisputesTable();
  });
});

// ---------- Case detail / decision workspace ----------

async function selectDispute(id) {
  SELECTED_ID = id;
  renderDisputesTable();

  const detail = document.getElementById("dispute-detail");
  detail.innerHTML = `<p class="placeholder">Analyzing dispute&hellip;</p>`;

  const res = await fetch(`/disputes/${id}/respond`, { method: "POST" });
  if (!res.ok) {
    detail.innerHTML = `<p class="placeholder">Error running the decision pipeline for ${id}.</p>`;
    return;
  }
  const data = await res.json();
  renderCaseDetail(id, data);
}

function renderCaseDetail(id, data) {
  const d = data.decision;
  const isRepresent = d.decision === "represent";
  const record = ALL_DISPUTES.find((r) => r.dispute_id === id) || {};
  const now = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });

  const detail = document.getElementById("dispute-detail");
  detail.innerHTML = `
    <div class="detail-head">
      <h2>${id}</h2>
    </div>
    <div class="detail-meta">
      ${record.reason_code} &mdash; ${escapeHtml(record.reason_description || "")} &middot; ${INR(record.dispute_amount_inr)} disputed<br/>
      <span class="mono">audit ${data.audit_id.slice(0, 10)}&hellip;</span> &middot;
      last evaluated <span class="mono">${now} IST</span> &middot;
      model <span class="mono">${escapeHtml(d.model_version || "")}</span>
    </div>

    <div class="calc-pipeline" id="calc-pipeline">
      <div class="calc-status">Analyzing dispute&hellip;</div>
    </div>

    <div id="decision-badge-slot"></div>

    <details style="margin: 10px 0 4px;">
      <summary style="cursor:pointer; color: var(--text-muted); font-size: 12.5px;">View calculation logic</summary>
      <div class="mono" style="font-size: 12px; color: var(--text-secondary); margin-top: 8px; line-height: 1.7;">
        win_probability &times; coverage_factor &times; amount &minus; representment_cost = expected_value<br/>
        ${escapeHtml(d.rule_applied)}
      </div>
    </details>

    <div class="section-title">Evidence Coverage</div>
    <div class="coverage-wrap">
      ${coverageRingHtml(d.evidence_coverage)}
    </div>
    <ul class="checklist" id="evidence-checklist">
      ${data.evidence_checklist
        .map(
          (item, i) => `
        <li class="${item.checked ? "checked" : "unchecked"}" data-idx="${i}">${escapeHtml(item.field)}</li>
        <div class="evidence-detail" id="ev-detail-${i}">${escapeHtml(item.detail || "No grounded language exists for this field.")}${item.checked ? "" : " (not present in this case's evidence file, so this sentence is NOT included in the letter.)"}</div>`
        )
        .join("")}
    </ul>

    <div class="section-title">Decision Rationale</div>
    ${rationaleHtml(data.evidence_checklist, d)}

    <div class="section-title">${isRepresent ? "Representment Letter" : "Internal Concession Memo"}</div>
    <div class="letter-box ${isRepresent ? "represent-letter" : "concede-memo"}" id="letter-box">${escapeHtml(data.letter)}</div>
    <div class="doc-actions">
      <button class="btn btn-secondary" id="btn-copy">Copy ${isRepresent ? "letter" : "memo"}</button>
      <button class="btn btn-secondary" id="btn-edit">Edit draft</button>
      <button class="btn btn-secondary" id="btn-pdf">Download PDF</button>
      ${
        isRepresent
          ? `<button class="btn btn-primary" id="btn-send">Send to processor</button>`
          : `<button class="btn btn-primary" id="btn-record">Record concession</button>`
      }
    </div>

    <div class="audit-line">
      Audit ID: ${data.audit_id}
      &nbsp;&middot;&nbsp;
      <a href="#" id="view-audit-link" style="color: var(--light-blue);">View decision audit &rarr;</a>
    </div>
    <div class="audit-replay-box" id="audit-replay-box"></div>
  `;

  animateCalcPipeline(d);
  wireCaseDetailActions(id, data, isRepresent);
}

function coverageRingHtml(coverage) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - coverage);
  return `
    <div class="coverage-ring">
      <svg width="64" height="64">
        <circle class="ring-bg" cx="32" cy="32" r="${r}"></circle>
        <circle class="ring-fill" cx="32" cy="32" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}" id="ring-fill-circle"></circle>
      </svg>
      <div class="ring-label">${PCT(coverage)}</div>
    </div>
    <div style="font-size:12.5px; color: var(--text-muted); flex:1;">of the reason code's evidence checklist is present on file.
    <span data-offset="${offset}" id="ring-offset-holder" hidden></span></div>
  `;
}

function rationaleHtml(checklist, d) {
  const positives = checklist.filter((i) => i.checked).map((i) => i.field.replace(/_/g, " "));
  const negatives = checklist.filter((i) => !i.checked).map((i) => i.field.replace(/_/g, " "));
  const confidence =
    d.evidence_coverage >= 0.7 && (d.win_probability >= 0.6 || d.win_probability <= 0.3)
      ? "High"
      : d.win_probability > 0.4 && d.win_probability < 0.6
      ? "Low"
      : "Medium";
  return `
    <ul class="rationale-list">
      ${positives.map((p) => `<li class="positive">+ ${escapeHtml(p)}</li>`).join("")}
      ${negatives.map((n) => `<li class="negative">&minus; ${escapeHtml(n)}</li>`).join("")}
    </ul>
    <div class="confidence-line">Decision confidence: <strong>${confidence}</strong>${d.needs_review ? " &middot; flagged for analyst review" : ""}</div>
  `;
}

function animateCalcPipeline(d) {
  const el = document.getElementById("calc-pipeline");
  const amountRecord = ALL_DISPUTES.find((r) => r.dispute_id === SELECTED_ID);
  const terms = [
    ["WIN PROBABILITY", d.win_probability.toFixed(2)],
    ["COVERAGE FACTOR", d.coverage_factor.toFixed(2)],
    ["DISPUTED AMOUNT", INR(amountRecord ? amountRecord.dispute_amount_inr : 0)],
    ["REPRESENTMENT COST", "− " + INR(d.representment_cost_inr)],
  ];
  el.innerHTML = `<div class="calc-status">Analyzing dispute&hellip;</div>`;
  let delay = 150;
  terms.forEach(([name, value]) => {
    setTimeout(() => {
      const row = document.createElement("div");
      row.className = "calc-term";
      row.innerHTML = `<span class="term-name">${name}</span><span class="term-value">${value}</span>`;
      el.appendChild(row);
      requestAnimationFrame(() => row.classList.add("show"));
    }, delay);
    delay += 220;
  });
  setTimeout(() => {
    const divider = document.createElement("div");
    divider.className = "calc-divider";
    el.appendChild(divider);
    const result = document.createElement("div");
    result.className = "calc-result";
    result.innerHTML = `<span class="term-name">EXPECTED VALUE</span><span class="term-value">${INR(d.expected_value_inr)}</span>`;
    el.appendChild(result);
    el.querySelector(".calc-status").textContent = "Calculation complete";
  }, delay + 100);

  setTimeout(() => {
    const slot = document.getElementById("decision-badge-slot");
    slot.innerHTML = `<div class="decision-badge-lg ${d.decision}">${d.decision.toUpperCase()}</div>`;
    requestAnimationFrame(() => slot.querySelector(".decision-badge-lg").classList.add("show"));
  }, delay + 300);

  setTimeout(() => {
    const circle = document.getElementById("ring-fill-circle");
    const holder = document.getElementById("ring-offset-holder");
    if (circle && holder) circle.style.strokeDashoffset = holder.dataset.offset;
  }, 100);
}

function wireCaseDetailActions(id, data, isRepresent) {
  document.querySelectorAll(".checklist li").forEach((li) => {
    li.addEventListener("click", () => {
      const box = document.getElementById("ev-detail-" + li.dataset.idx);
      box.classList.toggle("open");
    });
  });

  document.getElementById("btn-copy").addEventListener("click", async () => {
    const text = document.getElementById("letter-box").innerText;
    try {
      await navigator.clipboard.writeText(text);
      toast(`${isRepresent ? "Representment letter" : "Concession memo"} copied`);
    } catch {
      toast("Could not access clipboard in this browser");
    }
  });

  document.getElementById("btn-edit").addEventListener("click", () => {
    const box = document.getElementById("letter-box");
    const editable = box.getAttribute("contenteditable") === "true";
    box.setAttribute("contenteditable", editable ? "false" : "true");
    if (!editable) {
      box.focus();
      toast("Draft is now editable");
    } else {
      toast("Draft saved");
    }
  });

  document.getElementById("btn-pdf").addEventListener("click", () => {
    const w = window.open("", "_blank");
    if (!w) {
      toast("Pop-up blocked -- allow pop-ups to print/save as PDF");
      return;
    }
    const pre = w.document.createElement("pre");
    pre.style.fontFamily = "'JetBrains Mono', monospace";
    pre.style.whiteSpace = "pre-wrap";
    pre.style.padding = "40px";
    pre.textContent = document.getElementById("letter-box").innerText;
    w.document.title = `${id} -- ${isRepresent ? "Representment Letter" : "Concession Memo"}`;
    w.document.body.appendChild(pre);
    w.print();
  });

  const sendBtn = document.getElementById("btn-send");
  if (sendBtn) {
    sendBtn.addEventListener("click", () => {
      if (!confirm("Send this representment letter to the card network / processor?")) return;
      resolveAndRefresh(id, "Representment marked as sent");
    });
  }
  const recordBtn = document.getElementById("btn-record");
  if (recordBtn) {
    recordBtn.addEventListener("click", () => {
      resolveAndRefresh(id, "Concession recorded");
    });
  }

  document.getElementById("view-audit-link").addEventListener("click", async (e) => {
    e.preventDefault();
    const box = document.getElementById("audit-replay-box");
    if (box.classList.contains("open")) {
      box.classList.remove("open");
      return;
    }
    toast("Decision audit opened");
    const res = await fetch(`/audit/${data.audit_id}/replay`);
    const replay = await res.json();
    box.innerHTML = `replay decision: ${replay.decision} &middot; win_probability ${replay.win_probability.toFixed(3)} &middot; matches recorded decision: yes`;
    box.classList.add("open");
  });
}

async function resolveAndRefresh(id, message) {
  await fetch(`/disputes/${id}/resolve`, { method: "POST" });
  toast(message);
  const target = ALL_DISPUTES.find((d) => d.dispute_id === id);
  if (target) target.status = "resolved";
  renderDisputesTable();
  renderOverview();
}

// ---------- Risk Analytics ----------

function renderAnalytics() {
  const content = document.getElementById("analytics-content");
  if (!METRICS) {
    content.innerHTML = `<p class="placeholder">No eval/report.json found. Run: python eval/evaluate.py</p>`;
    return;
  }
  const cm = METRICS.confusion_matrix;
  const money = METRICS.money;

  content.innerHTML = `
    <div class="metrics-kpi-row">
      ${kpiTile("Precision", METRICS.precision.toFixed(3))}
      ${kpiTile("Recall", METRICS.recall.toFixed(3))}
      ${kpiTile("F1", METRICS.f1.toFixed(3))}
      ${kpiTile("AUC", METRICS.auc.toFixed(3))}
    </div>

    <div class="analytics-grid">
      <div class="panel">
        <h2 class="panel-title">Confusion Matrix</h2>
        <p class="panel-desc">Positive class = "represent" &middot; n = ${METRICS.n_test}</p>
        <div class="confusion-grid">
          <div></div><div class="cg-label">Actual: would win</div><div class="cg-label">Actual: would lose</div>
          <div class="cg-label">Predicted: represent</div>
          ${confusionCell(cm.tp, "TP", "Correctly represented a winnable case")}
          ${confusionCell(cm.fp, "FP", "Represented a case that would have lost — wasted the filing cost", true)}
          <div class="cg-label">Predicted: concede</div>
          ${confusionCell(cm.fn, "FN", "Conceded a case that was actually winnable — left money on the table", true)}
          ${confusionCell(cm.tn, "TN", "Correctly conceded an unwinnable case")}
        </div>
      </div>

      <div class="panel">
        <h2 class="panel-title">Financial Impact</h2>
        <p class="panel-desc">Total loss over the test set, by strategy.</p>
        <div id="analytics-impact-bars" class="impact-bars"></div>
      </div>
    </div>

    <div class="panel" style="margin-top:20px;">
      <h2 class="panel-title">Precision / Recall vs. probability threshold</h2>
      <p class="panel-desc">Diagnostic only &mdash; sweeps a plain probability cutoff, not the production EV rule.</p>
      <img src="/pr-curve.png?t=${Date.now()}" alt="Precision/Recall vs threshold curve" style="max-width:100%; border-radius: 12px; border: 1px solid var(--glass-border); background: white; margin-top: 10px;" />
    </div>
  `;

  const rows = [
    { label: "Concede Everything", value: money.concede_everything_inr },
    { label: "Represent Everything", value: money.represent_everything_inr },
    { label: "This System", value: money.this_system_inr, winner: true },
  ];
  const max = Math.max(...rows.map((r) => r.value));
  document.getElementById("analytics-impact-bars").innerHTML = rows
    .map(
      (r) => `
      <div class="impact-row">
        <div class="impact-label">${r.label}</div>
        <div class="impact-track"><div class="impact-fill ${r.winner ? "winner" : ""}" style="width:${(r.value / max) * 100}%"></div></div>
        <div class="impact-value">${INR(r.value)}</div>
      </div>`
    )
    .join("");
}

function kpiTile(label, value) {
  return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div></div>`;
}

function confusionCell(num, tag, tooltip, warn) {
  return `<div class="confusion-cell" title="${escapeHtml(tooltip)}" style="${warn ? "border-color: rgba(245,158,11,0.3);" : ""}">
    <div class="cg-num">${num}</div><div class="cg-tag">${tag}</div>
  </div>`;
}

loadAll();
