const API_BASE = "https://sih-gem-compliance.onrender.com";

let state = {
evaluation: null,
evidence: [],
rules: [],
edges: [],
ledger: [],
auditId: "GEMA-SIH-001"
};

/* =========================================================
BASIC HELPERS
========================================================= */

const $ = (id) => document.getElementById(id);

function showLoading(show = true) {
$("loadingBar").classList.toggle("hidden", !show);
}

function toast(message) {
$("toastMessage").textContent = message;
$("toast").classList.add("show");

setTimeout(() => {
    $("toast").classList.remove("show");
}, 2500);

}

async function api(path, options = {}) {

showLoading(true);

try {

    // FormData (file uploads) must NOT get a manual Content-Type — the
    // browser sets its own with the correct multipart boundary. Forcing
    // application/json here would silently break every upload.
    const isFormData = options.body instanceof FormData;

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            ...(isFormData ? {} : { "Content-Type": "application/json" }),
            ...(options.headers || {})
        }
    });

    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const errBody = await response.json();
            detail = errBody.detail || detail;
        } catch {}
        throw new Error(detail);
    }

    return await response.json();

} finally {
    showLoading(false);
}

}

/* =========================================================
NAVIGATION
========================================================= */

document.querySelectorAll(".nav-item").forEach(button => {

button.addEventListener("click", () => {

    const target = button.dataset.section;

    document.querySelectorAll(".nav-item")
        .forEach(item => item.classList.remove("active"));

    button.classList.add("active");

    document.querySelectorAll(".page-section")
        .forEach(section => section.classList.remove("active"));

    $(target).classList.add("active");

    if (target === "bidders") {
        loadBidderComparison();
    }

});

});

document.querySelectorAll("[data-section-target]").forEach(button => {

button.addEventListener("click", () => {

    const target = button.dataset.sectionTarget;

    document.querySelector(`[data-section="${target}"]`).click();

});

});

/* =========================================================
DOCUMENT INGESTION
========================================================= */

let ingestState = {
    tenderFile: null,
    bidderFiles: []
};

function setupDropzone(dropzoneId, inputId, onFiles) {

    const dropzone = $(dropzoneId);
    const input = $(inputId);

    input.addEventListener("change", (e) => {
        onFiles(Array.from(e.target.files));
        input.value = ""; // allow re-selecting the same file after removal
    });

    ["dragover", "dragenter"].forEach(evt =>
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        })
    );

    ["dragleave", "drop"].forEach(evt =>
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
        })
    );

    dropzone.addEventListener("drop", (e) => {
        const files = Array.from(e.dataTransfer.files || []);
        if (files.length) onFiles(files);
    });
}

setupDropzone("tenderDropzone", "tenderInput", (files) => {
    ingestState.tenderFile = files[0] || null;
    renderIngestChips();
});

setupDropzone("bidderDropzone", "bidderInput", (files) => {
    ingestState.bidderFiles = ingestState.bidderFiles.concat(files);
    renderIngestChips();
});

window.removeTenderFile = function () {
    ingestState.tenderFile = null;
    renderIngestChips();
};

window.removeBidderFile = function (index) {
    ingestState.bidderFiles.splice(index, 1);
    renderIngestChips();
};

function renderIngestChips() {

    const tenderChip = $("tenderChip");
    tenderChip.innerHTML = ingestState.tenderFile
        ? fileChipHtml(ingestState.tenderFile.name, "removeTenderFile()")
        : "";

    const bidderChips = $("bidderChips");
    bidderChips.innerHTML = ingestState.bidderFiles
        .map((f, i) => fileChipHtml(f.name, `removeBidderFile(${i})`))
        .join("");

    $("ingestButton").disabled = ingestState.bidderFiles.length === 0;
}

function fileChipHtml(name, onRemove) {
    return `
        <span class="file-chip">
            ${escapeHtml(name)}
            <button onclick="${onRemove}">&times;</button>
        </span>
    `;
}

$("ingestButton").addEventListener("click", async () => {

    const errorBox = $("ingestError");
    const summaryBox = $("ingestSummary");
    errorBox.classList.add("hidden");
    summaryBox.classList.add("hidden");

    if (ingestState.bidderFiles.length === 0) {
        errorBox.textContent = "Add at least one bidder document first.";
        errorBox.classList.remove("hidden");
        return;
    }

    const formData = new FormData();
    ingestState.bidderFiles.forEach(f => formData.append("bidder_files", f));
    if (ingestState.tenderFile) formData.append("tender_file", ingestState.tenderFile);
    const label = $("bidderLabelInput").value.trim();
    if (label) formData.append("bidder_label", label);

    try {

        const result = await api("/api/v3/ingest-documents", {
            method: "POST",
            body: formData
        });

        summaryBox.innerHTML = `
            <strong>${escapeHtml(result.bidder_label)}</strong> —
            <strong>${result.evidence_count}</strong> evidence facts extracted from
            <strong>${result.documents_processed.length}</strong> document(s),
            <strong>${result.rule_count}</strong> requirement(s)
            ${result.tender_rules_reused ? "reused from the current tender" : "compiled"}.
            Decision: <strong>${escapeHtml(result.compliance.decision)}</strong>
            (${result.compliance.compliance_score.toFixed(1)}/100).
        `;
        summaryBox.classList.remove("hidden");

        toast(`${result.bidder_label} processed — knowledge graph updated.`);

        ingestState = { tenderFile: null, bidderFiles: [] };
        renderIngestChips();
        $("bidderLabelInput").value = "";

        await loadBackendState();
        await loadBidderComparison();
        await loadTenderStatus();

        // Jump straight to Overview so the officer sees the result,
        // instead of leaving them on the now-empty ingest form.
        document.querySelector('[data-section="overview"]').click();

    } catch (error) {

        errorBox.textContent = `Extraction failed: ${error.message}`;
        errorBox.classList.remove("hidden");
    }

});

