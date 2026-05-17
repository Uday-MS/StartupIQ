/* ==========================================================================
   AUTH.JS — Authentication modal, form handling, user menu, save startups,
             recommendations, forgot password, show/hide password,
             password policy validation, email verification
   ========================================================================== */

// =============================================================================
// PASSWORD TOGGLE — Show/hide password fields
// =============================================================================

function togglePasswordField(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.classList.add('active');
    } else {
        input.type = 'password';
        btn.classList.remove('active');
    }
}


// =============================================================================
// PASSWORD POLICY — Real-time strength checker
// =============================================================================

var _PW_RULES = [
    { id: 'length',    regex: /.{8,}/,              label: 'At least 8 characters' },
    { id: 'uppercase', regex: /[A-Z]/,              label: 'At least 1 uppercase letter' },
    { id: 'lowercase', regex: /[a-z]/,              label: 'At least 1 lowercase letter' },
    { id: 'number',    regex: /[0-9]/,              label: 'At least 1 number' },
    { id: 'special',   regex: /[!@#$%^&*()_+\-=]/, label: 'At least 1 special character' },
];

/**
 * Check password against policy rules.
 * @returns {string[]} Array of failed rule labels (empty = all passed)
 */
function _checkPasswordPolicy(password) {
    var failures = [];
    _PW_RULES.forEach(function (rule) {
        if (!rule.regex.test(password)) {
            failures.push(rule.label.toLowerCase());
        }
    });
    return failures;
}

/**
 * Update a password policy checklist UI in real-time.
 * @param {string} password - Current password value
 * @param {string} containerId - ID of the .pw-policy-checklist container
 */
function _updatePolicyChecklist(password, containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    _PW_RULES.forEach(function (rule) {
        var el = container.querySelector('[data-rule="' + rule.id + '"]');
        if (!el) return;
        var icon = el.querySelector('.pw-rule-icon');
        var passed = rule.regex.test(password);

        if (passed) {
            el.classList.add('pw-rule-pass');
            el.classList.remove('pw-rule-fail');
            if (icon) icon.textContent = '\u2713';  // checkmark
        } else {
            el.classList.remove('pw-rule-pass');
            el.classList.add('pw-rule-fail');
            if (icon) icon.textContent = '\u25cb';  // circle
        }
    });
}

// Wire up real-time checklist for signup password field
document.addEventListener('DOMContentLoaded', function () {
    var signupPw = document.getElementById('signupPassword');
    if (signupPw) {
        signupPw.addEventListener('input', function () {
            _updatePolicyChecklist(signupPw.value, 'signupPwPolicy');
        });
    }

    // Also wire for reset password page (if present)
    var resetPw = document.getElementById('resetPassword');
    if (resetPw) {
        resetPw.addEventListener('input', function () {
            _updatePolicyChecklist(resetPw.value, 'resetPwPolicy');
        });
    }
});


// =============================================================================
// AUTH MODAL: Open / Close
// =============================================================================

/**
 * Open the auth modal with a specific tab active.
 * @param {'login'|'signup'} tab - Which tab to show
 */
function openAuthModal(tab) {
    const overlay = document.getElementById('authModalOverlay');
    const modal = document.getElementById('authModal');
    if (!overlay || !modal) return;

    // Reset forms and errors
    document.getElementById('loginForm').reset();
    document.getElementById('signupForm').reset();
    document.getElementById('loginError').textContent = '';
    document.getElementById('signupError').textContent = '';
    document.getElementById('loginError').style.display = 'none';
    document.getElementById('signupError').style.display = 'none';

    // Hide success state, show forms
    const successEl = document.getElementById('authSuccess');
    if (successEl) successEl.style.display = 'none';

    // Hide forgot password form, show main forms
    _hideForgotForm();

    // Show the correct tab
    switchAuthTab(tab || 'login');

    // Show overlay
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Focus first input after animation
    setTimeout(function () {
        const activeForm = tab === 'signup' ? 'signupUsername' : 'loginEmail';
        const input = document.getElementById(activeForm);
        if (input) input.focus();
    }, 350);
}


/**
 * Close the auth modal.
 */
function closeAuthModal() {
    const overlay = document.getElementById('authModalOverlay');
    if (!overlay) return;

    overlay.classList.remove('active');
    document.body.style.overflow = '';
}


// Close on overlay click (outside modal)
document.addEventListener('DOMContentLoaded', function () {
    const overlay = document.getElementById('authModalOverlay');
    const modal = document.getElementById('authModal');
    const closeBtn = document.getElementById('authModalClose');

    if (overlay) {
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeAuthModal();
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeAuthModal);
    }

    // ESC key closes modal
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAuthModal();
    });
});


