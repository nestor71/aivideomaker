// Auth management
class AuthManager {
    constructor() {
        this.currentUser = null;
        this.stripe = null;
        this.initializeStripe();
        this.checkAuthStatus();
    }

    async initializeStripe() {
        if (typeof Stripe !== 'undefined') {
            // In production, you'd get this from your config
            this.stripe = Stripe('pk_test_YOUR_STRIPE_PUBLISHABLE_KEY');
        }
    }

    async checkAuthStatus() {
        try {
            const response = await fetch('/api/auth/check-auth', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.authenticated) {
                    this.setUser(data.user);
                } else {
                    this.clearUser();
                }
            }
        } catch (error) {
            console.error('Error checking auth status:', error);
            this.clearUser();
        }
    }

    setUser(user) {
        this.currentUser = user;
        this.updateUI();
    }

    clearUser() {
        this.currentUser = null;
        this.updateUI();
    }

    updateUI() {
        const authButtons = document.getElementById('authButtons');
        const userMenu = document.getElementById('userMenu');
        const userName = document.getElementById('userName');
        const userTier = document.getElementById('userTier');
        const userAvatar = document.getElementById('userAvatar');
        const upgradeLink = document.getElementById('upgradeLink');

        if (this.currentUser) {
            // Show user menu, hide auth buttons
            authButtons.style.display = 'none';
            userMenu.style.display = 'block';

            // Update user info
            userName.textContent = this.currentUser.full_name || this.currentUser.email;
            
            // Update tier badge
            if (this.currentUser.subscription_tier === 'premium') {
                userTier.textContent = 'Premium';
                userTier.className = 'badge bg-warning ms-2';
                upgradeLink.style.display = 'none';
            } else {
                userTier.textContent = 'Free';
                userTier.className = 'badge bg-secondary ms-2';
                upgradeLink.style.display = 'block';
            }

            // Update avatar
            if (this.currentUser.avatar_url) {
                userAvatar.src = this.currentUser.avatar_url;
                userAvatar.style.display = 'block';
                document.getElementById('userIcon').style.display = 'none';
            } else {
                userAvatar.style.display = 'none';
                document.getElementById('userIcon').style.display = 'inline';
            }
        } else {
            // Show auth buttons, hide user menu
            authButtons.style.display = 'flex';
            userMenu.style.display = 'none';
        }
    }

    async login(email, password) {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password }),
                credentials: 'include'
            });

            const data = await response.json();

            if (response.ok) {
                this.setUser(data.user);
                this.hideModals();
                this.showSuccess('Welcome back!');
                return true;
            } else {
                this.showError(data.detail || 'Login failed');
                return false;
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('Login failed');
            return false;
        }
    }

    async signup(userData) {
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(userData),
                credentials: 'include'
            });

            const data = await response.json();

            if (response.ok) {
                this.setUser(data.user);
                this.hideModals();
                this.showSuccess('Welcome to AIVideoMaker!');
                return true;
            } else {
                this.showError(data.detail || 'Registration failed');
                return false;
            }
        } catch (error) {
            console.error('Signup error:', error);
            this.showError('Registration failed');
            return false;
        }
    }

    async logout() {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                credentials: 'include'
            });
            
            this.clearUser();
            this.showSuccess('Logged out successfully');
        } catch (error) {
            console.error('Logout error:', error);
        }
    }

    async startOAuth(provider) {
        try {
            const response = await fetch(`/api/auth/oauth/${provider}/authorize`);
            const data = await response.json();
            
            if (response.ok && data.auth_url) {
                window.location.href = data.auth_url;
            } else {
                this.showError('OAuth initialization failed');
            }
        } catch (error) {
            console.error('OAuth error:', error);
            this.showError('OAuth initialization failed');
        }
    }

    async getDashboardData() {
        try {
            const [subscriptionResponse, usageResponse] = await Promise.all([
                fetch('/api/subscription/current', { credentials: 'include' }),
                fetch('/api/subscription/usage', { credentials: 'include' })
            ]);

            const subscriptionData = subscriptionResponse.ok ? await subscriptionResponse.json() : null;
            const usageData = usageResponse.ok ? await usageResponse.json() : null;

            return { subscription: subscriptionData, usage: usageData };
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            return { subscription: null, usage: null };
        }
    }

    async updateDashboard() {
        const { subscription, usage } = await this.getDashboardData();

        if (usage) {
            // Update usage statistics
            const usageMinutes = document.getElementById('usageMinutes');
            const usageProgressBar = document.getElementById('usageProgressBar');
            const videosProcessed = document.getElementById('videosProcessed');
            const daysRemaining = document.getElementById('daysRemaining');

            const current = usage.current_month_minutes;
            const limit = usage.monthly_limit;
            const percentage = usage.percentage_used;

            usageMinutes.textContent = `${current.toFixed(1)} / ${limit === -1 ? '∞' : limit} min`;
            usageProgressBar.style.width = `${Math.min(percentage, 100)}%`;
            videosProcessed.textContent = usage.recent_usage.length;
            daysRemaining.textContent = usage.days_remaining_in_cycle;

            // Update progress bar color
            if (percentage > 80) {
                usageProgressBar.className = 'progress-bar bg-danger';
            } else if (percentage > 60) {
                usageProgressBar.className = 'progress-bar bg-warning';
            } else {
                usageProgressBar.className = 'progress-bar bg-primary';
            }
        }

        if (subscription) {
            // Update subscription info
            const currentPlan = document.getElementById('currentPlan');
            const nextBilling = document.getElementById('nextBilling');
            const upgradeButton = document.getElementById('upgradeButton');
            const manageButton = document.getElementById('manageButton');

            currentPlan.textContent = subscription.tier.charAt(0).toUpperCase() + subscription.tier.slice(1);
            currentPlan.className = subscription.tier === 'premium' ? 'badge bg-warning' : 'badge bg-secondary';

            if (subscription.current_period_end) {
                const endDate = new Date(subscription.current_period_end);
                nextBilling.textContent = endDate.toLocaleDateString();
                upgradeButton.style.display = subscription.tier === 'free' ? 'block' : 'none';
                manageButton.style.display = subscription.tier === 'premium' ? 'block' : 'none';
            }
        }
    }

    showError(message) {
        // Create toast notification
        this.showToast(message, 'error');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-light bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'primary'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        // Add to toast container
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
        }

        container.appendChild(toast);

        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        // Remove from DOM after hiding
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    hideModals() {
        ['loginModal', 'signupModal', 'authRequiredModal'].forEach(modalId => {
            const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
            if (modal) {
                modal.hide();
            }
        });
    }
}