async function loadTenderStatus() {

    try {

        const info = await api("/api/v3/tender/current");
        const box = $("tenderStatus");

        if (!info.tender_filename) {
            box.classList.add("hidden");
            return;
        }

        box.innerHTML = `
            Active tender: <strong>${escapeHtml(info.tender_filename)}</strong>
            (${info.rule_count} requirement(s) compiled) —
            new bidders reuse these automatically.
            <button class="text-button" onclick="resetTender()">Start a different tender</button>
        `;
        box.classList.remove("hidden");

    } catch (error) {

        console.warn("Could not load tender status.", error);
    }
}

window.resetTender = async function () {

    try {

        await api("/api/v3/tender/reset", { method: "POST" });
        toast("Tender cleared — next upload with a tender file compiles a fresh ruleset.");
        await loadTenderStatus();

    } catch (error) {

        toast(`Could not reset tender: ${error.message}`);
    }
};

/* =========================================================
OVERVIEW
========================================================= */

function renderOverview() {

if (!state.evaluation) return;

const result = state.evaluation;

const score = Number(result.compliance_score || 0);

$("complianceScore").textContent = score.toFixed(2);

const decision = result.decision || "REVIEW";

const badge = $("decisionBadge");

badge.textContent = decision;
badge.className = `decision-badge ${decision.toLowerCase()}`;

$("mandatoryFailureCount").textContent =
    result.mandatory_failures?.length || 0;

$("reviewCount").textContent =
    result.review_triggers?.length || 0;

$("queueCount").textContent =
    result.review_triggers?.length || 0;


if (decision === "PASS") {

    $("decisionTitle").textContent = "Compliance Requirements Satisfied";

    $("decisionDescription").textContent =
        "All evaluated mandatory requirements have passed.";

} else if (decision === "FAIL") {

    $("decisionTitle").textContent = "Mandatory Requirement Failure";

    $("decisionDescription").textContent =
        "At least one mandatory procurement requirement failed.";

} else {

    $("decisionTitle").textContent = "Human Review Required";

    $("decisionDescription").textContent =
        "Evidence or rule dependencies require officer review.";
}


/* Score Ring */

const degrees = Math.max(0, Math.min(100, score)) * 3.6;

$("complianceScore")
    .parentElement
    .parentElement
    .style.background =
    `conic-gradient(#2563eb ${degrees}deg, #e2e8f0 ${degrees}deg)`;


/* Mandatory failures */

const failures = result.mandatory_failures || [];

if (!failures.length) {

    $("mandatoryFailures").innerHTML =
        `<div class="empty-state">
            No mandatory failures detected.
        </div>`;

} else {

    $("mandatoryFailures").innerHTML =
        failures.map(id => `
            <div class="failure-item">
                <strong>${escapeHtml(id)}</strong>
                <span>Mandatory procurement rule failed.</span>
            </div>
        `).join("");
}


/* Reviews */

const reviews = result.review_triggers || [];

if (!reviews.length) {

    $("reviewQueue").innerHTML =
        `<div class="empty-state">
            No review triggers.
        </div>`;

} else {

    $("reviewQueue").innerHTML =
        reviews.map(id => {

            const evaluation = state.ruleEvaluations?.[id];

            const reason = evaluation?.reasoning
                || "Evidence state requires human review.";

            return `
                <div class="review-item clickable" onclick="jumpToReviewItem('${escapeJs(id)}')">
                    <strong>${escapeHtml(id)}</strong>
                    <span>${escapeHtml(reason)}</span>
                </div>
            `;
        }).join("");
}

}

/* =========================================================
EVIDENCE GRAPH
========================================================= */

let evidenceNetwork = null;

const EVIDENCE_STATUS_COLOR = {
    VERIFIED: "#16a34a",
    OFFICER_CONFIRMED: "#16a34a",
    CONFLICTING: "#dc2626",
    EXPIRED: "#9ca3af",
    UNVERIFIED: "#f59e0b",
    REJECTED: "#9ca3af"
};

const RULE_STATUS_COLOR = { PASS: "#16a34a", FAIL: "#dc2626", REVIEW: "#f59e0b" };

