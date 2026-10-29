const chatForm = document.getElementById("chat-form");
const promptInput = document.getElementById("prompt");
const messages = document.getElementById("messages");
const statusText = document.getElementById("status");
const sendButton = document.getElementById("send-button");

function addMessage(role, text) {
    const message = document.createElement("div");
    message.className = `message ${role}`;
    message.textContent = text;
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const prompt = promptInput.value.trim();
    const purpose = document.getElementById("purpose").value.trim();
    const dataCategory = document.getElementById("category").value.trim();

    if (!prompt || !purpose || !dataCategory) {
        statusText.textContent = "Please complete all fields.";
        return;
    }

    addMessage("user", prompt);
    promptInput.value = "";
    sendButton.disabled = true;
    statusText.textContent = "Checking authorization and waiting for AI...";

    try {
        const response = await fetch("/api/genai/generate", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                user_id: "session",
                purpose: purpose,
                data_category: dataCategory,
                prompt: prompt
            })
        });

        const result = await response.json();

        if (result.requires_consent_review) {
            addMessage(
                "assistant",
                "Protected data reuse detected. This request was stopped and was NOT sent to the AI provider. Consent review is required."
            );
            statusText.textContent = "Request blocked pending consent review.";
        } else if (!response.ok) {
            addMessage(
                "assistant",
                result.error || "The request could not be completed."
            );
            statusText.textContent = "Request was not completed.";
        } else if (result.response) {
            addMessage("assistant", result.response);
            statusText.textContent = "Response received.";
        } else {
            addMessage(
                "assistant",
                result.error || "No AI response was returned."
            );
            statusText.textContent = "No response received.";
        }
    } catch (error) {
        addMessage(
            "assistant",
            "Unable to connect to the server. Please try again."
        );
        statusText.textContent = "Connection failed.";
        console.error(error);
    } finally {
        sendButton.disabled = false;
        promptInput.focus();
    }
});