// Global auth manager
const authManager = new AuthManager();

// Modal functions
function showLoginModal() {
    const modal = new bootstrap.Modal(document.getElementById('loginModal'));
    
    // Apply translations when modal is shown
    document.getElementById('loginModal').addEventListener('shown.bs.modal', function() {
        console.log('Login modal shown, applying translations...');
        console.log('updateUI function available:', typeof updateUI);
        console.log('Current translations:', window.translations);
        if (typeof updateUI === 'function') {
            updateUI(); // Apply current translations
            console.log('UpdateUI called for login modal');
        } else {
            console.error('updateUI function not available!');
        }
    }, { once: true });
    
    modal.show();
}

function showSignupModal() {
    const modal = new bootstrap.Modal(document.getElementById('signupModal'));
    
    // Apply translations when modal is shown
    document.getElementById('signupModal').addEventListener('shown.bs.modal', function() {
        console.log('Signup modal shown, applying translations...');
        console.log('updateUI function available:', typeof updateUI);
        console.log('Current translations:', window.translations);
        if (typeof updateUI === 'function') {
            updateUI(); // Apply current translations
            console.log('UpdateUI called for signup modal');
        } else {
            console.error('updateUI function not available!');
        }
    }, { once: true });
    
    modal.show();
}

function showDashboard() {
    authManager.updateDashboard();
    new bootstrap.Modal(document.getElementById('dashboardModal')).show();
}