function renderEvidenceGraph() {

const container = $("graphContainer");

if (!state.evidence.length && !state.rules.length) {
    container.innerHTML = `<div class="empty-state">Evidence graph will appear after ingestion.</div>`;
    populateBlastSelector();
    return;
}

if (typeof vis === "undefined") {
    renderEvidenceGraphAsList(container);
    populateBlastSelector();
    return;
}

if (evidenceNetwork) {
    evidenceNetwork.destroy();
    evidenceNetwork = null;
}

const nodes = new vis.DataSet([
    ...state.evidence.map(n => ({
        id: n.node_id,
        label: `${n.node_id}\n${n.entity_name}`,
        shape: "dot",
        size: 14,
        color: EVIDENCE_STATUS_COLOR[n.status] || "#94a3b8",
        font: { size: 10, face: "JetBrains Mono", color: "#334155" }
    })),
    ...state.rules.map(r => ({
        id: r.rule_id,
        label: r.rule_id,
        shape: "box",
        color: RULE_STATUS_COLOR[state.ruleStatuses?.[r.rule_id]] || "#94a3b8",
        font: { size: 10, face: "JetBrains Mono", color: "#ffffff" }
    }))
]);

const edges = new vis.DataSet(
    state.edges.map(e => ({
        from: e.source_id,
        to: e.target_id,
        arrows: "to",
        dashes: e.relationship === "RULE_DEPENDENCY",
        color: { color: e.relationship === "RULE_DEPENDENCY" ? "#2563eb" : "#cbd5e1" }
    }))
);

evidenceNetwork = new vis.Network(container, { nodes, edges }, {
    physics: { stabilization: true, barnesHut: { gravitationalConstant: -3500, springLength: 100 } },
    interaction: { hover: true, tooltipDelay: 150 },
    edges: { smooth: { type: "continuous" } }
});

evidenceNetwork.on("click", (params) => {
    if (!params.nodes.length) return;
    const clicked = params.nodes[0];
    if (state.evidence.some(n => n.node_id === clicked)) {
        selectEvidence(clicked);
    }
});

populateBlastSelector();

}

// Same information as the graph, as plain rows — used only if the CDN
// graph library can't load (e.g. no internet at the venue).
function renderEvidenceGraphAsList(container) {

container.innerHTML = state.evidence.map(node => {

    const status = node.status || "UNVERIFIED";

    return `
        <div class="graph-row">
            <div class="graph-node" onclick="selectEvidence('${escapeJs(node.node_id)}')">
                <div class="node-type">EVIDENCE NODE</div>
                <strong><span class="node-status ${status.toLowerCase()}"></span> ${escapeHtml(node.node_id)}</strong>
                <small>${escapeHtml(node.entity_name)}</small>
                <small>Value: ${escapeHtml(String(node.extracted_value))}</small>
            </div>
            <div class="graph-arrow">→</div>
            <div class="graph-node">
                <div class="node-type">SOURCE</div>
                <strong>${escapeHtml(node.source_doc)}</strong>
                <small>Confidence ${Number(node.confidence || 0).toFixed(2)}</small>
            </div>
        </div>
    `;
}).join("");

}

window.selectEvidence = function(nodeId) {

const node = state.evidence.find(
    n => n.node_id === nodeId
);

if (!node) return;

$("selectedNodeTitle").textContent =
    `Evidence Node ${node.node_id}`;

$("nodeDetailsContent").innerHTML = `

    <div class="detail-row">
        <label>ENTITY</label>
        <strong>${escapeHtml(node.entity_name)}</strong>
    </div>

    <div class="detail-row">
        <label>EXTRACTED VALUE</label>
        <strong>${escapeHtml(String(node.extracted_value))}</strong>
    </div>

    <div class="detail-row">
        <label>STATUS</label>
        <strong>${escapeHtml(node.status || "UNVERIFIED")}</strong>
    </div>

    <div class="detail-row">
        <label>CONFIDENCE</label>
        <strong>${Number(node.confidence || 0).toFixed(3)}</strong>
    </div>

    <div class="detail-row">
        <label>SOURCE DOCUMENT</label>
        <strong>${escapeHtml(node.source_doc)}</strong>
    </div>

    <div class="detail-row">
        <label>VALID UNTIL</label>
        <strong>${node.valid_until || "No expiry specified"}</strong>
    </div>

    ${node.source_quote ? `
        <div class="source-quote">
            "${escapeHtml(node.source_quote)}"
            <br><small>— ${escapeHtml(node.source_doc)}${node.page_number ? `, page ${node.page_number}` : ""}</small>
        </div>
    ` : ""}

    <button
        class="primary-button full"
        onclick="analyzeBlast('${escapeJs(node.node_id)}')"
    >
        Analyze Blast Radius
    </button>

    <div class="form-group">
        <label>OFFICER CORRECTION</label>
        <input
            id="overrideValue-${escapeJs(node.node_id)}"
            type="text"
            placeholder="Corrected value"
        >
    </div>

    <button
        class="primary-button full"
        onclick="submitOverride('${escapeJs(node.node_id)}')"
    >
        Submit Correction
    </button>
`;

};

/* =========================================================
OFFICER ACTIONS — corrections + review resolution
========================================================= */

function coerceValue(raw) {
    if (raw !== "" && !isNaN(raw)) {
        return raw.includes(".") ? parseFloat(raw) : parseInt(raw, 10);
    }
    return raw;
}

