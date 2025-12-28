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

// Date range handling
$range = $_GET['range'] ?? 'month';
$date_range = get_date_range($range);

// Fetch all data
$hero = get_hero_metrics_with_trends($id, $date_range);
$costs = get_platform_costs($id, $date_range['start'], $date_range['end']);
$promos = get_promo_stats($id, $date_range['start'], $date_range['end']);
$breakdown = get_order_breakdown($id, $date_range['start'], $date_range['end']);
$growth = get_growth_comparisons($id);
$patterns = get_day_patterns($id, $date_range['start'], $date_range['end']);
$daily_data = get_daily_data($id, $date_range['start'], $date_range['end']);
$locations = get_location_breakdown($id, $date_range['start'], $date_range['end']);
$recent_orders = get_recent_orders($id, 25);
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
        <!-- Header with Date Range -->
        <div class="dashboard-header">
            <h1><?= h($brand['name']) ?></h1>
            <div class="date-range-picker">
                <a href="?id=<?= $id ?>&range=week" class="btn btn-small <?= $range === 'week' ? 'active' : '' ?>">This Week</a>
                <a href="?id=<?= $id ?>&range=month" class="btn btn-small <?= $range === 'month' ? 'active' : '' ?>">This Month</a>
                <a href="?id=<?= $id ?>&range=year" class="btn btn-small <?= $range === 'year' ? 'active' : '' ?>">This Year</a>
                <a href="?id=<?= $id ?>&range=l4w" class="btn btn-small <?= $range === 'l4w' ? 'active' : '' ?>">L4W</a>
            </div>
        </div>
        <p class="date-label"><?= h($date_range['label']) ?>: <?= format_date($date_range['start']) ?> — <?= format_date($date_range['end']) ?></p>

        <!-- ROW 1: Hero Metrics -->
        <div class="stats-grid stats-grid-5">
            <div class="stat-card">
                <div class="stat-value"><?= format_money($hero['gross']['value']) ?></div>
                <div class="stat-label">Gross Revenue</div>
                <div class="stat-trend <?= $hero['gross']['trend']['direction'] ?>"><?= $hero['gross']['trend']['label'] ?></div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= format_money($hero['net']['value']) ?></div>
                <div class="stat-label">Net Payout</div>
                <div class="stat-trend <?= $hero['net']['trend']['direction'] ?>"><?= $hero['net']['trend']['label'] ?></div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= number_format($hero['orders']['value']) ?></div>
                <div class="stat-label">Orders</div>
                <div class="stat-trend <?= $hero['orders']['trend']['direction'] ?>"><?= $hero['orders']['trend']['label'] ?></div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= format_money($hero['aov']['value']) ?></div>
                <div class="stat-label">Avg Order Value</div>
                <div class="stat-trend <?= $hero['aov']['trend']['direction'] ?>"><?= $hero['aov']['trend']['label'] ?></div>
            </div>
            <div class="stat-card">
                <div class="stat-value"><?= format_percent($hero['margin']['value']) ?></div>
                <div class="stat-label">Net Margin</div>
                <div class="stat-trend <?= $hero['margin']['trend']['direction'] ?>"><?= $hero['margin']['trend']['label'] ?></div>
            </div>
        </div>

        <!-- ROW 2: Platform Costs -->
        <div class="grid-3">
            <div class="card">
                <h2>Platform Costs</h2>
                <div class="metric-row">
                    <span class="metric-label">Commission</span>
                    <span class="metric-value danger"><?= format_money($costs['commission']) ?></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Avg Rate</span>
                    <span class="metric-value"><?= format_percent($costs['avg_rate']) ?></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Refunds</span>
                    <span class="metric-value danger"><?= format_money($costs['refunds']) ?></span>
                </div>
                <div class="metric-row total">
                    <span class="metric-label">Total Costs</span>
                    <span class="metric-value danger"><?= format_money($costs['total']) ?></span>
                </div>
            </div>

            <!-- ROW 3: Promos & Marketing -->
            <div class="card">
                <h2>Promos & Marketing</h2>
                <div class="metric-row">
                    <span class="metric-label">Restaurant Funded</span>
                    <span class="metric-value warning"><?= format_money($promos['restaurant_promos']) ?></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Platform Funded</span>
                    <span class="metric-value success"><?= format_money($promos['platform_promos']) ?></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Adjustments</span>
                    <span class="metric-value"><?= format_money($promos['adjustments']) ?></span>
                </div>
                <div class="metric-row total">
                    <span class="metric-label">Total Promos</span>
                    <span class="metric-value"><?= format_money($promos['total_promos']) ?></span>
                </div>
            </div>

            <!-- ROW 4: Order Breakdown -->
            <div class="card">
                <h2>Payment Methods</h2>
                <div class="metric-row">
                    <span class="metric-label">Card Orders</span>
                    <span class="metric-value"><?= number_format($breakdown['cash']['card_orders'] ?? 0) ?> (<?= format_money($breakdown['cash']['card_value'] ?? 0) ?>)</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Cash Orders</span>
                    <span class="metric-value"><?= number_format($breakdown['cash']['cash_orders'] ?? 0) ?> (<?= format_money($breakdown['cash']['cash_value'] ?? 0) ?>)</span>
                </div>
                <?php
                $total_orders = ($breakdown['cash']['card_orders'] ?? 0) + ($breakdown['cash']['cash_orders'] ?? 0);
                $cash_pct = $total_orders > 0 ? (($breakdown['cash']['cash_orders'] ?? 0) / $total_orders) * 100 : 0;
                ?>
                <div class="metric-row total">
                    <span class="metric-label">Cash %</span>
                    <span class="metric-value"><?= format_percent($cash_pct) ?></span>
                </div>
            </div>
        </div>

        <!-- ROW 5: Growth Comparisons -->
        <div class="stats-grid stats-grid-4">
            <div class="stat-card stat-card-compact">
                <div class="stat-label">Week over Week</div>
                <div class="stat-trend large <?= $growth['wow']['direction'] ?>"><?= $growth['wow']['label'] ?></div>
            </div>
            <div class="stat-card stat-card-compact">
                <div class="stat-label">Month over Month</div>
                <div class="stat-trend large <?= $growth['mom']['direction'] ?>"><?= $growth['mom']['label'] ?></div>
            </div>
            <div class="stat-card stat-card-compact">
                <div class="stat-label">Year over Year</div>
                <div class="stat-trend large <?= $growth['yoy']['direction'] ?>"><?= $growth['yoy']['label'] ?></div>
            </div>
            <div class="stat-card stat-card-compact">
                <div class="stat-label">L4W vs Prev L4W</div>
                <div class="stat-trend large <?= $growth['l4l']['direction'] ?>"><?= $growth['l4l']['label'] ?></div>
            </div>
        </div>

        <!-- ROW 6: Day Patterns + Platform Breakdown -->
        <div class="grid-2">
            <div class="card">
                <h2>Day Patterns</h2>
                <?php if ($patterns['best']): ?>
                <div class="pattern-highlights">
                    <div class="pattern-item best">
                        <span class="pattern-label">Best Day</span>
                        <span class="pattern-value"><?= $patterns['best']['day_name'] ?></span>
                        <span class="pattern-detail"><?= format_money($patterns['best']['gross']) ?> (<?= $patterns['best']['orders'] ?> orders)</span>
                    </div>
                    <div class="pattern-item worst">
                        <span class="pattern-label">Slowest Day</span>
                        <span class="pattern-value"><?= $patterns['worst']['day_name'] ?></span>
                        <span class="pattern-detail"><?= format_money($patterns['worst']['gross']) ?> (<?= $patterns['worst']['orders'] ?> orders)</span>
                    </div>
                </div>
                <div class="day-bars">
                    <?php
                    $max_gross = max(array_column($patterns['days'], 'gross') ?: [1]);
                    foreach ($patterns['days'] as $day):
                        $pct = $max_gross > 0 ? ($day['gross'] / $max_gross) * 100 : 0;
                    ?>
                    <div class="day-bar">
                        <span class="day-label"><?= $day['day_name'] ?></span>
                        <div class="bar-track">
                            <div class="bar-fill" style="width: <?= $pct ?>%"></div>
                        </div>
                        <span class="day-value"><?= format_money($day['gross']) ?></span>
                    </div>
                    <?php endforeach; ?>
                </div>
                <?php else: ?>
                <p class="empty">No data for this period</p>
                <?php endif; ?>
            </div>

            <div class="card">
                <h2>By Platform</h2>
                <?php if (!empty($breakdown['platforms'])): ?>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Platform</th>
                            <th>Orders</th>
                            <th>Gross</th>
                            <th>Rate</th>
                            <th>Net</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($breakdown['platforms'] as $p): ?>
                        <tr>
                            <td><span class="platform-badge <?= h($p['platform']) ?>"><?= h(ucfirst($p['platform'])) ?></span></td>
                            <td><?= number_format($p['orders']) ?></td>
                            <td><?= format_money($p['gross']) ?></td>
                            <td><?= format_percent($p['avg_rate']) ?></td>
                            <td><?= format_money($p['net']) ?></td>
                        </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
                <?php else: ?>
                <p class="empty">No data for this period</p>
                <?php endif; ?>
            </div>
        </div>

        <!-- Revenue Chart -->
        <div class="card">
            <h2>Daily Revenue</h2>
            <canvas id="revenueChart" height="100"></canvas>
        </div>

        <!-- Locations Breakdown -->
        <div class="card">
            <h2>Locations</h2>
            <?php if (!empty($locations)): ?>
            <table class="table">
                <thead>
                    <tr>
                        <th>Location</th>
                        <th>Platform</th>
                        <th>Orders</th>
                        <th>Gross</th>
                        <th>AOV</th>
                        <th>Net</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($locations as $loc): ?>
                    <tr>
                        <td><?= h($loc['name']) ?></td>
                        <td><span class="platform-badge <?= h($loc['platform']) ?>"><?= h(ucfirst($loc['platform'])) ?></span></td>
                        <td><?= number_format($loc['orders']) ?></td>
                        <td><?= format_money($loc['gross']) ?></td>
                        <td><?= format_money($loc['aov']) ?></td>
                        <td><?= format_money($loc['net']) ?></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
            <?php else: ?>
            <p class="empty">No locations found</p>
            <?php endif; ?>
        </div>

        <!-- Recent Orders -->
        <div class="card">
            <h2>Recent Orders</h2>
            <?php if (!empty($recent_orders)): ?>
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
                        <td class="text-danger"><?= format_money($order['commission']) ?></td>
                        <td><?= format_money($order['net_payout']) ?></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
            <?php else: ?>
            <p class="empty">No orders yet</p>
            <?php endif; ?>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const chartData = <?= json_encode($daily_data) ?>;

        if (chartData.length > 0) {
            new Chart(document.getElementById('revenueChart'), {
                type: 'line',
                data: {
                    labels: chartData.map(d => d.order_date),
                    datasets: [{
                        label: 'Gross',
                        data: chartData.map(d => d.gross),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.3
                    }, {
                        label: 'Net',
                        data: chartData.map(d => d.net),
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: { position: 'bottom' }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return value.toLocaleString('it-IT') + ' €';
                                }
                            }
                        }
                    }
                }
            });
        }
    </script>
</body>
</html>