// =============================================================================
// TAB SWITCHING
// =============================================================================

function switchAuthTab(tab) {
    const loginTab = document.getElementById('authTabLogin');
    const signupTab = document.getElementById('authTabSignup');
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');
    const indicator = document.getElementById('authTabIndicator');

    if (!loginTab || !signupTab || !loginForm || !signupForm) return;

    // Clear error messages
    document.getElementById('loginError').textContent = '';
    document.getElementById('loginError').style.display = 'none';
    document.getElementById('signupError').textContent = '';
    document.getElementById('signupError').style.display = 'none';

    if (tab === 'signup') {
        loginTab.classList.remove('active');
        signupTab.classList.add('active');
        loginForm.style.display = 'none';
        signupForm.style.display = 'flex';
        if (indicator) indicator.style.transform = 'translateX(100%)';
    } else {
        signupTab.classList.remove('active');
        loginTab.classList.add('active');
        signupForm.style.display = 'none';
        loginForm.style.display = 'flex';
        if (indicator) indicator.style.transform = 'translateX(0)';
    }
}

// Tab click handlers
document.addEventListener('DOMContentLoaded', function () {
    const loginTab = document.getElementById('authTabLogin');
    const signupTab = document.getElementById('authTabSignup');

    if (loginTab) loginTab.addEventListener('click', function () { switchAuthTab('login'); });
    if (signupTab) signupTab.addEventListener('click', function () { switchAuthTab('signup'); });
});


// =============================================================================
// FORM SUBMISSIONS — Login & Signup via fetch()
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {

    // --- LOGIN FORM ---
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const email = document.getElementById('loginEmail').value.trim();
            const password = document.getElementById('loginPassword').value;
            const errorEl = document.getElementById('loginError');
            const submitBtn = document.getElementById('loginSubmitBtn');
            const submitText = submitBtn.querySelector('.auth-submit-text');
            const submitLoader = submitBtn.querySelector('.auth-submit-loader');

            // Clear previous error
            errorEl.textContent = '';
            errorEl.style.display = 'none';

            // Show loading
            submitBtn.disabled = true;
            submitText.textContent = 'Signing in...';
            submitLoader.style.display = 'inline-block';

            fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            })
                .then(function (res) { return res.json().then(function (data) { return { status: res.status, data }; }); })
                .then(function (result) {
                    submitBtn.disabled = false;
                    submitText.textContent = 'Login';
                    submitLoader.style.display = 'none';

                    if (result.data.success) {
                        showAuthSuccess(result.data.message || 'Welcome back!', result.data.user.username);
                    } else {
                        errorEl.textContent = result.data.error || 'Login failed';
                        errorEl.style.display = 'block';
                    }
                })
                .catch(function (err) {
                    submitBtn.disabled = false;
                    submitText.textContent = 'Login';
                    submitLoader.style.display = 'none';
                    errorEl.textContent = 'Network error. Please try again.';
                    errorEl.style.display = 'block';
                });
        });
    }

    // --- SIGNUP FORM ---
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const username = document.getElementById('signupUsername').value.trim();
            const email = document.getElementById('signupEmail').value.trim();
            const password = document.getElementById('signupPassword').value;
            const errorEl = document.getElementById('signupError');
            const submitBtn = document.getElementById('signupSubmitBtn');
            const submitText = submitBtn.querySelector('.auth-submit-text');
            const submitLoader = submitBtn.querySelector('.auth-submit-loader');

            // Clear previous error
            errorEl.textContent = '';
            errorEl.style.display = 'none';

            // Client-side validation
            if (username.length < 2) {
                errorEl.textContent = 'Username must be at least 2 characters';
                errorEl.style.display = 'block';
                return;
            }

            // Strong password policy
            var pwErrors = _checkPasswordPolicy(password);
            if (pwErrors.length > 0) {
                errorEl.textContent = 'Password requires: ' + pwErrors.join(', ');
                errorEl.style.display = 'block';
                return;
            }

            // Show loading
            submitBtn.disabled = true;
            submitText.textContent = 'Creating account...';
            submitLoader.style.display = 'inline-block';

            fetch('/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password }),
            })
                .then(function (res) { return res.json().then(function (data) { return { status: res.status, data }; }); })
                .then(function (result) {
                    submitBtn.disabled = false;
                    submitText.textContent = 'Create Account';
                    submitLoader.style.display = 'none';

                    if (result.data.success) {
                        showAuthSuccess('Account created!', result.data.user.username);
                    } else {
                        errorEl.textContent = result.data.error || 'Signup failed';
                        errorEl.style.display = 'block';
                    }
                })
                .catch(function (err) {
                    submitBtn.disabled = false;
                    submitText.textContent = 'Create Account';
                    submitLoader.style.display = 'none';
                    errorEl.textContent = 'Network error. Please try again.';
                    errorEl.style.display = 'block';
                });
        });
    }
});


