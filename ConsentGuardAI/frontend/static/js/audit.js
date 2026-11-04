/**
 * ConsentGuardAI - Decision History & Audit Controller
 * Manages chronological audit log viewing, filtering, search, and SHA-256 chain verification.
 */

let allAuditEvents = [];

async function loadAuditEvents() {
    const tableBody = document.querySelector("#audit-table-body");
    const countBadge = document.querySelector("#audit-entries-count");
    if (!tableBody) return;

    try {
        const events = await apiRequest("/api/audit?limit=150");
        allAuditEvents = Array.isArray(events) ? events : [];
        if (countBadge) countBadge.textContent = `${allAuditEvents.length} Entries`;

        applyAuditFilters();
        verifyIntegrityChain();
    } catch (err) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 24px;">
                    Please <a href="/login"><strong>sign in</strong></a> to view audit records.
                </td>
            </tr>
        `;
    }
}

function applyAuditFilters() {
    const tableBody = document.querySelector("#audit-table-body");
    const decisionFilter = document.querySelector("#filter-decision")?.value || "ALL";
    const reuseFilter = document.querySelector("#filter-reuse")?.value || "ALL";
    const searchVal = (document.querySelector("#audit-search")?.value || "").toLowerCase().trim();

    if (!tableBody) return;

    let filtered = allAuditEvents.filter(evt => {
        // Decision filter
        if (decisionFilter !== "ALL" && evt.decision !== decisionFilter) {
            return false;
        }

        // Reuse filter
        if (reuseFilter === "REUSE_ONLY" && !evt.reuse_detected) {
            return false;
        }
        if (reuseFilter === "NEW_ONLY" && evt.reuse_detected) {
            return false;
        }

        // Search text
        if (searchVal) {
            const haystack = [
                evt.request_ref,
                evt.event_type,
                evt.description,
                evt.decision_reason,
                evt.original_purpose,
                evt.requested_purpose,
            ].join(" ").toLowerCase();

            if (!haystack.includes(searchVal)) {
                return false;
            }
        }

        return true;
    });

    tableBody.replaceChildren();

    if (filtered.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 28px;">
                    No audit records matching the selected criteria.
                </td>
            </tr>
        `;
        return;
    }

    filtered.forEach(evt => {
        const tr = document.createElement("tr");
        const dec = evt.decision || "—";
        const decBadge = dec !== "—"
            ? `<span class="badge badge-${dec}">${dec}</span>`
            : `<span class="badge badge-neutral">—</span>`;

        const reuseBadge = evt.reuse_detected
            ? `<span class="badge badge-WARN">YES (Asset #${evt.matched_record_id || "?"})</span>`
            : `<span class="badge badge-ALLOW">NO</span>`;

        const sentBadge = evt.sent_to_provider
            ? `<span class="badge badge-ALLOW">Transmitted</span>`
            : `<span class="badge badge-BLOCK">Withheld</span>`;

        tr.innerHTML = `
            <td style="white-space: nowrap; font-size: 0.78rem; color: var(--text-muted);">
                ${evt.created_at ? new Date(evt.created_at).toLocaleString() : "—"}
            </td>
            <td><code>${escapeHtml(evt.request_ref || `REQ-${evt.id}`)}</code></td>
            <td style="font-size: 0.78rem; font-weight: 600; color: var(--text-muted);">${escapeHtml(evt.event_type)}</td>
            <td>${reuseBadge}</td>
            <td><span style="font-weight: 600; color: #4338ca;">${escapeHtml(evt.original_purpose || "—")}</span></td>
            <td><span style="font-weight: 600; color: var(--text-main);">${escapeHtml(evt.requested_purpose || "—")}</span></td>
            <td>${decBadge}</td>
            <td>${sentBadge}</td>
            <td style="font-size: 0.8rem; color: var(--text-muted); max-width: 320px;" title="${escapeHtml(evt.decision_reason || evt.description)}">
                ${escapeHtml(evt.decision_reason || evt.description)}
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

async function verifyIntegrityChain() {
    const badgeEl = document.querySelector("#integrity-badge");
    if (!badgeEl) return;

    badgeEl.innerHTML = `<span>🔒</span> Verifying SHA-256 hash chain...`;
    try {
        const res = await apiRequest("/api/audit/integrity");
        if (res.integrity_valid) {
            badgeEl.innerHTML = `
                <span style="color: #6ee7b7;">✓ Cryptographically Valid (${res.entries_checked} entries verified)</span>
            `;
        } else {
            badgeEl.innerHTML = `
                <span style="color: #fca5a5;">⚠️ Tamper Detected (Hash mismatch)</span>
            `;
        }
    } catch (err) {
        badgeEl.textContent = "Chain check unavailable";
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

document.addEventListener("DOMContentLoaded", loadAuditEvents);
