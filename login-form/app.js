const form = document.getElementById("login-form");
const errorEl = document.getElementById("form-error");
const passwordInput = document.getElementById("password");
const toggleBtn = document.getElementById("toggle-password");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function clearError() {
  errorEl.textContent = "";
  errorEl.hidden = true;
}

toggleBtn.addEventListener("click", () => {
  const isHidden = passwordInput.type === "password";
  passwordInput.type = isHidden ? "text" : "password";
  toggleBtn.setAttribute("aria-pressed", String(isHidden));
  toggleBtn.setAttribute(
    "aria-label",
    isHidden ? "Hide password" : "Show password"
  );
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearError();

  const data = new FormData(form);
  const email = String(data.get("email") || "").trim();
  const password = String(data.get("password") || "");

  if (!email || !password) {
    showError("Please enter your email and password.");
    return;
  }

  console.log("Login attempt", { email });
  alert("Demo: form is valid. Connect this to your sign-in API.");
});

document.querySelectorAll(".social__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    console.log("Social sign-in:", btn.getAttribute("aria-label"));
    alert("Demo: wire this button to your OAuth provider.");
  });
});
