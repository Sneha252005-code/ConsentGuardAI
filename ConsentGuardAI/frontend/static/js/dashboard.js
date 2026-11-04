/**
 * ConsentGuardAI - Screen A: Privacy Dashboard Controller
 * Loads real database-backed statistics and recent activity from /api/audit/stats
 */

async function loadDashboardStats() {
    const totalRecordsEl = document.getElementById("stat-total-records");
    const purposeRecordsEl = document.getElementById("stat-purpose-records");
    const reuseAttemptsEl = document.getElementById("stat-reuse-attempts");
    const allowCountEl = document.getElementById("stat-allow-count");
    const warnCountEl = document.getElementById("stat-warn-count");
    const blockCountEl = document.getElementById("stat-block-count");
    const tableBody = document.getElementById("dashboard-reuse-table-body");

    try {
        const stats = await apiRequest("/api/audit/stats");

        if (totalRecordsEl) totalRecordsEl.textContent = stats.total_records_tracked;
        if (purposeRecordsEl) purposeRecordsEl.textContent = stats.records_with_original_purpose;
        if (reuseAttemptsEl) reuseAttemptsEl.textContent = stats.reuse_attempts_detected;

        if (stats.decisions) {
            if (allowCountEl) allowCountEl.textContent = `ALLOW: ${stats.decisions.ALLOW || 0}`;
            if (warnCountEl) warnCountEl.textContent = `WARN: ${stats.decisions.WARN || 0}`;
            if (blockCountEl) blockCountEl.textContent = `BLOCK: ${stats.decisions.BLOCK || 0}`;
        }

        // Render recent reuse events table
        if (tableBody) {
            tableBody.replaceChildren();
            const events = stats.recent_reuse_events || [];

            if (events.length === 0) {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 28px;">
                        No data reuse attempts recorded yet. Start a conversation in <a href="/chat"><strong>AI Chat</strong></a> to test the workflow.
                    </td>
                `;
                tableBody.appendChild(tr);
                return;
            }

            events.forEach(evt => {
                const tr = document.createElement("tr");
                const decisionClass = `badge-${evt.decision}`;
                const sentBadge = evt.sent_to_provider
                    ? `<span class="badge badge-ALLOW">YES</span>`
                    : `<span class="badge badge-BLOCK">BLOCKED (No)</span>`;

                tr.innerHTML = `
                    <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-muted);">
                        ${evt.timestamp ? new Date(evt.timestamp).toLocaleString() : "—"}
                    </td>
                    <td><code>${evt.request_ref || "—"}</code></td>
                    <td><strong>#${evt.matched_record_id || "—"}</strong></td>
                    <td><span style="font-weight: 600; color: #4338ca;">${evt.original_purpose || "—"}</span></td>
                    <td><span style="font-weight: 600;">${evt.requested_purpose || "—"}</span></td>
                    <td><span class="badge ${decisionClass}">${evt.decision}</span></td>
                    <td>${sentBadge}</td>
                    <td style="max-width: 280px; font-size: 0.82rem; color: var(--text-muted);" title="${evt.decision_reason}">
                        ${evt.decision_reason}
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        }
    } catch (err) {
        console.warn("Failed to load dashboard stats:", err);
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; color: #991b1b; padding: 20px;">
                        Please <a href="/login"><strong>sign in</strong></a> to view your secure dashboard metrics.
                    </td>
                </tr>
            `;
        }
    }
}

document.addEventListener("DOMContentLoaded", loadDashboardStats);
