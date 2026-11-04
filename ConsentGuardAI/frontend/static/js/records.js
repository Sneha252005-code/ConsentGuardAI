/**
 * ConsentGuardAI - Protected Data Records Controller
 * Manages encrypted protected data assets, immutable original purpose display,
 * safe metadata inspection, and cryptographic tracking.
 */

let allTrackedRecords = [];

async function loadTrackedRecords() {
    const tableBody = document.getElementById("records-table-body");
    const countBadge = document.getElementById("records-count-badge");
    if (!tableBody) return;

    try {
        const records = await apiRequest("/api/records");
        allTrackedRecords = Array.isArray(records) ? records : [];
        tableBody.replaceChildren();

        if (countBadge) {
            countBadge.textContent = `${allTrackedRecords.length} ${allTrackedRecords.length === 1 ? 'Asset' : 'Assets'} Tracked`;
        }

        if (allTrackedRecords.length === 0) {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 36px;">
                    No protected data assets registered yet. Submit messages with tracking enabled in <a href="/chat"><strong>AI Workspace</strong></a> or register an asset below.
                </td>
            `;
            tableBody.appendChild(tr);
            return;
        }

        allTrackedRecords.forEach(rec => {
            const tr = document.createElement("tr");
            const cleanTitle = rec.title || "Untitled Asset";
            const sourceDisplay = rec.source_conversation && rec.source_conversation !== "Session Direct"
                ? rec.source_conversation.substring(0, 10) + "..."
                : "Direct Submission";

            tr.innerHTML = `
                <td><strong>#${rec.id}</strong></td>
                <td><span style="font-weight: 600; color: var(--text-main);">${escapeHtml(cleanTitle)}</span></td>
                <td style="max-width: 260px; font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(rec.description || "—")}</td>
                <td><code>${escapeHtml(sourceDisplay)}</code></td>
                <td><span class="badge badge-neutral">${escapeHtml(rec.data_classification || "Confidential")}</span></td>
                <td>
                    <span style="display: inline-flex; align-items: center; gap: 5px; font-weight: 600; color: #4338ca; background: #eef2ff; padding: 3px 9px; border-radius: 6px; font-size: 0.8rem;">
                        <span>🔒</span> ${escapeHtml(rec.original_purpose)}
                    </span>
                </td>
                <td style="font-size: 0.8rem; color: var(--text-muted); white-space: nowrap;">
                    ${rec.created_at ? new Date(rec.created_at).toLocaleDateString() : "—"}
                </td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary btn-sm" onclick="inspectRecord(${rec.id})" title="View security metadata">Inspect</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteRecord(${rec.id})" title="Delete protected asset">Delete</button>
                    </div>
                </td>
            `;
            tableBody.appendChild(tr);
        });
    } catch (err) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; color: #991b1b; padding: 24px;">
                    Please <a href="/login"><strong>sign in</strong></a> to view your organization's protected records.
                </td>
            </tr>
        `;
    }
}

function inspectRecord(recId) {
    const rec = allTrackedRecords.find(r => r.id === recId);
    if (!rec) return;

    const modal = document.getElementById("record-detail-modal");
    if (!modal) return;

    document.getElementById("modal-record-title").textContent = rec.title || "Protected Asset";
    document.getElementById("modal-record-id").textContent = `Asset Record #${rec.id}`;
    document.getElementById("modal-record-purpose").textContent = rec.original_purpose || "Unspecified";
    document.getElementById("modal-record-classification").textContent = rec.data_classification || "Confidential";
    document.getElementById("modal-record-source").textContent = rec.source_conversation || "Direct Registration";
    document.getElementById("modal-record-desc").textContent = rec.description || "No description provided.";

    modal.style.display = "flex";
}

async function deleteRecord(recordId) {
    if (!confirm(`Are you sure you want to permanently delete tracked asset #${recordId}?`)) return;
    try {
        await apiRequest(`/api/records/${recordId}`, { method: "DELETE" });
        loadTrackedRecords();
    } catch (err) {
        alert("Failed to delete record: " + err.message);
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
    loadTrackedRecords();

    const form = document.getElementById("create-record-form");
    const statusEl = document.getElementById("record-form-status");
    const btnSave = document.getElementById("btn-save-record");

    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const title = document.getElementById("record-title").value.trim();
            const classification = document.getElementById("record-classification").value;
            const originalPurpose = document.getElementById("record-original-purpose").value.trim();
            const description = document.getElementById("record-description").value.trim();
            const content = document.getElementById("record-content").value.trim();

            if (!title || !originalPurpose || !content) {
                if (statusEl) {
                    statusEl.textContent = "Please fill in title, original purpose, and content.";
                    statusEl.style.color = "#991b1b";
                }
                return;
            }

            if (btnSave) {
                btnSave.disabled = true;
                btnSave.innerHTML = `<span>⏳</span> Encrypting &amp; Saving...`;
            }

            if (statusEl) {
                statusEl.textContent = "Encrypting data with AES-256 and saving record...";
                statusEl.style.color = "#4f46e5";
            }

            try {
                await apiRequest("/api/records", {
                    method: "POST",
                    body: JSON.stringify({
                        title: title,
                        data_classification: classification,
                        original_purpose: originalPurpose,
                        description: description || `Protected asset: ${title}`,
                        content: content,
                    })
                });

                form.reset();
                if (statusEl) {
                    statusEl.textContent = "✓ Asset encrypted and tracked under bound purpose!";
                    statusEl.style.color = "#059669";
                }
                loadTrackedRecords();
            } catch (err) {
                if (statusEl) {
                    statusEl.textContent = "Error saving asset: " + err.message;
                    statusEl.style.color = "#991b1b";
                }
            } finally {
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.innerHTML = `<span>🔒</span> Encrypt &amp; Track Asset`;
                }
            }
        });
    }
});
