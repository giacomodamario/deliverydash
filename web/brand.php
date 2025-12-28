<?php
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/functions.php';

require_login();

$id = (int)($_GET['id'] ?? 0);
$brand = get_brand($id);

if (!$brand) {
    http_response_code(404);
    die('Brand not found');
}

if (!can_view_brand($id)) {
    http_response_code(403);
    die('Access denied');
}

$locations = get_brand_locations($id);
$stats = get_dashboard_stats($id);
$platform_breakdown = get_platform_breakdown($id);
$orders_by_date = get_orders_by_date($id, 30);
$recent_orders = get_recent_orders($id, 100);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= h($brand['name']) ?> - Delivery Analytics</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">
            <a href="index.php">Delivery Analytics</a>
            <span class="nav-separator">/</span>
            <?= h($brand['name']) ?>
        </div>
        <div class="nav-user">
            <?= h(get_user_email()) ?>
            <a href="login.php?logout=1" class="btn btn-small">Logout</a>
        </div>
    </nav>

    <div class="container">
        <h1><?= h($brand['name']) ?></h1>

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
            <!-- Locations -->
            <div class="card">
                <h2>Locations</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Location</th>
                            <th>Platform</th>
                            <th>Orders</th>
                            <th>Gross</th>
                            <th>Net</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($locations as $loc): ?>
                        <tr>
                            <td><?= h($loc['name']) ?></td>
                            <td><span class="platform-badge <?= h($loc['platform']) ?>"><?= h(ucfirst($loc['platform'])) ?></span></td>
                            <td><?= number_format($loc['order_count']) ?></td>
                            <td><?= format_money($loc['total_gross']) ?></td>
                            <td><?= format_money($loc['total_net']) ?></td>
                        </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>

            <!-- Platform Breakdown -->
            <div class="card">
                <h2>By Platform</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Platform</th>
                            <th>Orders</th>
                            <th>Gross</th>
                            <th>Avg Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($platform_breakdown as $row): ?>
                        <tr>
                            <td><span class="platform-badge <?= h($row['platform']) ?>"><?= h(ucfirst($row['platform'])) ?></span></td>
                            <td><?= number_format($row['order_count']) ?></td>
                            <td><?= format_money($row['gross']) ?></td>
                            <td><?= format_percent($row['avg_commission_rate']) ?></td>
                        </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Revenue Chart -->
        <div class="card">
            <h2>Revenue (Last 30 Days)</h2>
            <canvas id="revenueChart"></canvas>
        </div>

        <!-- Recent Orders -->
        <div class="card">
            <h2>Recent Orders</h2>
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Order ID</th>
                        <th>Location</th>
                        <th>Platform</th>
                        <th>Gross</th>
                        <th>Commission</th>
                        <th>Net</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($recent_orders as $order): ?>
                    <tr>
                        <td><?= format_date($order['order_date']) ?></td>
                        <td><code><?= h(substr($order['order_id'], 0, 12)) ?></code></td>
                        <td><?= h($order['location_name']) ?></td>
                        <td><span class="platform-badge <?= h($order['platform']) ?>"><?= h(ucfirst($order['platform'])) ?></span></td>
                        <td><?= format_money($order['gross_value']) ?></td>
                        <td><?= format_money($order['commission']) ?></td>
                        <td><?= format_money($order['net_payout']) ?></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>
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
