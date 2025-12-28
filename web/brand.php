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
$custom_start = $_GET['from'] ?? null;
$custom_end = $_GET['to'] ?? null;
$date_range = get_date_range($range, $custom_start, $custom_end);
$last_order_date = get_last_order_date();
$tooltips = get_kpi_tooltips();

// Fetch all data
$hero = get_hero_metrics_with_trends($id, $date_range);
$costs = get_platform_costs($id, $date_range['start'], $date_range['end']);
$promos = get_promo_stats($id, $date_range['start'], $date_range['end']);
$breakdown = get_order_breakdown($id, $date_range['start'], $date_range['end']);
$growth = get_growth_comparisons($id);
$patterns = get_day_patterns($id, $date_range['start'], $date_range['end']);
$daily_data = get_daily_data($id, $date_range['start'], $date_range['end']);
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
                <a href="?id=<?= $id ?>&range=l4l" class="btn btn-small <?= $range === 'l4l' ? 'active' : '' ?>">L4L</a>
                <button type="button" class="btn btn-small <?= $range === 'custom' ? 'active' : '' ?>" onclick="toggleCustomRange()">Custom</button>
            </div>
        </div>

        <!-- Custom Date Range Form -->
        <div id="customRangeForm" class="custom-range-form" style="display: <?= $range === 'custom' ? 'flex' : 'none' ?>;">
            <form method="GET" class="date-form">
                <input type="hidden" name="id" value="<?= $id ?>">
                <input type="hidden" name="range" value="custom">
                <label>From: <input type="date" name="from" value="<?= h($custom_start ?? $date_range['start']) ?>" max="<?= $last_order_date ?>"></label>
                <label>To: <input type="date" name="to" value="<?= h($custom_end ?? $date_range['end']) ?>" max="<?= $last_order_date ?>"></label>
                <button type="submit" class="btn btn-primary btn-small">Apply</button>
            </form>
        </div>

        <div class="date-info">
            <span class="date-label"><?= h($date_range['label']) ?>: <?= format_date($date_range['start']) ?> — <?= format_date($date_range['end']) ?></span>
            <?php if (!empty($date_range['is_partial'])): ?>
            <span class="partial-warning">Partial period: data until <?= format_date($last_order_date) ?></span>
            <?php endif; ?>
        </div>

        <!-- ROW 1: Hero Metrics -->
        <div class="stats-grid stats-grid-5">
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['gross']['value']) ?></span>
                </div>
                <div class="stat-label">Gross Revenue <span class="info-icon" title="<?= h($tooltips['gross']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['gross']['trend']['direction'] ?>">
                    <?= $hero['gross']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['gross']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['net']['value']) ?></span>
                </div>
                <div class="stat-label">Net Payout <span class="info-icon" title="<?= h($tooltips['net']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['net']['trend']['direction'] ?>">
                    <?= $hero['net']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['net']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= number_format($hero['orders']['value']) ?></span>
                </div>
                <div class="stat-label">Orders <span class="info-icon" title="<?= h($tooltips['orders']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['orders']['trend']['direction'] ?>">
                    <?= $hero['orders']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['orders']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['aov']['value']) ?></span>
                </div>
                <div class="stat-label">Avg Order Value <span class="info-icon" title="<?= h($tooltips['aov']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['aov']['trend']['direction'] ?>">
                    <?= $hero['aov']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['aov']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_percent($hero['margin']['value']) ?></span>
                </div>
                <div class="stat-label">Net Margin <span class="info-icon" title="<?= h($tooltips['margin']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['margin']['trend']['direction'] ?>">
                    <?= $hero['margin']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['margin']['trend']['comparison']) ?></span>
                </div>
            </div>
        </div>

        <!-- ROW 2: Platform Costs + Promos -->
        <div class="grid-2">
            <div class="card">
                <h2>Platform Costs</h2>
                <div class="metric-row">
                    <span class="metric-label">Commission <span class="info-icon" title="<?= h($tooltips['commission']) ?>">ⓘ</span></span>
                    <span class="metric-value danger"><?= format_money($costs['commission']) ?></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Avg Rate <span class="info-icon" title="<?= h($tooltips['avg_rate']) ?>">ⓘ</span></span>
                    <span class="metric-value"><?= format_percent($costs['avg_rate']) ?></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Refunds <span class="info-icon" title="<?= h($tooltips['refunds']) ?>">ⓘ</span></span>
                    <span class="metric-value danger"><?= format_money($costs['refunds']) ?> <small>(<?= format_percent($costs['refund_pct']) ?> of net)</small></span>
                </div>
                <div class="metric-row total">
                    <span class="metric-label">Total Costs</span>
                    <span class="metric-value danger"><?= format_money($costs['total']) ?></span>
                </div>
            </div>

            <div class="card">
                <h2>Promos & Marketing</h2>
                <div class="metric-row">
                    <span class="metric-label">Restaurant Funded <span class="info-icon" title="<?= h($tooltips['restaurant_promos']) ?>">ⓘ</span></span>
                    <span class="metric-value warning"><?= format_money($promos['restaurant_promos']) ?> <small>(<?= format_percent($promos['restaurant_pct']) ?>)</small></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Platform Funded <span class="info-icon" title="<?= h($tooltips['platform_promos']) ?>">ⓘ</span></span>
                    <span class="metric-value success"><?= format_money($promos['platform_promos']) ?> <small>(<?= format_percent($promos['platform_pct']) ?>)</small></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Tips <span class="info-icon" title="<?= h($tooltips['tips']) ?>">ⓘ</span></span>
                    <span class="metric-value success"><?= format_money($promos['tips']) ?></span>
                </div>
                <div class="metric-row total">
                    <span class="metric-label">Total Promos</span>
                    <span class="metric-value"><?= format_money($promos['total_promos']) ?> <small>(<?= format_percent($promos['total_pct']) ?> of gross)</small></span>
                </div>
            </div>
        </div>

        <!-- ROW 3: Growth Comparisons -->
        <div class="card">
            <h2>Growth Comparisons</h2>
            <div class="growth-grid">
                <div class="growth-card">
                    <div class="growth-label">Week over Week</div>
                    <div class="growth-trend <?= $growth['wow']['direction'] ?>"><?= $growth['wow']['label'] ?></div>
                    <div class="growth-period"><?= h($growth['wow']['period']) ?></div>
                    <div class="growth-vs">vs <?= h($growth['wow']['vs_period']) ?></div>
                </div>
                <div class="growth-card">
                    <div class="growth-label">Month over Month</div>
                    <div class="growth-trend <?= $growth['mom']['direction'] ?>"><?= $growth['mom']['label'] ?></div>
                    <div class="growth-period"><?= h($growth['mom']['period']) ?></div>
                    <div class="growth-vs">vs <?= h($growth['mom']['vs_period']) ?></div>
                </div>
                <div class="growth-card">
                    <div class="growth-label">Year over Year</div>
                    <div class="growth-trend <?= $growth['yoy']['direction'] ?>"><?= $growth['yoy']['label'] ?></div>
                    <div class="growth-period"><?= h($growth['yoy']['period']) ?></div>
                    <div class="growth-vs">vs <?= h($growth['yoy']['vs_period']) ?></div>
                </div>
                <div class="growth-card">
                    <div class="growth-label">Like for Like (L4L)</div>
                    <div class="growth-trend <?= $growth['l4l']['direction'] ?>"><?= $growth['l4l']['label'] ?></div>
                    <div class="growth-period"><?= h($growth['l4l']['period']) ?></div>
                    <div class="growth-vs">vs <?= h($growth['l4l']['vs_period']) ?></div>
                </div>
            </div>
        </div>

        <!-- ROW 4: Day Patterns + Platform Breakdown -->
        <div class="grid-2">
            <div class="card">
                <h2>Day Patterns</h2>
                <?php if ($patterns['best']): ?>
                <div class="pattern-highlights">
                    <div class="pattern-item best">
                        <span class="pattern-label">Best Day</span>
                        <span class="pattern-value"><?= h($patterns['best']['day_name']) ?></span>
                        <span class="pattern-detail"><?= format_money($patterns['best']['avg_daily_gross']) ?> avg</span>
                    </div>
                    <div class="pattern-item worst">
                        <span class="pattern-label">Slowest Day</span>
                        <span class="pattern-value"><?= h($patterns['worst']['day_name']) ?></span>
                        <span class="pattern-detail"><?= format_money($patterns['worst']['avg_daily_gross']) ?> avg</span>
                    </div>
                </div>
                <div class="day-bars">
                    <?php
                    $max_gross = max(array_column($patterns['days'], 'avg_daily_gross') ?: [1]);
                    foreach ($patterns['days'] as $day):
                        $pct = $max_gross > 0 ? ($day['avg_daily_gross'] / $max_gross) * 100 : 0;
                        $short_name = substr($day['day_name'], 0, 3);
                    ?>
                    <div class="day-bar">
                        <span class="day-label"><?= $short_name ?></span>
                        <div class="bar-track">
                            <div class="bar-fill" style="width: <?= $pct ?>%"></div>
                        </div>
                        <span class="day-value"><?= format_money($day['avg_daily_gross']) ?></span>
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

                <!-- Payment Methods -->
                <div class="payment-summary">
                    <?php
                    $total_orders = ($breakdown['cash']['card_orders'] ?? 0) + ($breakdown['cash']['cash_orders'] ?? 0);
                    $cash_pct = $total_orders > 0 ? (($breakdown['cash']['cash_orders'] ?? 0) / $total_orders) * 100 : 0;
                    ?>
                    <div class="payment-item">
                        <span>Card: <?= number_format($breakdown['cash']['card_orders'] ?? 0) ?> orders</span>
                        <span><?= format_money($breakdown['cash']['card_value'] ?? 0) ?></span>
                    </div>
                    <div class="payment-item">
                        <span>Cash: <?= number_format($breakdown['cash']['cash_orders'] ?? 0) ?> orders (<?= format_percent($cash_pct) ?>)</span>
                        <span><?= format_money($breakdown['cash']['cash_value'] ?? 0) ?></span>
                    </div>
                </div>
                <?php else: ?>
                <p class="empty">No data for this period</p>
                <?php endif; ?>
            </div>
        </div>

        <!-- ROW 5: Revenue Chart -->
        <div class="card">
            <div class="chart-header">
                <h2>Daily Performance</h2>
                <div class="chart-controls">
                    <select id="chartKpi" onchange="updateChart()">
                        <option value="gross">Gross Revenue</option>
                        <option value="net">Net Payout</option>
                        <option value="orders">Orders</option>
                        <option value="aov">Avg Order Value</option>
                        <option value="margin">Margin %</option>
                    </select>
                </div>
            </div>
            <canvas id="revenueChart" height="100"></canvas>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const chartData = <?= json_encode($daily_data) ?>;
        let chart = null;

        function toggleCustomRange() {
            const form = document.getElementById('customRangeForm');
            form.style.display = form.style.display === 'none' ? 'flex' : 'none';
        }

        function updateChart() {
            const kpi = document.getElementById('chartKpi').value;
            const labels = chartData.map(d => d.order_date);

            let data, label, color, isCurrency = true, isPercent = false;

            switch(kpi) {
                case 'gross':
                    data = chartData.map(d => d.gross);
                    label = 'Gross Revenue';
                    color = '#3b82f6';
                    break;
                case 'net':
                    data = chartData.map(d => d.net);
                    label = 'Net Payout';
                    color = '#10b981';
                    break;
                case 'orders':
                    data = chartData.map(d => d.orders);
                    label = 'Orders';
                    color = '#8b5cf6';
                    isCurrency = false;
                    break;
                case 'aov':
                    data = chartData.map(d => d.aov);
                    label = 'Avg Order Value';
                    color = '#f59e0b';
                    break;
                case 'margin':
                    data = chartData.map(d => d.margin);
                    label = 'Margin %';
                    color = '#ef4444';
                    isCurrency = false;
                    isPercent = true;
                    break;
            }

            if (chart) {
                chart.destroy();
            }

            chart = new Chart(document.getElementById('revenueChart'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: label,
                        data: data,
                        borderColor: color,
                        backgroundColor: color + '20',
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
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    if (isPercent) return value.toFixed(1) + '%';
                                    if (isCurrency) return value.toLocaleString('it-IT') + ' €';
                                    return value;
                                }
                            }
                        }
                    }
                }
            });
        }

        // Initialize chart
        if (chartData.length > 0) {
            updateChart();
        }
    </script>
</body>
</html>
