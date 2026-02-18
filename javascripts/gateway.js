/**
 * TRXO Gateway Logic
 * 
 * Implements a "soft gateway" using Local Storage.
 * - Handles MkDocs Material "instant" navigation (SPA-like transitions).
 * - Redirects unauthorized users to the landing page (Gateway).
 * - Redirects authorized users away from landing page to Dashboard/Home.
 */

(function () {
    const ACCESS_KEY = 'trxo_access_granted';

    // Config: Define what URLs are considered "Gateway" vs "Content"
    // We check against potential root paths for both Localhost and GitHub Pages
    const GATEWAY_PATHS = ['/trxo/', '/trxo/index.html', '/', '/index.html'];

    // Redirect Targets
    // For production (GitHub Pages) usually /trxo/home/
    // For localhost usually /home/
    // We attempt to detect the base to make it robust
    function getDashboardPath() {
        const path = window.location.pathname;
        if (path.startsWith('/trxo')) {
            return '/trxo/home/';
        }
        return '/home/';
    }

    function getGatewayPath() {
        const path = window.location.pathname;
        if (path.startsWith('/trxo')) {
            return '/trxo/';
        }
        return '/';
    }

    // Helper: Check if current URL is the gateway
    function isGatewayPage() {
        const path = window.location.pathname;
        // Check exact match or trailing slash variations
        return GATEWAY_PATHS.some(p => path === p || path === p.slice(0, -1));
    }

    // Main Security Check
    function enforceAccess() {
        const hasAccess = localStorage.getItem(ACCESS_KEY) === 'true';
        const onGateway = isGatewayPage();

        // Debugging (Uncomment if needed)
        // console.log(`Path: ${window.location.pathname}, Access: ${hasAccess}, onGateway: ${onGateway}`);

        if (hasAccess) {
            // User is Authorized
            if (onGateway) {
                // If on Gateway, redirect to Content
                window.location.replace(getDashboardPath());
            }
        } else {
            // User is Unauthorized
            if (!onGateway) {
                // If trying to access internal content, Bounce to Gateway
                window.location.replace(getGatewayPath());
            } else {
                // We are on the Gateway and Unauthorized.
                // 1. Initialize Form Listener (since DOM might have just refreshed)
                initFormObserver();

                // 2. Aggressively hide UI elements via JS as a backup to CSS
                // This ensures that even if CSS is slow, we remove the nav
                const header = document.querySelector('.md-header');
                const tabs = document.querySelector('.md-tabs');
                if (header) header.style.display = 'none';
                if (tabs) tabs.style.display = 'none';
            }
        }
    }

    /**
     * Watches the Brevo form for successful submission.
     */
    function initFormObserver() {
        // Disconnect previous observers if any (though logic runs on page transition)
        // We'll just instantiate a new one for the current document context

        const observer = new MutationObserver(function (mutations) {
            const successMsg = document.getElementById('success-message');

            if (successMsg && successMsg.style.display !== 'none' && successMsg.offsetParent !== null) {
                // Grant Access
                localStorage.setItem(ACCESS_KEY, 'true');

                // UX Update
                const container = document.querySelector('.gateway-container');
                if (container) {
                    container.innerHTML = '<h2>Success! Redirecting to documentation...</h2>';
                }

                // Redirect
                setTimeout(function () {
                    window.location.replace(getDashboardPath());
                }, 1500);
            }
        });

        const formContainer = document.getElementById('sib-form-container');
        if (formContainer) {
            observer.observe(formContainer, {
                attributes: true,
                childList: true,
                subtree: true,
                attributeFilter: ['style', 'class']
            });
        }
    }

    // Initialize Logic
    // We subscribe to MkDocs Material's document$ observable to handle instant navigation
    if (window.document$) {
        window.document$.subscribe(function () {
            enforceAccess();
        });
    } else {
        // Fallback for standard loading
        document.addEventListener("DOMContentLoaded", enforceAccess);
        // Also run immediately in case we are late
        enforceAccess();
    }

})();
