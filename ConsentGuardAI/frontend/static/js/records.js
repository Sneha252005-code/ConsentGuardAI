document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("records-form");
    const tableBody = document.getElementById("records-table-body");

    if (!form || !tableBody) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const consentId = document.getElementById("consent-id").value.trim();

        showMessage("records-message", "Loading consent record...");

        try {
            const record = await apiRequest(
                `/api/consent/${encodeURIComponent(consentId)}`
            );

            const fields = [
                ["Consent ID", record.consent_id],
                ["User ID", record.user_id],
                ["Purpose", record.purpose],
                ["Data Categories", Array.isArray(record.data_categories)
                    ? record.data_categories.join(", ")
                    : ""],
                ["Granted", record.granted ? "Yes" : "No"],
                ["Withdrawn At", record.withdrawn_at || "Not withdrawn"]
            ];

            tableBody.replaceChildren();

            fields.forEach(([label, value]) => {
                const row = document.createElement("tr");
                const heading = document.createElement("th");
                const cell = document.createElement("td");

                heading.textContent = label;
                cell.textContent = value ?? "—";

                row.append(heading, cell);
                tableBody.appendChild(row);
            });

            showMessage("records-message", "Consent record loaded.");
        } catch (error) {
            tableBody.replaceChildren();
            showMessage("records-message", error.message, true);
        }
    });
});
