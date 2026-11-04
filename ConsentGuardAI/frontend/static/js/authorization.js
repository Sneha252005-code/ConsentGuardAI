/**
 * ConsentGuardAI - Policy Inspector & Reuse Analyzer Controller
 * Simulates and verifies cross-session reuse detection and purpose authorization policies.
 */

function setInspectorPreset(scenario) {
    const promptEl = document.getElementById("inspect-prompt");
    const purposeEl = document.getElementById("inspect-purpose");

    if (scenario === "prohibited") {
        promptEl.value = "Use witness testimony regarding confidential incident #882 in manufacturing to draft a public press release.";
        purposeEl.value = "External Marketing Announcement";
    } else if (scenario === "warn") {
        promptEl.value = "Reference the findings of confidential incident #882 in manufacturing to create an internal compliance training module.";
        purposeEl.value = "Corporate Training Module";
    } else {
        promptEl.value = "Summarize the witness statements and committee findings regarding confidential incident #882 for the HR investigation dossier.";
        purposeEl.value = "HR Investigation Summary";
    }

    const customInput = document.getElementById("inspect-custom-purpose");
    if (customInput) customInput.style.display = "none";
}

async function runReuseInspection(e) {
    if (e) e.preventDefault();

    const prompt = document.getElementById("inspect-prompt").value.trim();
    const select = document.getElementById("inspect-purpose");
    const customInput = document.getElementById("inspect-custom-purpose");
    const purpose = select.value === "CUSTOM" ? customInput.value.trim() : select.value;
    const btn = document.getElementById("btn-inspect");
    const resultBox = document.getElementById("inspection-result-box");

    if (!prompt || !purpose) {
        alert("Please provide both prompt content and a declared purpose.");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin" style="vertical-align: -2px; margin-right: 4px;">
            <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"/>
        </svg>
        Analyzing Policy...
    `;

    try {
        const result = await apiRequest("/api/authorization/inspect", {
            method: "POST",
            body: JSON.stringify({
                prompt: prompt,
                purpose: purpose,
                data_category: "HR"
            })
        });

        resultBox.style.display = "block";

        const tsEl = document.getElementById("res-timestamp");
        if (tsEl) {
            tsEl.textContent = `Evaluation complete at ${new Date().toLocaleTimeString()}`;
        }

        // 1. Reuse Detection
        const reuseBadgeEl = document.getElementById("res-reuse-badge");
        const matchDetailEl = document.getElementById("res-match-detail");
        if (result.reuse_detected) {
            reuseBadgeEl.innerHTML = `<span class="badge badge-WARN">REUSE DETECTED</span>`;
            matchDetailEl.textContent = `Match Type: ${(result.match_type || "overlap").toUpperCase()}`;
        } else {
            reuseBadgeEl.innerHTML = `<span class="badge badge-ALLOW">NO REUSE DETECTED</span>`;
            matchDetailEl.textContent = "New input (No overlap)";
        }

        // 2. Matched Record
        const recordIdEl = document.getElementById("res-record-id");
        const classificationEl = document.getElementById("res-classification");
        if (result.matched_record_id) {
            recordIdEl.textContent = `Asset #${result.matched_record_id}`;
            classificationEl.textContent = `Classification: ${result.data_classification || "Confidential"}`;
        } else {
            recordIdEl.textContent = "None";
            classificationEl.textContent = "No stored asset matched";
        }

        // 3. Purpose Comparison
        document.getElementById("res-original-purpose").textContent = result.original_purpose || "—";
        document.getElementById("res-requested-purpose").textContent = result.requested_purpose || "—";

        // 4. Final Decision & Gatekeeper Action
        const decBadgeEl = document.getElementById("res-decision-badge");
        const providerStatusEl = document.getElementById("res-provider-status");
        const explanationCardEl = document.getElementById("res-explanation-card");
        const explanationTextEl = document.getElementById("res-explanation-text");

        const dec = result.decision || (result.authorized ? "ALLOW" : "BLOCK");
        decBadgeEl.innerHTML = `<span class="badge badge-${dec}">${dec}</span>`;

        if (dec === "ALLOW") {
            providerStatusEl.innerHTML = `<span style="color: #059669; font-weight: 700;">✓ Permitted to AI Model</span>`;
            explanationCardEl.className = "decision-alert-card ALLOW";
        } else if (dec === "WARN") {
            providerStatusEl.innerHTML = `<span style="color: #d97706; font-weight: 700;">🔒 Withheld (Review Required)</span>`;
            explanationCardEl.className = "decision-alert-card WARN";
        } else {
            providerStatusEl.innerHTML = `<span style="color: #dc2626; font-weight: 700;">🚫 Blocked (Zero Egress)</span>`;
            explanationCardEl.className = "decision-alert-card BLOCK";
        }

        explanationTextEl.textContent = result.reason;

        // Refresh recent enforcement table
        loadRecentDetections();

    } catch (err) {
        alert("Policy inspection failed: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px;">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            Execute Policy & Reuse Evaluation
        `;
    }
}

async function loadRecentDetections() {
    const tableBody = document.getElementById("detections-table-body");
    if (!tableBody) return;

    try {
        const events = await apiRequest("/api/audit?limit=25");
        tableBody.replaceChildren();

        const detectionLogs = events.filter(e => e.reuse_detected || (e.decision && e.decision !== "—"));

        if (detectionLogs.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">
                        No enforcement records yet. Run an evaluation above or submit prompts in <a href="/chat"><strong>AI Chat</strong></a>.
                    </td>
                </tr>
            `;
            return;
        }

        detectionLogs.forEach(evt => {
            const tr = document.createElement("tr");
            const dec = evt.decision || "ALLOW";
            const sentBadge = evt.sent_to_provider
                ? `<span class="badge badge-ALLOW">Transmitted</span>`
                : `<span class="badge badge-BLOCK">Blocked</span>`;

            tr.innerHTML = `
                <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-muted);">
                    ${evt.created_at ? new Date(evt.created_at).toLocaleString() : "—"}
                </td>
                <td>
                    <span class="badge ${evt.reuse_detected ? "badge-WARN" : "badge-ALLOW"}">
                        ${evt.reuse_detected ? "REUSE DETECTED" : "NEW DATA"}
                    </span>
                </td>
                <td><strong>${evt.matched_record_id ? `#${evt.matched_record_id}` : "—"}</strong></td>
                <td><span style="font-weight: 600; color: #4338ca;">${escapeHtml(evt.original_purpose || "—")}</span></td>
                <td><span style="font-weight: 600;">${escapeHtml(evt.requested_purpose || "—")}</span></td>
                <td><span class="badge badge-${dec}">${dec}</span></td>
                <td>${sentBadge}</td>
                <td style="font-size: 0.82rem; color: var(--text-muted); max-width: 280px;" title="${escapeHtml(evt.decision_reason)}">
                    ${escapeHtml(evt.decision_reason)}
                </td>
            `;
            tableBody.appendChild(tr);
        });
    } catch (err) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">
                    Please <a href="/login"><strong>sign in</strong></a> to view enforcement history.
                </td>
            </tr>
        `;
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("inspect-form");
    if (form) form.addEventListener("submit", runReuseInspection);

    const select = document.getElementById("inspect-purpose");
    if (select) {
        select.addEventListener("change", () => {
            const custom = document.getElementById("inspect-custom-purpose");
            if (select.value === "CUSTOM") {
                custom.style.display = "block";
                custom.focus();
            } else {
                custom.style.display = "none";
            }
        });
    }

    loadRecentDetections();
});