function actorName() {
    return document.getElementById("actorNameInput")?.value.trim()
        || "Procurement Officer";
}

window.submitOverride = async function (nodeId) {

    const input = document.getElementById(`overrideValue-${nodeId}`);
    const raw = input.value.trim();

    if (!raw) {
        toast("Enter a corrected value first.");
        return;
    }

    const beforeStatuses = { ...(state.ruleStatuses || {}) };
    const beforeScore = state.evaluation?.compliance_score;
    const beforeDecision = state.evaluation?.decision;

    try {

        const result = await api("/api/v3/officer-override", {
            method: "POST",
            body: JSON.stringify({
                node_id: nodeId,
                new_value: coerceValue(raw),
                actor: actorName()
            })
        });

        const impact = result.impact_analysis;

        await loadBackendState();
        selectEvidence(nodeId);

        renderDiffPanel({
            title: `${nodeId} corrected to "${raw}"`,
            oldScore: impact.old_score ?? beforeScore,
            newScore: impact.new_score,
            oldDecision: impact.old_decision ?? beforeDecision,
            newDecision: impact.new_decision,
            affectedRules: impact.affected_rules || [],
            beforeStatuses,
        });

    } catch (error) {

        toast(`Correction failed: ${error.message}`);
    }
};

function renderDiffPanel({ title, oldScore, newScore, oldDecision, newDecision, affectedRules, beforeStatuses }) {

    const panel = $("diffPanel");

    if (!affectedRules.length) {
        panel.innerHTML = `
            <div class="diff-header"><strong>${escapeHtml(title)}</strong></div>
            <div class="empty-state">No rules were affected by this change.</div>
        `;
        panel.classList.remove("hidden");
        return;
    }

    const rows = affectedRules.map(ruleId => {
        const before = beforeStatuses[ruleId] || "REVIEW";
        const after = state.ruleStatuses?.[ruleId] || "REVIEW";
        const rule = state.rules.find(r => r.rule_id === ruleId);
        return `
            <div class="diff-row">
                <span class="rule-id">${escapeHtml(ruleId)}</span>
                <span class="status-pill ${before}">${before}</span>
                <span>\u2192</span>
                <span class="status-pill ${after}">${after}</span>
                <span>${rule ? escapeHtml(rule.clause_text) : ""}</span>
            </div>
        `;
    }).join("");

    panel.innerHTML = `
        <div class="diff-header">
            <strong>${escapeHtml(title)}</strong>
            <span>Score ${Number(oldScore ?? 0).toFixed(1)} \u2192 ${Number(newScore ?? 0).toFixed(1)}
                &nbsp;\u00B7&nbsp; ${escapeHtml(oldDecision || "")} \u2192 ${escapeHtml(newDecision || "")}</span>
        </div>
        ${rows}
    `;
    panel.classList.remove("hidden");
}

const OP_LABEL = {
    ">=": "\u2265", ">": ">", "<=": "\u2264", "<": "<",
    "==": "must equal", "!=": "must not equal", "EXISTS": "must be present",
    "DATE_AFTER": "must be after", "DATE_BEFORE": "must be before",
};

function renderRequiredVsVerified(rule, node, status) {

    const opLabel = OP_LABEL[rule.ast.op] || rule.ast.op;
    const requiredText = rule.ast.op === "EXISTS" ? "Must be present" : `${opLabel} ${rule.ast.value}`;

    $("nodeDetailsContent").innerHTML = `

        <div class="compare-row">
            <div class="compare-box">
                <label>REQUIRED</label>
                <strong>${escapeHtml(requiredText)}</strong>
            </div>
            <div class="compare-box">
                <label>VERIFIED</label>
                <strong>${escapeHtml(String(node.extracted_value))}</strong>
            </div>
        </div>

        <div class="detail-row">
            <label>RESULT</label>
            <span class="status-pill ${status}">${status}</span>
        </div>

        <div class="detail-row">
            <label>SOURCE</label>
            <strong>${escapeHtml(node.source_doc)}${node.page_number ? `, page ${node.page_number}` : ""}</strong>
        </div>

        ${node.source_quote ? `<div class="source-quote">"${escapeHtml(node.source_quote)}"</div>` : ""}

        <button class="primary-button full" onclick="analyzeBlast('${escapeJs(node.node_id)}')">
            Analyze Blast Radius
        </button>

        <div class="form-group">
            <label>OFFICER CORRECTION</label>
            <input id="overrideValue-${escapeJs(node.node_id)}" type="text" placeholder="Corrected value">
        </div>

        <button class="primary-button full" onclick="submitOverride('${escapeJs(node.node_id)}')">
            Submit Correction
        </button>
    `;
}

