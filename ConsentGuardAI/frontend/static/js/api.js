/**
 * Shared helper for sending JSON requests to the Flask API.
 */

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    let data;

    try {
        data = await response.json();
    } catch {
        data = { error: "The server returned an invalid response." };
    }

    if (!response.ok) {
        throw new Error(
            data.error || data.message || `Request failed (${response.status}).`
        );
    }

    return data;
}

function showMessage(elementId, message, isError = false) {
    const element = document.getElementById(elementId);

    if (!element) {
        return;
    }

    element.textContent = message;
    element.style.color = isError ? "#b91c1c" : "#166534";
}
