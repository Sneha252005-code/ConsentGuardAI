
async function loadAuditEvents() {
    const tableBody = document.querySelector("#audit-table-body");
    const statusElement = document.querySelector("#audit-status");

    if (!tableBody) return;

    if (statusElement) {
        statusElement.textContent = "Loading audit events...";
    }

    try {
        const data = await apiRequest("/api/audit");

        // The Flask API returns an array directly.
        const events = Array.isArray(data) ? data : (data.events || []);

        tableBody.replaceChildren();

        if (events.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 4;
            cell.textContent = "No audit events recorded yet.";
            row.appendChild(cell);
            tableBody.appendChild(row);

            if (statusElement) {
                statusElement.textContent = "No audit events recorded yet.";
            }
            return;
        }

        events.forEach((event) => {
            const row = document.createElement("tr");

            [
                event.created_at || event.timestamp || "",
                event.event_type || event.event || "",
                event.user_id || "",
                event.description || event.details || ""
            ].forEach((value) => {
                const cell = document.createElement("td");
                cell.textContent = String(value);
                row.appendChild(cell);
            });

            tableBody.appendChild(row);
        });

        if (statusElement) {
            statusElement.textContent = "Audit events loaded successfully.";
        }
    } catch (error) {
        tableBody.replaceChildren();

        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = error.message || "Could not load audit events.";
        row.appendChild(cell);
        tableBody.appendChild(row);

        if (statusElement) {
            statusElement.textContent = "Failed to load audit events.";
        }

        console.error("Audit loading failed:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.querySelector("#refresh-audit");

    if (refreshButton) {
        refreshButton.addEventListener("click", loadAuditEvents);
    }

    loadAuditEvents();
});
