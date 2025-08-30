// Admin Dashboard Management
class AdminDashboard {
    constructor() {
        this.currentPage = 1;
        this.currentFilters = {
            search: '',
            tier: '',
            status: ''
        };
        this.charts = {};
        this.init();
    }

    async init() {
        await this.loadDashboardData();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Search and filters
        const searchInput = document.getElementById('userSearch');
        const tierFilter = document.getElementById('tierFilter');
        const statusFilter = document.getElementById('statusFilter');

        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.currentFilters.search = e.target.value;
                this.currentPage = 1;
                this.loadUsers();
            }, 500);
        });

        tierFilter.addEventListener('change', (e) => {
            this.currentFilters.tier = e.target.value;
            this.currentPage = 1;
            this.loadUsers();
        });

        statusFilter.addEventListener('change', (e) => {
            this.currentFilters.status = e.target.value;
            this.currentPage = 1;
            this.loadUsers();
        });
    }

    async loadDashboardData() {
        await Promise.all([
            this.loadStats(),
            this.loadUsers(),
            this.loadAnalytics(),
            this.loadSystemHealth()
        ]);
    }

    async loadStats() {
        try {
            const response = await fetch('/api/admin/dashboard/stats', {
                credentials: 'include'
            });

            if (response.ok) {
                const stats = await response.json();
                this.updateStatsCards(stats);
            }
        } catch (error) {
            console.error('Error loading dashboard stats:', error);
        }
    }

    updateStatsCards(stats) {
        document.getElementById('totalUsers').textContent = stats.users.total.toLocaleString();
        document.getElementById('userGrowth').textContent = `${stats.growth.user_growth_rate >= 0 ? '+' : ''}${stats.growth.user_growth_rate.toFixed(1)}%`;
        
        document.getElementById('premiumUsers').textContent = stats.subscriptions.premium.toLocaleString();
        document.getElementById('conversionRate').textContent = `${stats.subscriptions.conversion_rate.toFixed(1)}%`;
        
        document.getElementById('monthlyRevenue').textContent = `$${stats.revenue.monthly.toLocaleString()}`;
        document.getElementById('monthlyVideos').textContent = stats.usage.monthly_videos.toLocaleString();
        
        // Update growth indicators
        const userGrowthElement = document.getElementById('userGrowth');
        userGrowthElement.className = stats.growth.user_growth_rate >= 0 ? 'text-success' : 'text-danger';
    }

    async loadUsers() {
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                limit: 20,
                ...this.currentFilters
            });

            const response = await fetch(`/api/admin/users?${params}`, {
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                this.updateUsersTable(data.users);
                this.updatePagination(data.pagination);
            }
        } catch (error) {
            console.error('Error loading users:', error);
        }
    }

    updateUsersTable(users) {
        const tbody = document.getElementById('usersTableBody');
        
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No users found</td></tr>';
            return;
        }

        tbody.innerHTML = users.map(user => `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <div>
                            <div class="fw-bold">${user.full_name || 'N/A'}</div>
                            <div class="text-muted small">${user.email}</div>
                            <div class="text-muted small">
                                ${this.getOAuthBadges(user.oauth_providers)}
                            </div>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="badge ${user.subscription.tier === 'premium' ? 'bg-warning' : 'bg-secondary'}">
                        ${user.subscription.tier.charAt(0).toUpperCase() + user.subscription.tier.slice(1)}
                    </span>
                </td>
                <td>
                    <div>
                        <span class="badge ${user.is_active ? 'bg-success' : 'bg-danger'}">
                            ${user.is_active ? 'Active' : 'Inactive'}
                        </span>
                        <br>
                        <small class="badge ${user.is_verified ? 'bg-info' : 'bg-secondary'} mt-1">
                            ${user.is_verified ? 'Verified' : 'Unverified'}
                        </small>
                    </div>
                </td>
                <td class="text-muted small">
                    ${new Date(user.created_at).toLocaleDateString()}
                </td>
                <td class="text-muted small">
                    ${user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                </td>
                <td class="text-muted small">
                    ${user.subscription.monthly_usage.toFixed(1)} min
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="adminDashboard.viewUserDetails(${user.id})">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-outline-${user.is_active ? 'danger' : 'success'}" 
                                onclick="adminDashboard.toggleUserStatus(${user.id}, ${!user.is_active})">
                            <i class="fas fa-${user.is_active ? 'ban' : 'check'}"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    getOAuthBadges(providers) {
        const badges = [];
        if (providers.google) badges.push('<span class="badge bg-danger">Google</span>');
        if (providers.microsoft) badges.push('<span class="badge bg-info">Microsoft</span>');
        if (providers.apple) badges.push('<span class="badge bg-dark">Apple</span>');
        return badges.join(' ');
    }

    updatePagination(pagination) {
        const paginationEl = document.getElementById('usersPagination');
        const { page, pages, total } = pagination;
        
        if (pages <= 1) {
            paginationEl.innerHTML = '';
            return;
        }

        let paginationHTML = '';
        
        // Previous button
        paginationHTML += `
            <li class="page-item ${page === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="adminDashboard.goToPage(${page - 1})">Previous</a>
            </li>
        `;
        
        // Page numbers
        const startPage = Math.max(1, page - 2);
        const endPage = Math.min(pages, page + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <li class="page-item ${i === page ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="adminDashboard.goToPage(${i})">${i}</a>
                </li>
            `;
        }
        
        // Next button
        paginationHTML += `
            <li class="page-item ${page === pages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="adminDashboard.goToPage(${page + 1})">Next</a>
            </li>
        `;
        
        paginationEl.innerHTML = paginationHTML;
    }

    async loadAnalytics() {
        try {
            const [usageResponse, revenueResponse] = await Promise.all([
                fetch('/api/admin/analytics/usage?days=30', { credentials: 'include' }),
                fetch('/api/admin/analytics/revenue?days=30', { credentials: 'include' })
            ]);

            if (usageResponse.ok && revenueResponse.ok) {
                const usageData = await usageResponse.json();
                const revenueData = await revenueResponse.json();
                
                this.createUsageChart(usageData);
                this.createTierChart(usageData.tier_usage);
            }
        } catch (error) {
            console.error('Error loading analytics:', error);
        }
    }

    createUsageChart(data) {
        const ctx = document.getElementById('usageChart');
        
        if (this.charts.usage) {
            this.charts.usage.destroy();
        }
        
        this.charts.usage = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.daily_usage.map(d => new Date(d.date).toLocaleDateString()),
                datasets: [
                    {
                        label: 'Videos Processed',
                        data: data.daily_usage.map(d => d.videos),
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Unique Users',
                        data: data.daily_usage.map(d => d.unique_users),
                        borderColor: '#198754',
                        backgroundColor: 'rgba(25, 135, 84, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#ffffff' }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#ffffff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        ticks: { color: '#ffffff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    }
                }
            }
        });
    }

    createTierChart(tierData) {
        const ctx = document.getElementById('tierChart');
        
        if (this.charts.tier) {
            this.charts.tier.destroy();
        }
        
        this.charts.tier = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: tierData.map(d => d.tier.charAt(0).toUpperCase() + d.tier.slice(1)),
                datasets: [{
                    data: tierData.map(d => d.videos),
                    backgroundColor: [
                        '#6c757d',  // Free - Gray
                        '#ffc107'   // Premium - Warning/Gold
                    ],
                    borderWidth: 2,
                    borderColor: '#000000'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#ffffff' }
                    }
                }
            }
        });
    }

    async loadSystemHealth() {
        try {
            const response = await fetch('/api/admin/system/health', {
                credentials: 'include'
            });

            if (response.ok) {
                const health = await response.json();
                this.updateSystemHealth(health);
            }
        } catch (error) {
            console.error('Error loading system health:', error);
        }
    }

    updateSystemHealth(health) {
        // Database status
        const dbIcon = document.getElementById('dbIcon');
        const dbStatus = document.getElementById('dbStatus');
        
        if (health.services.database === 'up') {
            dbIcon.className = 'fas fa-database fa-2x me-3 text-success';
            dbStatus.className = 'badge bg-success';
            dbStatus.textContent = 'Online';
        } else {
            dbIcon.className = 'fas fa-database fa-2x me-3 text-danger';
            dbStatus.className = 'badge bg-danger';
            dbStatus.textContent = 'Offline';
        }

        // Redis status
        const redisIcon = document.getElementById('redisIcon');
        const redisStatus = document.getElementById('redisStatus');
        
        if (health.services.redis === 'up') {
            redisIcon.className = 'fas fa-memory fa-2x me-3 text-success';
            redisStatus.className = 'badge bg-success';
            redisStatus.textContent = 'Online';
        } else {
            redisIcon.className = 'fas fa-memory fa-2x me-3 text-danger';
            redisStatus.className = 'badge bg-danger';
            redisStatus.textContent = 'Offline';
        }

        // Metrics
        document.getElementById('activeSessions').textContent = health.metrics.active_sessions;
        document.getElementById('recentErrors').textContent = health.metrics.recent_errors_24h;
    }

    async viewUserDetails(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}`, {
                credentials: 'include'
            });

            if (response.ok) {
                const userData = await response.json();
                this.showUserDetailsModal(userData);
            }
        } catch (error) {
            console.error('Error loading user details:', error);
        }
    }

    showUserDetailsModal(userData) {
        const { user, usage_stats, payments, recent_activity } = userData;
        
        // User info
        document.getElementById('userDetailsInfo').innerHTML = `
            <div class="mb-2">
                <strong>Name:</strong><br>
                <span class="text-muted">${user.full_name || 'N/A'}</span>
            </div>
            <div class="mb-2">
                <strong>Email:</strong><br>
                <span class="text-muted">${user.email}</span>
            </div>
            <div class="mb-2">
                <strong>Role:</strong><br>
                <span class="badge bg-primary">${user.role}</span>
            </div>
            <div class="mb-2">
                <strong>Status:</strong><br>
                <span class="badge ${user.is_active ? 'bg-success' : 'bg-danger'}">
                    ${user.is_active ? 'Active' : 'Inactive'}
                </span>
                <span class="badge ${user.is_verified ? 'bg-info' : 'bg-secondary'} ms-1">
                    ${user.is_verified ? 'Verified' : 'Unverified'}
                </span>
            </div>
            <div class="mb-2">
                <strong>Created:</strong><br>
                <span class="text-muted">${new Date(user.created_at).toLocaleDateString()}</span>
            </div>
            <div>
                <strong>Last Login:</strong><br>
                <span class="text-muted">${user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}</span>
            </div>
        `;
        
        // Usage stats
        document.getElementById('userUsageStats').innerHTML = `
            <div class="mb-2">
                <strong>Total Videos:</strong><br>
                <span class="text-info">${usage_stats.total_videos}</span>
            </div>
            <div class="mb-2">
                <strong>Total Duration:</strong><br>
                <span class="text-info">${usage_stats.total_duration_minutes.toFixed(1)} minutes</span>
            </div>
            <div>
                <strong>Total Size:</strong><br>
                <span class="text-info">${usage_stats.total_size_gb.toFixed(2)} GB</span>
            </div>
        `;
        
        // Recent activity
        document.getElementById('userRecentActivity').innerHTML = recent_activity.length > 0 
            ? recent_activity.map(activity => `
                <div class="border-bottom pb-2 mb-2">
                    <div class="fw-bold">${activity.action}</div>
                    <div class="text-muted small">
                        ${activity.duration_seconds ? `${activity.duration_seconds}s` : 'N/A'} - 
                        ${new Date(activity.created_at).toLocaleDateString()}
                    </div>
                </div>
            `).join('')
            : '<p class="text-muted">No recent activity</p>';
        
        // Payment history
        const paymentTableBody = document.getElementById('userPaymentHistory');
        paymentTableBody.innerHTML = payments.length > 0
            ? payments.map(payment => `
                <tr>
                    <td>$${payment.amount.toFixed(2)}</td>
                    <td>
                        <span class="badge ${payment.status === 'completed' ? 'bg-success' : payment.status === 'failed' ? 'bg-danger' : 'bg-warning'}">
                            ${payment.status}
                        </span>
                    </td>
                    <td class="text-muted small">${new Date(payment.created_at).toLocaleDateString()}</td>
                    <td class="text-muted small">${payment.description || 'N/A'}</td>
                </tr>
            `).join('')
            : '<tr><td colspan="4" class="text-center text-muted">No payment history</td></tr>';
        
        new bootstrap.Modal(document.getElementById('userDetailsModal')).show();
    }

    async toggleUserStatus(userId, newStatus) {
        if (!confirm(`Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} this user?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/admin/users/${userId}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ active: newStatus }),
                credentials: 'include'
            });

            if (response.ok) {
                this.showToast(`User ${newStatus ? 'activated' : 'deactivated'} successfully`, 'success');
                this.loadUsers();
            } else {
                this.showToast('Failed to update user status', 'error');
            }
        } catch (error) {
            console.error('Error updating user status:', error);
            this.showToast('Error updating user status', 'error');
        }
    }

    goToPage(page) {
        if (page < 1) return;
        this.currentPage = page;
        this.loadUsers();
    }

    async refreshDashboard() {
        const refreshBtn = document.querySelector('button[onclick="refreshDashboard()"]');
        const originalHTML = refreshBtn.innerHTML;
        
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin me-1"></i>Refreshing...';
        refreshBtn.disabled = true;
        
        await this.loadDashboardData();
        
        refreshBtn.innerHTML = originalHTML;
        refreshBtn.disabled = false;
        
        this.showToast('Dashboard refreshed', 'success');
    }

    async exportData() {
        // TODO: Implement data export functionality
        this.showToast('Export functionality coming soon', 'info');
    }

    startAutoRefresh() {
        // Refresh stats every 5 minutes
        setInterval(() => {
            this.loadStats();
            this.loadSystemHealth();
        }, 5 * 60 * 1000);
    }

    showToast(message, type = 'info') {
        // Reuse toast functionality from auth.js
        if (typeof authManager !== 'undefined' && authManager.showToast) {
            authManager.showToast(message, type);
        } else {
            // Fallback alert
            alert(message);
        }
    }
}

// Global functions
function refreshDashboard() {
    if (window.adminDashboard) {
        window.adminDashboard.refreshDashboard();
    }
}

function exportData() {
    if (window.adminDashboard) {
        window.adminDashboard.exportData();
    }
}

// Initialize admin dashboard when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname.includes('/admin')) {
        // Check authentication with better error handling
        setTimeout(() => {
            // First try to load user data
            fetch('/api/auth/check-auth')
                .then(response => response.json())
                .then(data => {
                    if (data.user && (data.user.role === 'ADMIN' || data.user.role === 'admin')) {
                        // User is admin, initialize dashboard
                        if (typeof AdminDashboard !== 'undefined') {
                            window.adminDashboard = new AdminDashboard();
                        }
                    } else {
                        // Not admin, redirect
                        window.location.href = '/?error=access_denied';
                    }
                })
                .catch(error => {
                    console.error('Auth check failed:', error);
                    // On error, redirect to login
                    window.location.href = '/?error=auth_failed';
                });
        }, 100);
    }
});