// =============================================================================
// AUTH SUCCESS STATE — Show success and reload
// =============================================================================

function showAuthSuccess(message, username) {
    // Hide forms
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');
    const divider = document.querySelector('.auth-divider');
    const googleBtn = document.getElementById('googleAuthBtn');
    const tabs = document.getElementById('authTabs');
    const forgotForm = document.getElementById('forgotPasswordForm');

    if (loginForm) loginForm.style.display = 'none';
    if (signupForm) signupForm.style.display = 'none';
    if (divider) divider.style.display = 'none';
    if (googleBtn) googleBtn.style.display = 'none';
    if (tabs) tabs.style.display = 'none';
    if (forgotForm) forgotForm.style.display = 'none';

    // Show success
    const successEl = document.getElementById('authSuccess');
    const successTitle = document.getElementById('authSuccessTitle');
    const successMsg = document.getElementById('authSuccessMsg');

    if (successTitle) successTitle.textContent = 'Welcome, ' + username + '!';
    if (successMsg) successMsg.textContent = message;
    if (successEl) successEl.style.display = 'flex';

    // Reload after brief success display
    setTimeout(function () {
        window.location.reload();
    }, 1200);
}


// =============================================================================
// GOOGLE AUTH — Real OAuth redirect
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    const googleBtn = document.getElementById('googleAuthBtn');
    if (googleBtn) {
        googleBtn.addEventListener('click', function () {
            // Redirect to Google OAuth login
            window.location.href = '/auth/google/login';
        });
    }
});


// =============================================================================
// FORGOT PASSWORD — Show form, submit email, send reset link
// =============================================================================

function _showForgotForm() {
    var loginForm = document.getElementById('loginForm');
    var signupForm = document.getElementById('signupForm');
    var divider = document.querySelector('.auth-divider');
    var googleBtn = document.getElementById('googleAuthBtn');
    var tabs = document.getElementById('authTabs');
    var forgotForm = document.getElementById('forgotPasswordForm');

    if (loginForm) loginForm.style.display = 'none';
    if (signupForm) signupForm.style.display = 'none';
    if (divider) divider.style.display = 'none';
    if (googleBtn) googleBtn.style.display = 'none';
    if (tabs) tabs.style.display = 'none';
    if (forgotForm) forgotForm.style.display = 'flex';

    // Reset forgot form state
    var forgotError = document.getElementById('forgotError');
    var forgotSuccess = document.getElementById('forgotSuccess');
    if (forgotError) { forgotError.textContent = ''; forgotError.style.display = 'none'; }
    if (forgotSuccess) { forgotSuccess.textContent = ''; forgotSuccess.style.display = 'none'; }

    setTimeout(function () {
        var emailInput = document.getElementById('forgotEmail');
        if (emailInput) emailInput.focus();
    }, 200);
}

