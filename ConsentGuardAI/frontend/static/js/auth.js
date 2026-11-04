/**
 * ConsentGuardAI - Authentication Controller
 * Manages user registration, login, and secure session establishment.
 */

document.addEventListener("DOMContentLoaded", () => {
    // -----------------------------------------------------------------------
    // Registration Form Handler
    // -----------------------------------------------------------------------
    const registerForm = document.getElementById("register-form");
    const regPasswordInput = document.getElementById("password");
    const regMessageEl = document.getElementById("register-message");

    if (registerForm) {
        // Real-time password length indicator
        if (regPasswordInput && regMessageEl) {
            regPasswordInput.addEventListener("input", () => {
                const len = regPasswordInput.value.length;
                if (len === 0) {
                    regMessageEl.textContent = "";
                } else if (len < 12) {
                    regMessageEl.textContent = `Password length: ${len}/12 characters (minimum 12 required)`;
                    regMessageEl.style.color = "#d97706"; // Amber warning
                } else {
                    regMessageEl.textContent = `✓ Password meets requirements (${len} characters)`;
                    regMessageEl.style.color = "#059669"; // Emerald success
                }
            });
        }

        registerForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const emailInput = document.getElementById("email");
            const submitBtn = registerForm.querySelector("button[type='submit']");
            const email = emailInput ? emailInput.value.trim() : "";
            const password = regPasswordInput ? regPasswordInput.value : "";

            if (!email || !password) {
                showMessage("register-message", "Please enter both email and password.", true);
                return;
            }

            if (password.length < 12) {
                showMessage("register-message", "Password must be at least 12 characters long.", true);
                regPasswordInput.focus();
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<span>⏳</span> Creating Account...`;
            }

            showMessage("register-message", "Creating your account...", false);

            try {
                const result = await apiRequest("/auth/register", {
                    method: "POST",
                    body: JSON.stringify({ email, password })
                });

                showMessage(
                    "register-message",
                    result.message || "Account created! Signing you in...",
                    false
                );

                registerForm.reset();

                // Seamlessly redirect to home/chat since user is now authenticated
                setTimeout(() => {
                    window.location.href = "/";
                }, 800);
            } catch (error) {
                showMessage("register-message", error.message, true);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = "Create Account";
                }
            }
        });
    }

    // -----------------------------------------------------------------------
    // Login Form Handler
    // -----------------------------------------------------------------------
    const loginForm = document.getElementById("login-form");

    if (loginForm) {
        loginForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const emailInput = document.getElementById("email");
            const passwordInput = document.getElementById("password");
            const submitBtn = loginForm.querySelector("button[type='submit']");
            const email = emailInput ? emailInput.value.trim() : "";
            const password = passwordInput ? passwordInput.value : "";

            if (!email || !password) {
                showMessage("login-message", "Please enter both email and password.", true);
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<span>⏳</span> Signing In...`;
            }

            showMessage("login-message", "Verifying credentials...", false);

            try {
                const result = await apiRequest("/auth/login", {
                    method: "POST",
                    body: JSON.stringify({ email, password })
                });

                showMessage(
                    "login-message",
                    result.message || "Signed in successfully!",
                    false
                );

                loginForm.reset();

                // Redirect to dashboard or return URL
                setTimeout(() => {
                    const urlParams = new URLSearchParams(window.location.search);
                    const nextUrl = urlParams.get("next") || "/";
                    window.location.href = nextUrl;
                }, 600);
            } catch (error) {
                showMessage("login-message", error.message, true);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = "Sign In";
                }
            }
        });
    }
});
