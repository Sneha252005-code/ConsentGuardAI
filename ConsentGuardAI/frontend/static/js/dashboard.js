document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.getElementById("dashboard");

    if (!dashboard) return;

    const message = document.createElement("p");
    message.className = "dashboard-notice";
    message.textContent =
        "Dashboard metrics will appear here when evaluation and audit data are connected.";

    dashboard.appendChild(message);
});