function _hideForgotForm() {
    var forgotForm = document.getElementById('forgotPasswordForm');
    var divider = document.querySelector('.auth-divider');
    var googleBtn = document.getElementById('googleAuthBtn');
    var tabs = document.getElementById('authTabs');

    if (forgotForm) forgotForm.style.display = 'none';
    if (divider) divider.style.display = 'flex';
    if (googleBtn) googleBtn.style.display = 'flex';
    if (tabs) tabs.style.display = 'flex';
}

document.addEventListener('DOMContentLoaded', function () {
    // "Forgot password?" link
    var forgotLink = document.getElementById('forgotPasswordLink');
    if (forgotLink) {
        forgotLink.addEventListener('click', function (e) {
            e.preventDefault();
            _showForgotForm();
        });
    }

    // "Back" button in forgot form
    var forgotBackBtn = document.getElementById('forgotBackBtn');
    if (forgotBackBtn) {
        forgotBackBtn.addEventListener('click', function () {
            _hideForgotForm();
            switchAuthTab('login');
        });
    }

    // Forgot password form submission
    var forgotForm = document.getElementById('forgotPasswordForm');
    if (forgotForm) {
        forgotForm.addEventListener('submit', function (e) {
            e.preventDefault();

            var email = document.getElementById('forgotEmail').value.trim();
            var errorEl = document.getElementById('forgotError');
            var successEl = document.getElementById('forgotSuccess');
            var submitBtn = document.getElementById('forgotSubmitBtn');
            var submitText = submitBtn.querySelector('.auth-submit-text');
            var submitLoader = submitBtn.querySelector('.auth-submit-loader');

            errorEl.textContent = '';
            errorEl.style.display = 'none';
            successEl.textContent = '';
            successEl.style.display = 'none';

            if (!email || email.indexOf('@') === -1) {
                errorEl.textContent = 'Please enter a valid email address';
                errorEl.style.display = 'block';
                return;
            }

            submitBtn.disabled = true;
            submitText.textContent = 'Sending...';
            submitLoader.style.display = 'inline-block';

            fetch('/forgot-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email }),
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                submitBtn.disabled = false;
                submitText.textContent = 'Send Reset Link';
                submitLoader.style.display = 'none';

                if (result.data.success) {
                    successEl.textContent = result.data.message || 'Reset link sent!';
                    successEl.style.display = 'block';
                    submitBtn.style.display = 'none';
                } else {
                    errorEl.textContent = result.data.error || 'Something went wrong';
                    errorEl.style.display = 'block';
                }
            })
            .catch(function () {
                submitBtn.disabled = false;
                submitText.textContent = 'Send Reset Link';
                submitLoader.style.display = 'none';
                errorEl.textContent = 'Network error. Please try again.';
                errorEl.style.display = 'block';
            });
        });
    }
});


// =============================================================================
// USER DROPDOWN MENU
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    const userBtn = document.getElementById('navUserBtn');
    const dropdown = document.getElementById('navDropdown');

    if (userBtn && dropdown) {
        userBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            dropdown.classList.toggle('open');
            userBtn.classList.toggle('open');
        });

        // Close dropdown on outside click
        document.addEventListener('click', function () {
            dropdown.classList.remove('open');
            userBtn.classList.remove('open');
        });

        dropdown.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    }

    // --- LOGOUT ---
    const logoutBtn = document.getElementById('navLogoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function (e) {
            e.preventDefault();
            fetch('/logout')
                .then(function (res) { return res.json(); })
                .then(function () {
                    window.location.href = '/';
                });
        });
    }
});