window.jumpToReviewItem = function (ruleId) {

    document.querySelector('[data-section="evidence"]').click();

    const evaluation = state.ruleEvaluations?.[ruleId];
    const rule = state.rules.find(r => r.rule_id === ruleId);
    const evidenceIds = evaluation?.evidence_ids || [];
    const status = state.ruleStatuses?.[ruleId] || "REVIEW";

    $("selectedNodeTitle").textContent = rule ? `${ruleId} — ${rule.clause_text}` : `Review: ${ruleId}`;

    if (evidenceIds.length === 0) {

        $("nodeDetailsContent").innerHTML = `
            <div class="empty-state">
                No specific evidence node is linked to this rule —
                check the Rules tab for the clause.
            </div>
        `;
        return;
    }

    // A simple requirement (not AND/OR/NOT) checked against exactly one
    // piece of evidence — this is the "why did this fail" view: required
    // value vs what was actually verified, with the source it came from.
    const isLeafComparison = rule && rule.ast && !["AND", "OR", "NOT"].includes(rule.ast.op);

    if (evidenceIds.length === 1 && isLeafComparison) {
        const node = state.evidence.find(n => n.node_id === evidenceIds[0]);
        if (node) {
            renderRequiredVsVerified(rule, node, status);
            return;
        }
    }

    if (evidenceIds.length === 1) {
        selectEvidence(evidenceIds[0]);
        return;
    }

    // Multiple sources disagree (CONFLICTING) — show them side by side
    // instead of forcing the officer to click through nodes one at a time.
    const nodes = evidenceIds
        .map(id => state.evidence.find(n => n.node_id === id))
        .filter(Boolean);

    const cardsHtml = nodes.map(n => `
        <div class="conflict-card">
            <strong>${escapeHtml(n.source_doc)}</strong>
            <span>${escapeHtml(n.entity_name)} = ${escapeHtml(String(n.extracted_value))}</span>
            <small>${escapeHtml(n.node_id)} · confidence ${Number(n.confidence || 0).toFixed(2)}</small>
        </div>
    `).join("");

    $("nodeDetailsContent").innerHTML = `
        <div class="detail-row">
            <label>WHY THIS NEEDS REVIEW</label>
            <strong>${escapeHtml(evaluation.reasoning || "Conflicting evidence.")}</strong>
        </div>

        <div class="conflict-grid">${cardsHtml}</div>

        <div class="form-group">
            <label>CONFIRMED VALUE — applies to all ${nodes.length} sources above</label>
            <input id="resolveInput-${escapeJs(ruleId)}" type="text" placeholder="e.g. 11.2">
        </div>

        <button class="primary-button full" onclick="resolveConflict('${escapeJs(ruleId)}')">
            Confirm &amp; Recalculate
        </button>
    `;
};

window.resolveConflict = async function (ruleId) {

    const evaluation = state.ruleEvaluations?.[ruleId];
    const evidenceIds = evaluation?.evidence_ids || [];
    const input = document.getElementById(`resolveInput-${ruleId}`);
    const raw = input.value.trim();

    if (!raw) {
        toast("Enter the confirmed value first.");
        return;
    }

    const value = coerceValue(raw);
    const beforeStatuses = { ...(state.ruleStatuses || {}) };
    const beforeScore = state.evaluation?.compliance_score;

    try {

        let lastImpact = null;
        for (const nodeId of evidenceIds) {
            const result = await api("/api/v3/officer-override", {
                method: "POST",
                body: JSON.stringify({ node_id: nodeId, new_value: value, actor: actorName() })
            });
            lastImpact = result.impact_analysis;
        }

        await loadBackendState();
        jumpToReviewItem(ruleId);

        renderDiffPanel({
            title: `Confirmed ${raw} across ${evidenceIds.length} source(s)`,
            oldScore: beforeScore,
            newScore: lastImpact?.new_score,
            oldDecision: state.evaluation?.decision,
            newDecision: lastImpact?.new_decision,
            affectedRules: lastImpact?.affected_rules || [ruleId],
            beforeStatuses,
        });

    } catch (error) {

        toast(`Resolution failed: ${error.message}`);
    }
};

/* =========================================================
RULES
========================================================= */

function renderRules() {

const container = $("ruleTable");

if (!state.rules.length) {

    container.innerHTML =
        `<div class="empty-state">
            No rules loaded.
        </div>`;

    return;
}

const rows = state.rules.map(rule => {

    const status =
        state.ruleStatuses?.[rule.rule_id] || "REVIEW";

    return `
        <div class="rule-row clickable" onclick="jumpToReviewItem('${escapeJs(rule.rule_id)}')">

            <div class="rule-id">
                ${escapeHtml(rule.rule_id)}
            </div>

            <div class="rule-clause">
                ${escapeHtml(rule.clause_text)}
            </div>

            <div>
                <span class="status-pill ${status}">
                    ${status}
                </span>
            </div>

            <div>
                ${rule.is_mandatory
                    ? '<span class="status-pill FAIL">MANDATORY</span>'
                    : '<span class="status-pill PASS">OPTIONAL</span>'
                }
            </div>

        </div>
    `;

}).join("");


container.innerHTML = `

    <div class="rule-row header">

        <div>RULE</div>
        <div>CLAUSE</div>
        <div>STATUS</div>
        <div>TYPE</div>

    </div>

    ${rows}
`;

}

/* =========================================================
BLAST RADIUS
========================================================= */

