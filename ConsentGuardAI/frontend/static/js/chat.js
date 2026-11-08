/**
 * ConsentGuardAI - AI Workspace & Gatekeeper Controller
 * Implements isolated conversation sessions, live purpose selection,
 * cross-conversation reuse detection, and authoritative ALLOW/WARN/BLOCK enforcement.
 */

let activeConversationId = null;

function handlePurposeChange() {
    const select = document.getElementById("declared-purpose");
    const customInput = document.getElementById("custom-purpose-input");
    if (!select || !customInput) return;

    if (select.value === "CUSTOM") {
        customInput.style.display = "inline-block";
        customInput.focus();
    } else {
        customInput.style.display = "none";
    }
}

function getEffectivePurpose() {
    const select = document.getElementById("declared-purpose");
    const customInput = document.getElementById("custom-purpose-input");
    if (!select) return "General Analysis";

    if (select.value === "CUSTOM") {
        return (customInput ? customInput.value : "").trim() || "General Analysis";
    }
    return select.value;
}

// ---------------------------------------------------------------------------
// Conversation Sessions Management
// ---------------------------------------------------------------------------

async function loadConversations() {
    const listEl = document.getElementById("sessions-list");
    if (!listEl) return;

    try {
        const convs = await apiRequest("/api/genai/conversations");
        listEl.replaceChildren();

        if (convs.length === 0) {
            listEl.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 24px 12px; font-size: 0.82rem;">
                    No conversation sessions yet.<br>Click <strong>New Conversation</strong> above.
                </div>
            `;
            await startNewConversation();
            return;
        }

        convs.forEach(conv => {
            const item = document.createElement("div");
            item.className = `session-item ${conv.id === activeConversationId ? "active" : ""}`;
            item.onclick = (e) => {
                if (e.target.closest(".session-delete-btn")) return;
                selectConversation(conv.id, conv.title);
            };

            const title = conv.title || "Conversation";
            item.innerHTML = `
                <span class="session-title-text" title="${escapeHtml(title)}">💬 ${escapeHtml(title)}</span>
                <button class="session-delete-btn" title="Delete conversation" onclick="deleteConv('${conv.id}')">🗑️</button>
            `;
            listEl.appendChild(item);
        });

        // Select the active conversation or default to the first one
        if (!activeConversationId && convs.length > 0) {
            selectConversation(convs[0].id, convs[0].title);
        }
    } catch (err) {
        listEl.innerHTML = `
            <div style="text-align: center; color: #991b1b; padding: 24px 12px; font-size: 0.82rem;">
                Please <a href="/login"><strong>sign in</strong></a> to access your conversation sessions.
            </div>
        `;
    }
}

async function startNewConversation() {
    try {
        const newConv = await apiRequest("/api/genai/conversations", {
            method: "POST",
            body: JSON.stringify({ title: "New Conversation" })
        });
        activeConversationId = newConv.id;
        await loadConversations();
        selectConversation(newConv.id, "New Conversation");
    } catch (err) {
        console.warn("Unable to create conversation session:", err);
    }
}

async function selectConversation(convId, title) {
    activeConversationId = convId;
    const titleEl = document.getElementById("active-conv-title");
    const idEl = document.getElementById("active-conv-id");
    const messagesEl = document.getElementById("chat-messages");

    if (titleEl) titleEl.textContent = title || "Active Session";
    if (idEl) idEl.textContent = `Session ID: ${convId.substring(0, 8)}...`;

    // Highlight active session item in sidebar
    document.querySelectorAll(".session-item").forEach(el => {
        el.classList.toggle("active", el.innerHTML.includes(convId));
    });

    if (!messagesEl) return;

    messagesEl.innerHTML = `
        <div style="text-align:center; padding: 30px; color: var(--text-muted); font-size: 0.85rem;">
            Loading verified conversation context...
        </div>
    `;

    try {
        const data = await apiRequest(`/api/genai/conversations/${convId}`);
        messagesEl.replaceChildren();

        if (!data.messages || data.messages.length === 0) {
            messagesEl.innerHTML = `
                <div class="msg-wrapper assistant">
                    <div class="msg-bubble assistant-bubble">
                        <div class="assistant-label-row">
                            <span class="assistant-avatar">🤖</span>
                            <span class="assistant-name">ConsentGuard AI Assistant</span>
                        </div>
                        <div class="ai-response-content">
                            This is a <strong>fresh, isolated conversation session</strong> (<code>${convId.substring(0, 8)}</code>).<br>
                            Previous conversation history is never injected into this context. All prompts are verified against your organization's purpose authorization policy before being sent to the AI model.
                        </div>
                    </div>
                    <div class="msg-meta-bar">
                        <span class="badge badge-ALLOW">ISOLATED CONTEXT VERIFIED</span>
                    </div>
                </div>
            `;
            return;
        }

        data.messages.forEach(msg => {
            renderMessage(msg.role, msg.content, msg.purpose, msg.decision, msg.decision_reason, msg.created_at);
        });
        messagesEl.scrollTop = messagesEl.scrollHeight;
    } catch (err) {
        messagesEl.innerHTML = `
            <div class="alert alert-block">
                Failed to load session history: ${escapeHtml(err.message)}
            </div>
        `;
    }
}

async function deleteConv(convId) {
    if (!confirm("Are you sure you want to permanently delete this conversation session?")) return;
    try {
        await apiRequest(`/api/genai/conversations/${convId}`, { method: "DELETE" });
        if (activeConversationId === convId) activeConversationId = null;
        await loadConversations();
    } catch (err) {
        alert("Could not delete conversation: " + err.message);
    }
}

// ---------------------------------------------------------------------------
// Render Message Bubbles & Policy Enforcement Cards
// ---------------------------------------------------------------------------

function formatAiText(raw) {
    if (!raw) return "";

    // Escape basic HTML
    let safe = escapeHtml(raw);

    // Markdown code blocks
    safe = safe.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
        return `<pre class="chat-code-block"><code class="language-${lang}">${code.trim()}</code></pre>`;
    });

    // Inline code `code`
    safe = safe.replace(/`([^`]+)`/g, `<code class="chat-inline-code">$1</code>`);

    // Bold **text**
    safe = safe.replace(/\*\*([^*]+)\*\*/g, `<strong>$1</strong>`);

    // Italics *text*
    safe = safe.replace(/\*([^*]+)\*/g, `<em>$1</em>`);

    // Headings ### Title
    safe = safe.replace(/^### (.*$)/gim, `<h4 class="chat-heading">$1</h4>`);
    safe = safe.replace(/^## (.*$)/gim, `<h3 class="chat-heading">$1</h3>`);

    // Bullet points
    safe = safe.replace(/^\s*-\s+(.*$)/gim, `<li>$1</li>`);
    safe = safe.replace(/(<li>.*<\/li>)/s, `<ul class="chat-bullet-list">$1</ul>`);

    // Line breaks to <br> if not inside pre
    const parts = safe.split(/(<pre[\s\S]*?<\/pre>)/);
    for (let i = 0; i < parts.length; i++) {
        if (!parts[i].startsWith("<pre")) {
            parts[i] = parts[i].replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
        }
    }
    return `<p>${parts.join("")}</p>`.replace(/<p><\/p>/g, "");
}

function renderMessage(role, text, purpose, decision, reason, timestamp, providerSource, providerLabel) {
    const messagesEl = document.getElementById("chat-messages");
    if (!messagesEl) return;

    const wrapper = document.createElement("div");
    wrapper.className = `msg-wrapper ${role}`;

    let metaHtml = "";
    let contentHtml = "";

    const formattedTime = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Just now";

    if (role === "user") {
        contentHtml = `<div class="msg-bubble user-bubble">${escapeHtml(text)}</div>`;
        metaHtml = `
            <div class="msg-meta-bar">
                <span class="badge badge-neutral" style="font-size:0.72rem;">Declared Purpose: ${escapeHtml(purpose || "General")}</span>
                <span>${formattedTime}</span>
            </div>
        `;
    } else {
        const dec = decision || "ALLOW";
        let securityStatusHtml = "";

        if (dec === "WARN") {
            securityStatusHtml = `
                <div class="security-status-strip WARN">
                    <div class="security-strip-header">
                        <span class="security-strip-badge WARN">⚠️ SECURITY GATEKEEPER: WARN</span>
                        <span class="security-strip-egress">🔒 Zero Model Egress: WITHHELD</span>
                    </div>
                    <div class="security-strip-reason">${escapeHtml(reason || "Potential Purpose Conflict: Secondary use requires review.")}</div>
                </div>
            `;
            contentHtml = `
                ${securityStatusHtml}
                <div class="msg-bubble assistant-bubble restricted-bubble">
                    <div class="assistant-label-row">
                        <span class="assistant-avatar">🔒</span>
                        <span class="assistant-name">ConsentGuard Policy Enforcement</span>
                    </div>
                    <div class="ai-restricted-notice">
                        <p><strong>Restricted Data Withheld from AI Provider:</strong></p>
                        <p style="margin-bottom: 0;">${escapeHtml(text)}</p>
                    </div>
                </div>
            `;
            metaHtml = `
                <div class="msg-meta-bar">
                    <span class="badge badge-${dec}">${dec}</span>
                    <span class="badge badge-provider badge-provider-withheld">Zero Model Egress</span>
                    <span>${formattedTime}</span>
                </div>
            `;
        } else if (dec === "BLOCK") {
            securityStatusHtml = `
                <div class="security-status-strip BLOCK">
                    <div class="security-strip-header">
                        <span class="security-strip-badge BLOCK">🚫 SECURITY GATEKEEPER: BLOCK</span>
                        <span class="security-strip-egress">🔒 Zero Model Egress: BLOCKED</span>
                    </div>
                    <div class="security-strip-reason">${escapeHtml(reason || "Policy strictly prohibits reusing this confidential data for the requested purpose.")}</div>
                </div>
            `;
            contentHtml = `
                ${securityStatusHtml}
                <div class="msg-bubble assistant-bubble restricted-bubble">
                    <div class="assistant-label-row">
                        <span class="assistant-avatar">🚫</span>
                        <span class="assistant-name">ConsentGuard Gatekeeper</span>
                    </div>
                    <div class="ai-restricted-notice">
                        <p><strong>Access Denied by Policy Engine:</strong></p>
                        <p style="margin-bottom: 0;">${escapeHtml(text)}</p>
                    </div>
                </div>
            `;
            metaHtml = `
                <div class="msg-meta-bar">
                    <span class="badge badge-${dec}">${dec}</span>
                    <span class="badge badge-provider badge-provider-withheld">Zero Model Egress</span>
                    <span>${formattedTime}</span>
                </div>
            `;
        } else {
            // Authorized (ALLOW) -> Prominent separate Security Status and real AI Answer content
            let provSource = providerSource;
            let provLabel = providerLabel;

            if (!provLabel && reason && reason.includes("| Provider: ")) {
                const parts = reason.split("| Provider: ");
                provLabel = parts[1].trim();
                const lower = provLabel.toLowerCase();
                if (lower.includes("openai")) {
                    provSource = "openai";
                } else if (lower.includes("fallback")) {
                    provSource = "local_fallback";
                } else if (lower.includes("mock")) {
                    provSource = "mock";
                }
            }

            if (!provSource) provSource = "mock";
            if (!provLabel) {
                provLabel = (provSource === "openai" ? "OpenAI" : provSource === "local_fallback" ? "Local Fallback Engine" : "Local Mock Provider");
            }

            let cleanReason = reason || "Request matches authorized purpose and policy rules.";
            if (cleanReason.includes(" | Provider: ")) {
                cleanReason = cleanReason.split(" | Provider: ")[0].trim();
            }

            let egressHtml = "";
            let pillHtml = "";

            if (provSource === "openai") {
                egressHtml = `<span class="security-strip-egress provider-openai">🌐 OpenAI Egress: ${escapeHtml(provLabel)}</span>`;
                pillHtml = `<span class="provider-pill openai" title="Live OpenAI API Model Response">🌐 ${escapeHtml(provLabel)}</span>`;
            } else if (provSource === "local_fallback") {
                egressHtml = `<span class="security-strip-egress provider-fallback">⚡ Provider: ${escapeHtml(provLabel)}</span>`;
                pillHtml = `<span class="provider-pill fallback" title="Generated by Local Intelligent Fallback Engine (OpenAI Quota/Offline)">⚡ ${escapeHtml(provLabel)}</span>`;
            } else {
                egressHtml = `<span class="security-strip-egress provider-mock">🧪 Provider: ${escapeHtml(provLabel)}</span>`;
                pillHtml = `<span class="provider-pill mock" title="Generated by Local Mock Provider (Dev / Test Mode)">🧪 ${escapeHtml(provLabel)}</span>`;
            }

            securityStatusHtml = `
                <div class="security-status-strip ALLOW">
                    <div class="security-strip-header">
                        <span class="security-strip-badge ALLOW">🛡️ SECURITY GATEKEEPER: ALLOW</span>
                        ${egressHtml}
                    </div>
                    <div class="security-strip-reason">${escapeHtml(cleanReason)}</div>
                </div>
            `;
            contentHtml = `
                ${securityStatusHtml}
                <div class="msg-bubble assistant-bubble">
                    <div class="assistant-label-row">
                        <span class="assistant-avatar">🤖</span>
                        <span class="assistant-name">AI Assistant</span>
                        ${pillHtml}
                    </div>
                    <div class="ai-response-content">
                        ${formatAiText(text)}
                    </div>
                </div>
            `;

            metaHtml = `
                <div class="msg-meta-bar">
                    <span class="badge badge-${dec}">${dec}</span>
                    <span class="badge badge-provider badge-provider-${provSource}">${escapeHtml(provLabel)}</span>
                    <span>${formattedTime}</span>
                </div>
            `;
        }
    }

    wrapper.innerHTML = contentHtml + metaHtml;
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
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

// ---------------------------------------------------------------------------
// Composer Form Handler
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const promptInput = document.getElementById("prompt-input");
    const btnSend = document.getElementById("btn-send-message");
    const statusText = document.getElementById("chat-status");
    const btnNewChat = document.getElementById("btn-new-chat");

    if (btnNewChat) {
        btnNewChat.addEventListener("click", startNewConversation);
    }

    if (promptInput) {
        promptInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (chatForm) chatForm.dispatchEvent(new Event("submit"));
            }
        });
    }

    if (chatForm) {
        chatForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const prompt = promptInput.value.trim();
            const purpose = getEffectivePurpose();
            const trackCheckbox = document.getElementById("track-record-checkbox");
            const trackRecord = trackCheckbox ? trackCheckbox.checked : false;

            if (!prompt) return;

            // Render user message bubble
            renderMessage("user", prompt, purpose, null, null, new Date());
            promptInput.value = "";
            if (btnSend) btnSend.disabled = true;
            if (statusText) statusText.textContent = "Verifying prompt against tracked records and purpose policies...";

            try {
                const result = await apiRequest("/api/genai/generate", {
                    method: "POST",
                    body: JSON.stringify({
                        conversation_id: activeConversationId,
                        prompt: prompt,
                        purpose: purpose,
                        data_category: "Confidential",
                        track_as_record: trackRecord,
                        record_title: prompt.substring(0, 36) + "...",
                        data_classification: "Confidential"
                    })
                });

                // Auto-title conversation if new
                const titleEl = document.getElementById("active-conv-title");
                if (titleEl && (titleEl.textContent === "New Conversation" || titleEl.textContent === "Active Session")) {
                    const cleanTitle = prompt.substring(0, 26).trim() + "...";
                    titleEl.textContent = cleanTitle;
                    if (result.conversation_id) {
                        try {
                            await apiRequest(`/api/genai/conversations/${result.conversation_id}`, {
                                method: "PATCH",
                                body: JSON.stringify({ title: cleanTitle })
                            });
                        } catch (renameErr) {
                            // Non-blocking title update
                        }
                    }
                }

                // Update active conversation ID if newly created
                if (result.conversation_id && result.conversation_id !== activeConversationId) {
                    activeConversationId = result.conversation_id;
                    loadConversations();
                }

                // Render assistant response with separate security status and real AI answer
                renderMessage(
                    "assistant",
                    result.response || "No response generated.",
                    purpose,
                    result.decision,
                    result.reason,
                    new Date(),
                    result.provider_source,
                    result.provider_label
                );

                if (statusText) {
                    statusText.textContent = `Completed: Decision ${result.decision}. Provider egress: ${result.sent_to_provider ? "GRANTED" : "BLOCKED (Protected)"}.`;
                }

            } catch (err) {
                renderMessage(
                    "assistant",
                    `Unable to process request: ${err.message}`,
                    purpose,
                    "BLOCK",
                    "Security check failure or session expired.",
                    new Date()
                );
                if (statusText) statusText.textContent = "Request terminated for security.";
            } finally {
                if (btnSend) btnSend.disabled = false;
                promptInput.focus();
            }
        });
    }

    loadConversations();
});
