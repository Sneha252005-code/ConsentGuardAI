document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("consent-form");

    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const userId = document.getElementById("user_id").value.trim();
        const purpose = document.getElementById("purpose").value;

        const dataCategories = Array.from(
            form.querySelectorAll('input[name="data_categories"]:checked')
        ).map((checkbox) => checkbox.value);

        if (dataCategories.length === 0) {
            showMessage(
                "consent-message",
                "Please select at least one data category.",
                true
            );
            return;
        }

        try {
            const result = await apiRequest("/api/consent/", {
                method: "POST",
                body: JSON.stringify({
                    user_id: userId,
                    purpose: purpose,
                    data_categories: dataCategories
                })
            });

            showMessage(
                "consent-message",
                `Consent granted successfully. Consent ID: ${result.consent_id || "Created"}`
            );

            form.reset();
        } catch (error) {
            showMessage("consent-message", error.message, true);
        }
    });
});
