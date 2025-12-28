<?php
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/functions.php';

require_login();

$brand_id = get_user_brand_id();
$stats = get_dashboard_stats($brand_id);
$brands = get_brands();
$platform_breakdown = get_platform_breakdown($brand_id);
$orders_by_date = get_orders_by_date($brand_id, 30);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Delivery Analytics</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">Delivery Analytics</div>
        <div class="nav-user">
            <?= h(get_user_email()) ?>
            <a href="login.php?logout=1" class="btn btn-small">Logout</a>
        </div>
    </nav>

    <div class="container">
        <h1>Dashboard</h1>

        <!-- Stats Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value"><?= number_format($stats['total_orders'] ?? 0) ?></div>
                <div class="stat-label">Total Orders</div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= format_money($stats['total_gross'] ?? 0) ?></div>
                <div class="stat-label">Gross Revenue</div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= format_money($stats['total_commission'] ?? 0) ?></div>
                <div class="stat-label">Total Commission</div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= format_money($stats['total_net'] ?? 0) ?></div>
                <div class="stat-label">Net Payout</div>
            </div>
        </div>

        <div class="grid-2">
            <!-- Platform Breakdown -->
            <div class="card">
                <h2>By Platform</h2>
                <?php if (empty($platform_breakdown)): ?>
                    <p class="empty">No data yet. Import some invoices first.</p>
                <?php else: ?>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Platform</th>
                                <th>Orders</th>
                                <th>Gross</th>
                                <th>Commission</th>
                                <th>Avg Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($platform_breakdown as $row): ?>
                            <tr>
                                <td><span class="platform-badge <?= h($row['platform']) ?>"><?= h(ucfirst($row['platform'])) ?></span></td>
                                <td><?= number_format($row['order_count']) ?></td>
                                <td><?= format_money($row['gross']) ?></td>
                                <td><?= format_money($row['commission']) ?></td>
                                <td><?= format_percent($row['avg_commission_rate']) ?></td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                <?php endif; ?>
            </div>

            <!-- Revenue Chart -->
            <div class="card">
                <h2>Last 30 Days</h2>
                <canvas id="revenueChart"></canvas>
            </div>
        </div>

        <!-- Brands List -->
        <?php if (get_user_role() === 'admin'): ?>
        <div class="card">
            <h2>Brands</h2>
            <?php if (empty($brands)): ?>
                <p class="empty">No brands yet. Import some invoices first.</p>
            <?php else: ?>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Brand</th>
                            <th>Locations</th>
                            <th>Orders</th>
                            <th>Gross Revenue</th>
                            <th>Net Payout</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($brands as $brand): ?>
                        <tr>
                            <td><strong><?= h($brand['name']) ?></strong></td>
                            <td><?= $brand['location_count'] ?></td>
                            <td><?= number_format($brand['order_count']) ?></td>
                            <td><?= format_money($brand['total_gross']) ?></td>
                            <td><?= format_money($brand['total_net']) ?></td>
                            <td><a href="brand.php?id=<?= $brand['id'] ?>" class="btn btn-small">View</a></td>
                        </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
        <?php endif; ?>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const chartData = <?= json_encode($orders_by_date) ?>;

        if (chartData.length > 0) {
            new Chart(document.getElementById('revenueChart'), {
                type: 'line',
                data: {
                    labels: chartData.map(d => d.order_date),
                    datasets: [{
                        label: 'Gross',
                        data: chartData.map(d => d.gross),
                        borderColor: '#3b82f6',
                        tension: 0.1
                    }, {
                        label: 'Net',
                        data: chartData.map(d => d.net),
                        borderColor: '#10b981',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        }
    </script>
</body>
</html>