// =============================================================================
// PROTECTED ROUTE INTERCEPT — Open modal instead of navigating
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    const protectedLinks = document.querySelectorAll('.nav-protected');

    protectedLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            openAuthModal('login');
        });
    });
});


// =============================================================================
// SAVE STARTUP — Global helper functions
// =============================================================================

/**
 * Save a startup. Shows login modal if not authenticated.
 */
function saveStartup(name, industry, country, funding, buttonEl) {
    // Check if user is logged in
    fetch('/auth/status')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.logged_in) {
                openAuthModal('login');
                return;
            }

            // User is logged in — save the startup
            buttonEl.disabled = true;
            buttonEl.classList.add('saving');

            fetch('/api/save-startup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    startup_name: name,
                    industry: industry || '',
                    country: country || '',
                    funding: funding || 0,
                }),
            })
            .then(function (r) { return r.json().then(function (d) { return { status: r.status, data: d }; }); })
            .then(function (result) {
                buttonEl.disabled = false;
                buttonEl.classList.remove('saving');

                if (result.data.success) {
                    buttonEl.classList.add('saved');
                    buttonEl.innerHTML = '<span class="save-icon">★</span> Saved';
                    buttonEl.onclick = function () {
                        unsaveStartup(name, buttonEl);
                    };
                    _showToast('Startup saved!', 'success');
                } else if (result.status === 409) {
                    // Already saved
                    buttonEl.classList.add('saved');
                    buttonEl.innerHTML = '<span class="save-icon">★</span> Saved';
                    buttonEl.onclick = function () {
                        unsaveStartup(name, buttonEl);
                    };
                } else if (result.data.login_required) {
                    openAuthModal('login');
                } else {
                    _showToast(result.data.error || 'Failed to save', 'error');
                }
            })
            .catch(function () {
                buttonEl.disabled = false;
                buttonEl.classList.remove('saving');
                _showToast('Network error', 'error');
            });
        });
}

/**
 * Unsave a startup.
 */
function unsaveStartup(name, buttonEl) {
    buttonEl.disabled = true;

    fetch('/api/unsave-startup', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ startup_name: name }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
        buttonEl.disabled = false;
        if (data.success) {
            buttonEl.classList.remove('saved');
            buttonEl.innerHTML = '<span class="save-icon">☆</span> Save';
            buttonEl.onclick = function () {
                saveStartup(name, buttonEl.dataset.industry || '', buttonEl.dataset.country || '', buttonEl.dataset.funding || 0, buttonEl);
            };
            _showToast('Startup removed', 'info');
        }
    })
    .catch(function () {
        buttonEl.disabled = false;
    });
}


// =============================================================================
// TOAST NOTIFICATIONS
// =============================================================================

function _showToast(message, type) {
    // Remove existing toast
    var existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.className = 'toast-notification toast-' + (type || 'info');
    toast.innerHTML = '<span class="toast-icon">' +
        (type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ') +
        '</span><span class="toast-msg">' + message + '</span>';

    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(function () {
        toast.classList.add('toast-visible');
    });

    // Auto-remove
    setTimeout(function () {
        toast.classList.remove('toast-visible');
        setTimeout(function () { toast.remove(); }, 400);
    }, 3000);
}


// =============================================================================
// SAVED STARTUPS PANEL — Opened from user dropdown
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    var savedBtn = document.getElementById('navSavedStartups');
    if (savedBtn) {
        savedBtn.addEventListener('click', function (e) {
            e.preventDefault();
            // Close dropdown
            var dropdown = document.getElementById('navDropdown');
            var userBtn = document.getElementById('navUserBtn');
            if (dropdown) dropdown.classList.remove('open');
            if (userBtn) userBtn.classList.remove('open');

            _openSavedPanel();
        });
    }
});