function showBilling() {
    // TODO: Implement billing portal
    window.open('/api/subscription/billing-portal', '_blank');
}

function showProfile() {
    // TODO: Implement profile modal
    authManager.showToast('Profile settings coming soon', 'info');
}

function upgradeToPremium() {
    new bootstrap.Modal(document.getElementById('upgradeModal')).show();
}

function switchToSignup() {
    bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
    showSignupModal();
}

function switchToLogin() {
    bootstrap.Modal.getInstance(document.getElementById('signupModal')).hide();
    showLoginModal();
}

function showSignupFromAuth() {
    bootstrap.Modal.getInstance(document.getElementById('authRequiredModal')).hide();
    showSignupModal();
}

function showLoginFromAuth() {
    bootstrap.Modal.getInstance(document.getElementById('authRequiredModal')).hide();
    showLoginModal();
}

function logout() {
    authManager.logout();
}

// OAuth functions
function loginWithOAuth(provider) {
    authManager.startOAuth(provider);
}

function signupWithOAuth(provider) {
    authManager.startOAuth(provider);
}

// Form handlers
document.addEventListener('DOMContentLoaded', function() {
    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;
            
            const loginButton = loginForm.querySelector('button[type="submit"]');
            loginButton.disabled = true;
            loginButton.textContent = 'Signing In...';
            
            const success = await authManager.login(email, password);
            
            loginButton.disabled = false;
            loginButton.textContent = 'Sign In';
            
            if (success) {
                loginForm.reset();
            }
        });
    }

    // Signup form
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                full_name: document.getElementById('signupName').value,
                email: document.getElementById('signupEmail').value,
                password: document.getElementById('signupPassword').value,
                agreed_to_terms: document.getElementById('agreeTos').checked,
                gdpr_consent: document.getElementById('agreePrivacy').checked,
                marketing_consent: document.getElementById('agreeMarketing').checked
            };

            // Validate passwords match
            const password = document.getElementById('signupPassword').value;
            const passwordConfirm = document.getElementById('signupPasswordConfirm').value;
            
            if (password !== passwordConfirm) {
                authManager.showError('Passwords do not match');
                return;
            }
            
            const signupButton = signupForm.querySelector('button[type="submit"]');
            signupButton.disabled = true;
            signupButton.textContent = 'Creating Account...';
            
            const success = await authManager.signup(formData);
            
            signupButton.disabled = false;
            signupButton.textContent = 'Create Account';
            
            if (success) {
                signupForm.reset();
            }
        });
    }
});

// Function to check if user needs to authenticate before processing
async function checkAuthBeforeProcessing() {
    if (!authManager.currentUser) {
        new bootstrap.Modal(document.getElementById('authRequiredModal')).show();
        return false;
    }
    return true;
}

// Stripe integration for premium subscriptions
async function startSubscription(tier) {
    if (!authManager.currentUser) {
        authManager.showError('Please sign in first');
        return;
    }

    if (!authManager.stripe) {
        authManager.showError('Payment system not available');
        return;
    }

    try {
        // Create payment method with Stripe Elements
        // This is a simplified version - in production you'd use Stripe Elements
        const { error, paymentMethod } = await authManager.stripe.createPaymentMethod({
            type: 'card',
            card: {
                // This would be a real card element in production
                number: '4242424242424242',
                exp_month: 12,
                exp_year: 2025,
                cvc: '123'
            }
        });

        if (error) {
            authManager.showError(error.message);
            return;
        }

        // Create subscription
        const response = await fetch('/api/subscription/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tier: tier,
                payment_method_id: paymentMethod.id
            }),
            credentials: 'include'
        });

        const data = await response.json();

        if (response.ok) {
            authManager.showSuccess('Successfully upgraded to Premium!');
            authManager.checkAuthStatus(); // Refresh user data
            bootstrap.Modal.getInstance(document.getElementById('upgradeModal')).hide();
        } else {
            authManager.showError(data.detail || 'Subscription failed');
        }
    } catch (error) {
        console.error('Subscription error:', error);
        authManager.showError('Subscription failed');
    }
}