function populateBlastSelector() {

const select = $("blastNodeSelect");

select.innerHTML =
    `<option value="">Select evidence node</option>` +
    state.evidence.map(node => `
        <option value="${escapeHtml(node.node_id)}">
            ${escapeHtml(node.node_id)} — ${escapeHtml(node.entity_name)}
        </option>
    `).join("");

}

$("blastButton").addEventListener("click", () => {

const nodeId = $("blastNodeSelect").value;

if (!nodeId) {

    toast("Select an evidence node first.");

    return;
}

analyzeBlast(nodeId);

});

async function analyzeBlast(nodeId) {

try {

    /*
     * Backend endpoint expected:
     *
     * GET /api/v3/blast-radius/{node_id}
     */

    const result =
        await api(`/api/v3/blast-radius/${encodeURIComponent(nodeId)}`);

    renderBlastResult(result);

} catch (error) {

    /*
     * Local fallback for demo mode.
     */

    const affected = state.edges
        .filter(edge => edge.source_id === nodeId)
        .map(edge => edge.target_id);

    renderBlastResult({
        target_node: nodeId,
        blast_radius_size: affected.length,
        mandatory_rules_affected: 0,
        affected_rules: affected,
        decision_sensitivity:
            affected.length > 2
                ? "MODERATE"
                : affected.length
                    ? "LOW"
                    : "NONE"
    });

}

}

function renderBlastResult(result) {

const rules = result.affected_rules || [];

$("blastResult").innerHTML = `

    <div>

        <span class="eyebrow">
            DOWNSTREAM IMPACT
        </span>

        <div class="impact-number">
            ${result.blast_radius_size || 0}
        </div>

        <div class="impact-label">
            Rules inside blast radius
        </div>

    </div>

    <div class="detail-row">
        <label>MANDATORY RULES AFFECTED</label>
        <strong>
            ${result.mandatory_rules_affected || 0}
        </strong>
    </div>

    <div class="detail-row">
        <label>SENSITIVITY</label>
        <strong>
            ${escapeHtml(result.decision_sensitivity || "UNKNOWN")}
        </strong>
    </div>

    <div class="impact-list">

        ${rules.length
            ? rules.map(r => `
                <span class="rule-chip">
                    ${escapeHtml(r)}
                </span>
            `).join("")
            : '<span class="impact-label">No downstream rules.</span>'
        }

    </div>
`;

}

/* =========================================================
COUNTERFACTUAL
========================================================= */

$("simulateButton").addEventListener("click", async () => {

const changes = Array.from(document.querySelectorAll("#cfChanges .cf-change")).map(group => ({
    entity_name: group.querySelector(".cf-entity").value.trim(),
    extracted_value: group.querySelector(".cf-value").value.trim(),
}));

if (!changes.length || changes.some(change => !change.entity_name || !change.extracted_value)) {

    toast("Enter both entity and hypothetical value.");

    return;
}

/*
 * Your backend can expose:
 *
 * POST /api/v3/counterfactual
 */

try {

    const result = await api("/api/v3/counterfactual", {
        method: "POST",
        body: JSON.stringify({ changes })
    });

    renderSimulation(result);

} catch (error) {

    toast("Counterfactual endpoint unavailable.");

}

});

$("addCfChangeButton").addEventListener("click", () => {
    const row = document.createElement("div");
    row.className = "form-group cf-change";
    row.innerHTML = `
        <label>Entity</label>
        <input class="cf-entity" type="text" placeholder="e.g. experience_years">
        <label>Value</label>
        <input class="cf-value" type="text" placeholder="e.g. 7">
        <button class="text-button" type="button">Remove</button>`;
    row.querySelector("button").addEventListener("click", () => row.remove());
    $("cfChanges").appendChild(row);
});

function renderSimulation(result) {

const flippedText = (result.flipped_rules || [])
    .map(r => `${escapeHtml(r.rule_id)}: ${escapeHtml(r.from)} → ${escapeHtml(r.to)}`)
    .join(", ") || "None";

$("simulationResult").innerHTML = `

    <div class="sim-result">

        <div class="sim-stat">

            <span>CURRENT</span>

            <strong>
                ${Number(result.current_score || 0).toFixed(2)}
            </strong>

        </div>

        <div class="sim-stat">

            <span>PROJECTED</span>

            <strong>
                ${Number(result.projected_score ?? 0).toFixed(2)}
            </strong>

        </div>

        <div class="sim-stat">

            <span>DELTA</span>

            <strong>
                ${Number(result.score_improvement || 0).toFixed(2)}
            </strong>

        </div>

    </div>

    <div class="detail-row">

        <label>PROJECTED DECISION</label>

        <strong>
            ${escapeHtml(result.projected_decision || "SIMULATED")}
        </strong>

    </div>

    <div class="detail-row">

        <label>FLIPPED RULES</label>

        <strong>
            ${flippedText}
        </strong>

    </div>
`;

}

/* =========================================================
LEDGER
========================================================= */