function _openSavedPanel() {
    // Check if panel already exists
    var existing = document.getElementById('savedStartupsPanel');
    if (existing) existing.remove();

    var panel = document.createElement('div');
    panel.id = 'savedStartupsPanel';
    panel.className = 'saved-panel-overlay';
    panel.innerHTML = `
        <div class="saved-panel">
            <div class="saved-panel-header">
                <h3 class="saved-panel-title">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
                    Saved Startups
                </h3>
                <button class="saved-panel-close" onclick="document.getElementById('savedStartupsPanel').remove()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            <div class="saved-panel-body" id="savedPanelBody">
                <div class="saved-loading">
                    <div class="country-spinner"></div>
                    <span>Loading...</span>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(panel);

    // ESC to close
    panel._escHandler = function (e) {
        if (e.key === 'Escape') {
            panel.remove();
            document.removeEventListener('keydown', panel._escHandler);
        }
    };
    document.addEventListener('keydown', panel._escHandler);

    // Overlay click to close
    panel.addEventListener('click', function (e) {
        if (e.target === panel) panel.remove();
    });

    // Animate in
    requestAnimationFrame(function () {
        panel.classList.add('active');
    });

    // Fetch saved startups
    fetch('/api/saved-startups')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var body = document.getElementById('savedPanelBody');
            if (!body) return;

            if (!data.startups || data.startups.length === 0) {
                body.innerHTML = `
                    <div class="saved-empty">
                        <div class="saved-empty-icon">📌</div>
                        <p>No saved startups yet</p>
                        <span>Save startups from the dashboard or search to see them here.</span>
                    </div>
                `;
                return;
            }

            var html = '<div class="saved-list">';
            data.startups.forEach(function (s) {
                var fundingStr = s.funding >= 1e9
                    ? '$' + (s.funding / 1e9).toFixed(2) + 'B'
                    : s.funding >= 1e6
                        ? '$' + (s.funding / 1e6).toFixed(2) + 'M'
                        : s.funding > 0
                            ? '$' + s.funding.toLocaleString()
                            : '';

                html += `
                    <div class="saved-item" data-id="${s.id}">
                        <div class="saved-item-info">
                            <div class="saved-item-name">${_escHtml(s.startup_name)}</div>
                            <div class="saved-item-meta">
                                ${s.industry ? '<span class="badge badge-industry">' + _escHtml(s.industry) + '</span>' : ''}
                                ${s.country ? '<span class="badge badge-country">' + _escHtml(s.country) + '</span>' : ''}
                                ${fundingStr ? '<span class="saved-item-funding">' + fundingStr + '</span>' : ''}
                            </div>
                        </div>
                        <button class="saved-item-remove" onclick="_removeSavedItem(${s.id}, '${_escHtml(s.startup_name)}', this)" title="Remove">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                        </button>
                    </div>
                `;
            });
            html += '</div>';
            body.innerHTML = html;
        })
        .catch(function () {
            var body = document.getElementById('savedPanelBody');
            if (body) body.innerHTML = '<div class="saved-empty"><p>Failed to load saved startups</p></div>';
        });
}

function _removeSavedItem(id, name, btn) {
    btn.disabled = true;
    fetch('/api/save-startup/' + id, { method: 'DELETE' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                var item = btn.closest('.saved-item');
                if (item) {
                    item.style.opacity = '0';
                    item.style.transform = 'translateX(20px)';
                    setTimeout(function () { item.remove(); }, 300);
                }
                // Also update any save buttons on the page
                _updateSaveButtonsOnPage(name, false);
                _showToast('Startup removed', 'info');
            }
        });
}

function _updateSaveButtonsOnPage(name, isSaved) {
    // Update any save buttons with matching data-name
    document.querySelectorAll('.save-startup-btn[data-name="' + name + '"]').forEach(function (btn) {
        if (isSaved) {
            btn.classList.add('saved');
            btn.innerHTML = '<span class="save-icon">★</span> Saved';
        } else {
            btn.classList.remove('saved');
            btn.innerHTML = '<span class="save-icon">☆</span> Save';
        }
    });
}


// =============================================================================
// RECOMMENDATIONS — Load on home page if logged in
// =============================================================================

function loadRecommendations() {
    var container = document.getElementById('recommendationsContainer');
    if (!container) return;

    fetch('/api/recommendations')
        .then(function (r) {
            if (r.status === 401) {
                container.style.display = 'none';
                return null;
            }
            return r.json();
        })
        .then(function (data) {
            if (!data) return;

            if (!data.recommendations || data.recommendations.length === 0) {
                if (data.message) {
                    container.innerHTML = `
                        <div class="section-header scroll-reveal">
                            <h2 class="section-heading">
                                <span class="section-heading-icon">💡</span>
                                Recommended for You
                            </h2>
                            <p class="section-heading-sub">${data.message}</p>
                        </div>
                    `;
                } else {
                    container.style.display = 'none';
                }
                return;
            }

            var html = `
                <div class="section-header scroll-reveal">
                    <h2 class="section-heading">
                        <span class="section-heading-icon">💡</span>
                        Recommended for You
                    </h2>
                    <p class="section-heading-sub">Based on your saved startups</p>
                </div>
                <div class="recommendations-grid">
            `;

            data.recommendations.forEach(function (s, i) {
                var amount = s["Amount Raised (USD)"];
                var amountStr = amount >= 1e9
                    ? '$' + (amount / 1e9).toFixed(2) + 'B'
                    : amount >= 1e6
                        ? '$' + (amount / 1e6).toFixed(2) + 'M'
                        : '$' + amount.toLocaleString();

                html += `
                    <div class="recommendation-card animate-in" style="animation-delay: ${i * 0.05}s">
                        <div class="rec-card-header">
                            <div class="rec-card-name">${_escHtml(s["Startup Name"])}</div>
                            <button class="save-startup-btn"
                                data-name="${_escHtml(s["Startup Name"])}"
                                data-industry="${_escHtml(s["Industry"])}"
                                data-country="${_escHtml(s["Country"])}"
                                data-funding="${amount}"
                                onclick="saveStartup('${_escJs(s["Startup Name"])}', '${_escJs(s["Industry"])}', '${_escJs(s["Country"])}', ${amount}, this)">
                                <span class="save-icon">☆</span> Save
                            </button>
                        </div>
                        <div class="rec-card-meta">
                            <span class="badge badge-industry">${_escHtml(s["Industry"])}</span>
                            <span class="badge badge-country">${_escHtml(s["Country"])}</span>
                            <span class="badge badge-stage">${_escHtml(s["Funding Stage"])}</span>
                        </div>
                        <div class="rec-card-funding">${amountStr}</div>
                    </div>
                `;
            });

            html += '</div>';
            container.innerHTML = html;
            container.style.display = 'block';

            // Check which ones are already saved
            _markSavedButtons();
        })
        .catch(function () {
            if (container) container.style.display = 'none';
        });
}

/**
 * Check saved startups and mark matching buttons
 */
function _markSavedButtons() {
    fetch('/api/saved-startups')
        .then(function (r) {
            if (r.status === 401) return null;
            return r.json();
        })
        .then(function (data) {
            if (!data || !data.startups) return;

            var savedNames = new Set(data.startups.map(function (s) { return s.startup_name; }));

            document.querySelectorAll('.save-startup-btn').forEach(function (btn) {
                var name = btn.dataset.name;
                if (savedNames.has(name)) {
                    btn.classList.add('saved');
                    btn.innerHTML = '<span class="save-icon">★</span> Saved';
                    btn.onclick = function () { unsaveStartup(name, btn); };
                }
            });
        });
}


// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function _escHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function _escJs(str) {
    if (!str) return '';
    return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}


// =============================================================================
// INIT ON PAGE LOAD
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    // Load recommendations on homepage
    if (document.getElementById('recommendationsContainer')) {
        loadRecommendations();
    }

    // Mark saved buttons on any page (search, index, etc.)
    setTimeout(function () {
        if (document.querySelector('.save-startup-btn')) {
            _markSavedButtons();
        }
    }, 500);
});
