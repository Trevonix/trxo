/**
 * Email Validation Logic
 * 
 * Blocks personal email domains (Gmail, Yahoo, Hotmail) from being submitted.
 */

(function () {
    function initEmailValidation() {
        const form = document.getElementById("sib-form");
        if (!form) return;

        // Reset initialization flag if form is re-rendered but id remains
        form.removeEventListener("submit", validateEmail, true);

        // Use capture phase (true) to intercept before other handlers
        form.addEventListener("submit", validateEmail, true);

        // Also attach to the button click just in case
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.removeEventListener("click", validateEmailClick, true);
            submitBtn.addEventListener("click", validateEmailClick, true);
        }

        // Add input listener to clear error when user types
        const emailInput = document.getElementById("EMAIL");
        if (emailInput) {
            emailInput.addEventListener("input", function () {
                const errorLabel = document.getElementById("email-error");
                if (errorLabel) errorLabel.style.display = "none";
                this.style.border = "1px solid #13ce66"; // Restore default or success border
            });
        }
    }

    function validateEmail(e) {
        if (!processValidation(e)) {
            e.preventDefault();
            e.stopImmediatePropagation(); // Stop other listeners
            return false;
        }
    }

    function validateEmailClick(e) {
        if (!processValidation(e)) {
            e.preventDefault();
            e.stopImmediatePropagation();
            return false;
        }
    }

    function processValidation(e) {
        const emailInput = document.getElementById("EMAIL");
        const errorLabel = document.getElementById("email-error");

        if (!emailInput) return true;

        const blockedDomains = ["gmail.com", "yahoo.com", "hotmail.com"];
        const emailValue = emailInput.value.trim().toLowerCase();

        // Simple domain extraction
        const parts = emailValue.split('@');
        if (parts.length < 2) return true; // Let browser validation handle invalid email format

        const domain = parts[parts.length - 1];

        if (blockedDomains.includes(domain)) {
            if (errorLabel) {
                // Ensure text is set and correct
                errorLabel.innerText = "Please use your business email address. Gmail, Yahoo and Hotmail are not allowed.";
                errorLabel.style.display = "block";
            }
            emailInput.style.border = "1px solid #ff4949";
            return false;
        } else {
            if (errorLabel) errorLabel.style.display = "none";
            emailInput.style.border = "1px solid #13ce66";
            return true;
        }
    }

    // Support for MkDocs Material instant loading
    if (window.document$) {
        window.document$.subscribe(function () {
            setTimeout(initEmailValidation, 100);
        });
    }

    // Standard load
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initEmailValidation);
    } else {
        initEmailValidation();
    }
})();
