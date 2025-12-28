/**
 * Delivery Analytics - Frontend JS
 */

// Format currency
function formatMoney(amount) {
    return new Intl.NumberFormat('it-IT', {
        style: 'currency',
        currency: 'EUR'
    }).format(amount);
}

// Format percentage
function formatPercent(rate) {
    return rate.toFixed(1) + '%';
}

// Format date
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('it-IT');
}

// API helper
async function api(action, params = {}) {
    const url = new URL('api/data.php', window.location.origin + window.location.pathname.replace(/\/[^\/]*$/, '/'));
    url.searchParams.set('action', action);
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return response.json();
}

// Initialize charts if Chart.js is loaded
function initCharts() {
    const chartEl = document.getElementById('revenueChart');
    if (!chartEl || typeof Chart === 'undefined') return;

    // Chart is initialized inline in PHP pages
}

// Auto-refresh dashboard stats every 5 minutes
function startAutoRefresh() {
    setInterval(async () => {
        try {
            const stats = await api('stats');
            // Update stat cards if they exist
            document.querySelectorAll('[data-stat]').forEach(el => {
                const key = el.dataset.stat;
                if (stats[key] !== undefined) {
                    if (key.includes('total_') && !key.includes('orders')) {
                        el.textContent = formatMoney(stats[key]);
                    } else {
                        el.textContent = stats[key].toLocaleString();
                    }
                }
            });
        } catch (e) {
            console.error('Auto-refresh failed:', e);
        }
    }, 5 * 60 * 1000);
}

// Document ready
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    // startAutoRefresh(); // Uncomment to enable auto-refresh
});
