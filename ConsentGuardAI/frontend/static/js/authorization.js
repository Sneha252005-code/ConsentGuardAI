document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("authorization-form");

    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const payload = {
            user_id: document.getElementById("auth-user-id").value.trim(),
            purpose: document.getElementById("auth-purpose").value,
            data_categories: [
                document.getElementById("auth-category").value
            ]
        };

        const resultElement = document.getElementById("authorization-result");
        resultElement.textContent = "Checking authorization...";

        try {
            const result = await apiRequest("/api/authorization/check", {
                method: "POST",
                body: JSON.stringify(payload)
            });

            const authorized = result.authorized === true;

            resultElement.textContent = authorized
                ? "Authorization granted for this request."
                : "Authorization denied. Check the consent details.";

            resultElement.style.color = authorized ? "#166534" : "#b91c1c";
        } catch (error) {
            showMessage("authorization-result", error.message, true);
        }
    });
});
