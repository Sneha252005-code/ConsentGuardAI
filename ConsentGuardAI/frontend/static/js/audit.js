
async function loadAuditEvents() {
    const tableBody = document.querySelector("#audit-table-body");
    if (!tableBody) return;

    try {
        const data = await apiRequest("/api/audit/");
        const events = data.events || [];

        tableBody.replaceChildren();

        if (events.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 4;
            cell.textContent = "No audit events recorded yet.";
            row.appendChild(cell);
            tableBody.appendChild(row);
            return;
        }

        events.forEach((event) => {
            const row = document.createElement("tr");

            [
                event.timestamp || "",
                event.event || "",
                event.user_id || "",
                event.details || ""
            ].forEach((value) => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });

            tableBody.appendChild(row);
        });
    } catch (error) {
        tableBody.replaceChildren();
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = "Could not load audit events.";
        row.appendChild(cell);
        tableBody.appendChild(row);
        console.error("Audit loading failed:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadAuditEvents();

    const refreshButton = document.querySelector("#refresh-audit");
    if (refreshButton) {
        refreshButton.addEventListener("click", loadAuditEvents);
    }
});