function renderLedger() {

const container = $("ledgerContainer");

if (!state.ledger.length) {

    container.innerHTML =
        `<div class="empty-state">
            No ledger events.
        </div>`;

    return;
}

container.innerHTML = state.ledger.map(event => `

    <div class="ledger-event">

        <strong>
            ${escapeHtml(event.event_id)}
        </strong>

        <strong>
            ${escapeHtml(event.action)}
        </strong>

        <span>
            ${escapeHtml(event.actor)}
        </span>

        <span class="hash">
            ${escapeHtml(event.event_hash || "")}
        </span>

    </div>

`).join("");

}

/* =========================================================
BIDDER COMPARISON
========================================================= */

async function loadBidderComparison() {

    try {

        const result = await api("/api/v3/bidders");
        renderBidderTable(result.bidders || []);
        populateReportBidderSelect(result.bidders || []);

    } catch (error) {

        console.warn("Could not load bidder comparison.", error);
    }

    try {

        const matrix = await api("/api/v3/bidders/matrix");
        renderBidderMatrix(matrix);

    } catch (error) {

        console.warn("Could not load bidder matrix.", error);
    }
}

function populateReportBidderSelect(bidders) {

    const select = $("reportBidderSelect");
    select.innerHTML = bidders
        .map(b => `<option value="${escapeHtml(b.bidder_id)}">${escapeHtml(b.label)}</option>`)
        .join("");
}

function renderBidderMatrix(matrix) {

    const container = $("bidderMatrix");
    const bidderIds = matrix.bidder_ids || [];

    if (bidderIds.length < 2 || !matrix.rows.length) {
        container.innerHTML = `<div class="empty-state">Add at least two bidders on the same tender to compare.</div>`;
        return;
    }

    const headerCells = bidderIds.map(bid => `<th>${escapeHtml(matrix.bidder_labels[bid] || bid)}</th>`).join("");

    const bodyRows = matrix.rows.map(row => {
        const cells = bidderIds.map(bid => {
            const status = row.results[bid] || "N/A";
            return `<td class="matrix-cell ${status}">${escapeHtml(status)}</td>`;
        }).join("");
        return `<tr><td>${escapeHtml(row.rule_id)}</td><td>${escapeHtml(row.clause_text)}</td>${cells}</tr>`;
    }).join("");

    container.innerHTML = `
        <table class="matrix-table">
            <thead><tr><th>Rule</th><th>Requirement</th>${headerCells}</tr></thead>
            <tbody>${bodyRows}</tbody>
        </table>
    `;
}

window.loadBidderReport = async function () {

    const bidderId = $("reportBidderSelect").value;
    if (!bidderId) {
        toast("Ingest at least one bidder first.");
        return;
    }

    try {

        const r = await api(`/api/v3/bidders/${bidderId}/report`);
        renderBidderReport(r);

    } catch (error) {

        toast(`Could not generate report: ${error.message}`);
    }
};

function renderBidderReport(r) {

    const failuresHtml = (r.mandatory_failures || []).length
        ? r.mandatory_failures.map(id => `<span class="rule-chip">${escapeHtml(id)}</span>`).join(" ")
        : '<span class="empty-state">None</span>';
    const ruleReportsHtml = (r.rule_reports || []).length
        ? r.rule_reports.map(report => `<pre class="rule-report">${escapeHtml(report.text)}</pre>`).join("")
        : '<span class="empty-state">No provenance-backed rule reports are available.</span>';

    $("bidderReport").innerHTML = `
        <div class="detail-row"><label>BIDDER</label><strong>${escapeHtml(r.bidder_label)}</strong></div>
        <div class="detail-row"><label>DECISION</label><span class="status-pill ${r.decision}">${r.decision}</span></div>
        <div class="detail-row"><label>COMPLIANCE SCORE</label><strong>${r.compliance_score.toFixed(1)}/100</strong></div>
        <div class="detail-row"><label>MANDATORY REQUIREMENTS</label>
            <strong>${r.mandatory_requirements_satisfied}/${r.mandatory_requirements_total} satisfied</strong></div>
        <div class="detail-row"><label>EVIDENCE REVIEWED</label><strong>${r.evidence_reviewed}</strong></div>

        <div class="risk-row">
            <div class="risk-box low"><strong>${r.evidence_by_risk.low}</strong><span>Low risk</span></div>
            <div class="risk-box medium"><strong>${r.evidence_by_risk.medium}</strong><span>Medium risk</span></div>
            <div class="risk-box high"><strong>${r.evidence_by_risk.high}</strong><span>High risk</span></div>
        </div>

        <div class="detail-row"><label>MANDATORY FAILURES</label>${failuresHtml}</div>
        <div class="detail-row"><label>AUDIT ID</label><strong>${escapeHtml(r.audit_id)}</strong></div>
        <div class="detail-row"><label>LATEST LEDGER HASH</label><strong style="font-size:9px;">${escapeHtml(r.latest_hash || "—")}</strong></div>
        <div class="detail-row"><label>RULE DECISION DETAILS</label></div>
        <div class="rule-report-list">${ruleReportsHtml}</div>
    `;
}

