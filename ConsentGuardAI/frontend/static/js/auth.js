document.addEventListener("DOMContentLoaded", () => {
    // Registration form
    const registerForm = document.getElementById("register-form");

    if (registerForm) {
        registerForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;

            showMessage("register-message", "Creating your account...");

            try {
                const result = await apiRequest("/auth/register", {
                    method: "POST",
                    body: JSON.stringify({ email, password })
                });

                showMessage(
                    "register-message",
                    result.message || "Registration successful!"
                );

                registerForm.reset();

                // Go to login after a short pause
                setTimeout(() => {
                    window.location.href = "/login";
                }, 1200);
            } catch (error) {
                showMessage("register-message", error.message, true);
            }
        });
    }

    // Login form
    const loginForm = document.getElementById("login-form");

    if (loginForm) {
        loginForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;

            showMessage("login-message", "Logging in...");

            try {
                const result = await apiRequest("/auth/login", {
                    method: "POST",
                    body: JSON.stringify({ email, password })
                });

                showMessage(
                    "login-message",
                    result.message || "Login successful!"
                );

                loginForm.reset();

                // Go to the homepage after successful login
                setTimeout(() => {
                    window.location.href = "/";
                }, 1200);
            } catch (error) {
                showMessage("login-message", error.message, true);
            }
        });
    }
});