function renderBidderTable(bidders) {

    const container = $("bidderTable");

    if (bidders.length === 0) {
        container.innerHTML = `<div class="empty-state">No bidders ingested yet — add one from the Ingest tab.</div>`;
        return;
    }

    const rows = bidders.map((b, i) => `
        <div class="bidder-row ${b.is_active ? "active" : ""}">
            <span class="bidder-rank">#${i + 1}</span>
            <div class="bidder-info">
                <strong>${escapeHtml(b.label)}</strong>
                <small>${b.mandatory_failures} mandatory failure(s), ${b.review_triggers} needing review</small>
            </div>
            <span class="status-pill ${escapeHtml(b.decision)}">${escapeHtml(b.decision)}</span>
            <strong class="bidder-score">${b.compliance_score.toFixed(1)}</strong>
            <button class="text-button" onclick="activateBidder('${escapeJs(b.bidder_id)}')">
                ${b.is_active ? "Viewing" : "View"}
            </button>
        </div>
    `).join("");

    container.innerHTML = `<div class="bidder-list">${rows}</div>`;
}

window.activateBidder = async function (bidderId) {

    try {

        await api(`/api/v3/bidders/${bidderId}/activate`, { method: "POST" });
        await loadBackendState();
        await loadBidderComparison();
        document.querySelector('[data-section="overview"]').click();

    } catch (error) {

        toast(`Could not switch bidder: ${error.message}`);
    }
};



async function loadBackendState() {

try {

    /*
     * Current backend endpoint:
     *
     * GET /api/v3/evaluate
     */

    const evaluation =
        await api("/api/v3/evaluate");

    // .overall has the score/decision/failure summary; .decisions is the
    // per-rule detail (used below for the Review Queue and node inspector).
    state.evaluation = evaluation.overall;

    // Per-rule reasoning + evidence_ids — needed so a Review Queue item
    // can be traced back to the evidence node(s) actually causing it.
    state.ruleEvaluations = evaluation.decisions;

    /*
     * The frontend expects the backend to expose graph
     * state through a state endpoint.
     */

    try {

        const graph =
            await api("/api/v3/state");

        state.evidence = graph.evidence || [];
        state.rules = graph.rules || [];
        state.edges = graph.edges || [];
        state.ledger = graph.ledger || [];
        state.ruleStatuses = graph.rule_statuses || {};

        if (graph.audit_id) {
            state.auditId = graph.audit_id;
        }

        if (graph.tender_deadline) {
            $("deadline").textContent =
                formatDate(graph.tender_deadline);
        }

    } catch (graphError) {

        console.warn(
            "State endpoint not available yet.",
            graphError
        );
    }

    renderEverything();

    toast("Audit state synchronized.");

} catch (error) {

    console.error(error);

    toast(
        "Backend unavailable — running interface in demo state."
    );

    loadDemoState();
}

}

/* =========================================================
DEMO FALLBACK
========================================================= */

function loadDemoState() {

state.evidence = [
    {
        node_id: "E14",
        entity_name: "turnover",
        extracted_value: 7.2,
        confidence: 0.98,
        status: "CONFLICTING",
        source_doc: "financial_statement.pdf"
    },
    {
        node_id: "E22",
        entity_name: "turnover",
        extracted_value: 11.2,
        confidence: 0.95,
        status: "CONFLICTING",
        source_doc: "turnover_certificate.pdf"
    }
];

state.rules = [
    {
        rule_id: "R42",
        clause_text: "Turnover must be greater than or equal to ₹10 Cr",
        weight: 50,
        is_mandatory: true
    },
    {
        rule_id: "R90",
        clause_text: "Composite eligibility rule",
        weight: 20,
        is_mandatory: true
    }
];

state.edges = [
    {
        source_id: "E14",
        target_id: "R42"
    },
    {
        source_id: "E22",
        target_id: "R42"
    },
    {
        source_id: "R42",
        target_id: "R90"
    }
];

state.ruleStatuses = {
    R42: "REVIEW",
    R90: "REVIEW"
};

state.evaluation = {
    compliance_score: 0,
    decision: "REVIEW",
    mandatory_failures: [],
    review_triggers: ["R42", "R90"]
};

state.ledger = [
    {
        event_id: "EVT-0000",
        action: "INIT",
        actor: "SYSTEM",
        event_hash: "GENESIS-HASH"
    }
];

$("deadline").textContent =
    "30 AUG 2026";

renderEverything();

}

/* =========================================================
RENDER EVERYTHING
========================================================= */

function renderEverything() {

$("auditId").textContent = state.auditId;

$("evidenceCount").textContent =
    state.evidence.length;

$("ruleCount").textContent =
    state.rules.length;

$("dependencyCount").textContent =
    state.edges.length;

$("ledgerCount").textContent =
    state.ledger.length;

renderOverview();
renderEvidenceGraph();
renderRules();
renderLedger();

}

/* =========================================================
REFRESH
========================================================= */

$("refreshButton").addEventListener(
"click",
loadBackendState
);

/* =========================================================
UTILITIES
========================================================= */

function escapeHtml(value) {

return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

}

function escapeJs(value) {

return String(value)
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "\\'");

}

function formatDate(value) {

try {

    return new Date(value)
        .toLocaleString(
            "en-IN",
            {
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit"
            }
        );

} catch {

    return value;
}

}

/* =========================================================
START APPLICATION
========================================================= */

loadBackendState();
loadTenderStatus();
