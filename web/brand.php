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
$compare_type = $_GET['compare'] ?? 'auto';  // auto, yoy, l4l, custom
$compare_from = $_GET['compare_from'] ?? null;
$compare_to = $_GET['compare_to'] ?? null;
$location_id = isset($_GET['location']) ? (int)$_GET['location'] : 0;  // 0 = all locations

$date_range = get_date_range($range, $custom_start, $custom_end);
$last_order_date = get_last_order_date();
$tooltips = get_kpi_tooltips();
$locations = get_brand_locations($id);

// Fetch all data
$hero = get_hero_metrics_with_trends($id, $date_range);
$net_revenue = $hero['net_revenue_raw'] ?? 0;
$costs = get_platform_costs($id, $date_range['start'], $date_range['end'], $net_revenue);
$promos = get_promo_stats($id, $date_range['start'], $date_range['end'], $net_revenue);
$refund_breakdown = get_refund_breakdown($id, $date_range['start'], $date_range['end']);
$refund_page = isset($_GET['refund_page']) ? max(1, (int)$_GET['refund_page']) : 1;
$refund_filter = $_GET['refund_filter'] ?? null;
$refund_details = get_refund_details($id, $date_range['start'], $date_range['end'], $refund_page, 10, $refund_filter);
$breakdown = get_order_breakdown($id, $date_range['start'], $date_range['end']);
$growth = get_growth_comparisons($id);
$patterns = get_day_patterns($id, $date_range['start'], $date_range['end']);
$heatmap = get_hourly_heatmap($id, $date_range['start'], $date_range['end']);
$daily_data = get_daily_data($id, $date_range['start'], $date_range['end']);
$daily_data_prev = get_daily_data($id, $date_range['prev_start'], $date_range['prev_end']);
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
            <form method="GET" class="date-form-advanced">
                <input type="hidden" name="id" value="<?= $id ?>">
                <input type="hidden" name="range" value="custom">

                <!-- Period 1 -->
                <div class="period-section">
                    <span class="period-label">Period 1:</span>
                    <label>From: <input type="date" name="from" value="<?= h($custom_start ?? $date_range['start']) ?>" max="<?= $last_order_date ?>" onchange="suggestComparison()"></label>
                    <label>To: <input type="date" name="to" value="<?= h($custom_end ?? $date_range['end']) ?>" max="<?= $last_order_date ?>" onchange="suggestComparison()"></label>
                </div>

                <!-- Period 2 (Comparison) -->
                <div class="period-section">
                    <span class="period-label">Compare to:</span>
                    <div class="compare-options">
                        <label class="compare-option">
                            <input type="radio" name="compare" value="yoy" <?= $compare_type === 'yoy' ? 'checked' : '' ?> onchange="updateCompareFields()">
                            YoY
                        </label>
                        <label class="compare-option">
                            <input type="radio" name="compare" value="l4l" <?= $compare_type === 'l4l' ? 'checked' : '' ?> onchange="updateCompareFields()">
                            L4L
                        </label>
                        <label class="compare-option">
                            <input type="radio" name="compare" value="custom" <?= $compare_type === 'custom' ? 'checked' : '' ?> onchange="updateCompareFields()">
                            Custom
                        </label>
                    </div>
                    <div id="customCompareFields" style="display: <?= $compare_type === 'custom' ? 'flex' : 'none' ?>; gap: 0.5rem; margin-top: 0.5rem;">
                        <label>From: <input type="date" name="compare_from" value="<?= h($compare_from ?? $date_range['prev_start']) ?>" max="<?= $last_order_date ?>"></label>
                        <label>To: <input type="date" name="compare_to" value="<?= h($compare_to ?? $date_range['prev_end']) ?>" max="<?= $last_order_date ?>"></label>
                    </div>
                </div>

                <!-- Store Filter -->
                <?php if (count($locations) > 1): ?>
                <div class="period-section">
                    <span class="period-label">Location:</span>
                    <select name="location" class="location-select">
                        <option value="0">All Locations</option>
                        <?php foreach ($locations as $loc): ?>
                        <option value="<?= $loc['id'] ?>" <?= $location_id === (int)$loc['id'] ? 'selected' : '' ?>><?= h($loc['name']) ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <?php endif; ?>

                <button type="submit" class="btn btn-primary btn-small">Apply</button>
            </form>
        </div>

        <div class="date-info">
            <span class="date-label"><?= format_date_range($date_range['start'], $date_range['end']) ?></span>
            <?php if (!empty($date_range['is_partial'])): ?>
            <span class="partial-warning">Partial period: data until <?= format_date_short($last_order_date) ?></span>
            <?php endif; ?>
            <?php if ($location_id > 0): ?>
            <span class="location-filter-active">Filtered by location</span>
            <?php endif; ?>
        </div>

        <!-- ROW 1: Hero Metrics -->
        <div class="stats-grid stats-grid-6">
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['gross']['value']) ?></span>
                </div>
                <div class="stat-label">Gross Revenue <span class="info-tooltip" data-tooltip="<?= h($tooltips['gross']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['gross']['trend']['direction'] ?>">
                    <?= $hero['gross']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['gross']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['net_revenue']['value']) ?></span>
                </div>
                <div class="stat-label">Net Revenue <span class="info-tooltip" data-tooltip="<?= h($tooltips['net_revenue']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['net_revenue']['trend']['direction'] ?>">
                    <?= $hero['net_revenue']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['net_revenue']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['net_payout']['value']) ?></span>
                </div>
                <div class="stat-label">Net Payout <span class="info-tooltip" data-tooltip="<?= h($tooltips['net_payout']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['net_payout']['trend']['direction'] ?>">
                    <?= $hero['net_payout']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['net_payout']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= number_format($hero['orders']['value']) ?></span>
                </div>
                <div class="stat-label">Orders <span class="info-tooltip" data-tooltip="<?= h($tooltips['orders']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['orders']['trend']['direction'] ?>">
                    <?= $hero['orders']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['orders']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_money($hero['aov']['value']) ?></span>
                </div>
                <div class="stat-label">AOV <span class="info-tooltip" data-tooltip="<?= h($tooltips['aov']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['aov']['trend']['direction'] ?>">
                    <?= $hero['aov']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['aov']['trend']['comparison']) ?></span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-value"><?= format_percent($hero['margin']['value']) ?></span>
                </div>
                <div class="stat-label">Net Margin <span class="info-tooltip" data-tooltip="<?= h($tooltips['margin']) ?>">ⓘ</span></div>
                <div class="stat-trend <?= $hero['margin']['trend']['direction'] ?>">
                    <?= $hero['margin']['trend']['label'] ?>
                    <span class="trend-period"><?= h($hero['margin']['trend']['comparison']) ?></span>
                </div>
            </div>
        </div>

        <!-- ROW 2: Platform Costs -->
        <div class="grid-2">
            <div class="card">
                <h2>Platform Costs</h2>
                <div class="metric-row">
                    <span class="metric-label">Commission <span class="info-tooltip" data-tooltip="<?= h($tooltips['commission']) ?>">ⓘ</span></span>
                    <span class="metric-value danger"><?= format_money($costs['commission']) ?></span>
                    <span class="metric-pct"><?= format_percent($costs['commission_pct']) ?> of net rev</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Commission on Funded <span class="info-tooltip" data-tooltip="<?= h($tooltips['discount_commission']) ?>">ⓘ</span></span>
                    <span class="metric-value danger"><?= format_money($costs['discount_commission']) ?></span>
                    <span class="metric-pct"><?= format_percent($costs['discount_commission_pct']) ?> of net rev</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Refunds <span class="info-tooltip" data-tooltip="<?= h($tooltips['refunds']) ?>">ⓘ</span></span>
                    <span class="metric-value danger"><?= format_money($costs['refunds']) ?></span>
                    <span class="metric-pct"><?= format_percent($costs['refund_pct']) ?> of net rev</span>
                </div>
                <div class="metric-row total">
                    <span class="metric-label">Total Costs</span>
                    <span class="metric-value danger"><?= format_money($costs['total']) ?></span>
                    <span class="metric-pct"><?= format_percent($costs['total_pct']) ?> of net rev</span>
                </div>
            </div>

            <div class="card">
                <h2>Marketing & Promos</h2>
                <div class="metric-row">
                    <span class="metric-label">Ads <span class="info-tooltip" data-tooltip="<?= h($tooltips['ad_fee']) ?>">ⓘ</span></span>
                    <span class="metric-value warning"><?= format_money($promos['ads']) ?></span>
                    <span class="metric-pct"><?= format_percent($promos['ads_pct']) ?> of net rev</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Restaurant Funded <span class="info-tooltip" data-tooltip="<?= h($tooltips['restaurant_promos']) ?>">ⓘ</span></span>
                    <span class="metric-value warning"><?= format_money($promos['restaurant_promos']) ?></span>
                    <span class="metric-pct"><?= format_percent($promos['restaurant_pct']) ?> of net rev</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Platform Funded <span class="info-tooltip" data-tooltip="<?= h($tooltips['platform_promos']) ?>">ⓘ</span></span>
                    <span class="metric-value success"><?= format_money($promos['platform_promos']) ?></span>
                    <span class="metric-pct"><?= format_percent($promos['platform_pct']) ?> of net rev</span>
                </div>
                <div class="metric-row total">
                    <span class="metric-label">Total Promos</span>
                    <span class="metric-value"><?= format_money($promos['total_promos']) ?></span>
                    <span class="metric-pct"><?= format_percent($promos['total_pct']) ?> of net rev</span>
                </div>
            </div>
        </div>

        <!-- ROW 3: Refunds Breakdown -->
        <?php if (!empty($refund_breakdown['items']) || $refund_breakdown['total_count'] > 0): ?>
        <div class="card">
            <h2>Refunds Breakdown</h2>

            <!-- By Fault Party -->
            <h3 style="font-size: 0.95rem; color: var(--gray-600); margin-bottom: 0.75rem;">By Fault Party</h3>
            <table class="table" style="margin-bottom: 1.5rem;">
                <thead>
                    <tr>
                        <th>Fault Party</th>
                        <th class="text-right">Count</th>
                        <th class="text-right">Amount</th>
                        <th class="text-right">% of Total</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($refund_breakdown['by_fault'] as $party => $data): ?>
                    <?php if ($data['count'] > 0): ?>
                    <tr>
                        <td><span class="fault-badge <?= strtolower($party) === 'platform' ? 'platform' : (strtolower($party) === 'restaurant' ? 'restaurant' : '') ?>"><?= h($party) ?></span></td>
                        <td class="text-right"><?= number_format($data['count']) ?></td>
                        <td class="text-right"><?= format_money($data['amount']) ?></td>
                        <td class="text-right"><?= format_percent($data['pct']) ?></td>
                    </tr>
                    <?php endif; ?>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- By Reason -->
            <?php if (!empty($refund_breakdown['items'])): ?>
            <h3 style="font-size: 0.95rem; color: var(--gray-600); margin-bottom: 0.75rem;">By Reason</h3>
            <table class="table">
                <thead>
                    <tr>
                        <th>Reason</th>
                        <th class="text-right">Count</th>
                        <th class="text-right">Amount</th>
                        <th class="text-right">% of Total</th>
                        <th>Fault</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($refund_breakdown['items'] as $r): ?>
                    <tr>
                        <td><?= h($r['reason']) ?></td>
                        <td class="text-right"><?= number_format($r['count']) ?></td>
                        <td class="text-right"><?= format_money($r['amount']) ?></td>
                        <td class="text-right"><?= format_percent($r['pct']) ?></td>
                        <td><span class="fault-badge <?= strtolower($r['fault']) === 'platform' ? 'platform' : (strtolower($r['fault']) === 'restaurant' ? 'restaurant' : '') ?>"><?= h($r['fault']) ?></span></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
            <?php endif; ?>

            <!-- Insights -->
            <div class="refund-insights" style="margin-top: 1rem;">
                <?php if ($refund_breakdown['restaurant_fault_amount'] > 0): ?>
                <p class="insight-text" style="background: #fef2f2; border-left-color: var(--danger); color: #991b1b;">
                    Restaurant-fault: <?= format_money($refund_breakdown['restaurant_fault_amount']) ?> (<?= format_percent($refund_breakdown['restaurant_fault_pct']) ?>) - your responsibility
                </p>
                <?php endif; ?>
                <?php if ($refund_breakdown['platform_fault_amount'] > 0): ?>
                <p class="insight-text">
                    Platform-fault: <?= format_money($refund_breakdown['platform_fault_amount']) ?> (<?= format_percent($refund_breakdown['platform_fault_pct']) ?>) - potentially disputable
                </p>
                <p class="insight-text" style="background: #dbeafe; border-left-color: #3b82f6; color: #1e40af;">
                    Review platform-fault refunds for dispute opportunities
                </p>
                <?php endif; ?>
            </div>
        </div>
        <?php endif; ?>

        <!-- Refund Details -->
        <?php if ($refund_details['total'] > 0): ?>
        <div class="card">
            <div class="section-header">
                <h2>Refund Details</h2>
                <span class="badge"><?= $refund_details['total'] ?> orders</span>
            </div>

            <!-- Filter Pills -->
            <?php if (!empty($refund_details['reasons'])): ?>
            <div class="filter-pills">
                <a href="?id=<?= $id ?>&range=<?= $range ?>&from=<?= $custom_start ?>&to=<?= $custom_end ?>"
                   class="pill <?= !$refund_filter ? 'active' : '' ?>">All</a>
                <?php foreach ($refund_details['reasons'] as $reason): ?>
                <a href="?id=<?= $id ?>&range=<?= $range ?>&from=<?= $custom_start ?>&to=<?= $custom_end ?>&refund_filter=<?= urlencode($reason) ?>"
                   class="pill <?= $refund_filter === $reason ? 'active' : '' ?>"><?= h($reason) ?></a>
                <?php endforeach; ?>
            </div>
            <?php endif; ?>

            <!-- Refund Orders Table -->
            <table class="table">
                <thead>
                    <tr>
                        <th>Order ID</th>
                        <th>Date</th>
                        <th>Time</th>
                        <th class="text-right">Value</th>
                        <th class="text-right">Refund</th>
                        <th>Reason</th>
                        <th>Fault</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($refund_details['orders'] as $order): ?>
                    <tr class="refund-row <?= strtolower($order['refund_fault']) ?>">
                        <td><code><?= h($order['order_id']) ?></code></td>
                        <td><?= format_date($order['order_date']) ?></td>
                        <td><?= h($order['order_time'] ?? '-') ?></td>
                        <td class="text-right"><?= format_money($order['gross_value']) ?></td>
                        <td class="text-right danger"><?= format_money($order['refund']) ?></td>
                        <td><?= h($order['refund_reason'] ?? '-') ?></td>
                        <td><span class="fault-badge <?= strtolower($order['refund_fault']) ?>"><?= h($order['refund_fault']) ?></span></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- Pagination -->
            <?php if ($refund_details['total_pages'] > 1): ?>
            <div class="pagination">
                <?php if ($refund_page > 1): ?>
                <a href="?id=<?= $id ?>&range=<?= $range ?>&from=<?= $custom_start ?>&to=<?= $custom_end ?>&refund_filter=<?= urlencode($refund_filter ?? '') ?>&refund_page=<?= $refund_page - 1 ?>" class="btn btn-small">← Prev</a>
                <?php endif; ?>
                <span class="page-info">Page <?= $refund_page ?> of <?= $refund_details['total_pages'] ?></span>
                <?php if ($refund_page < $refund_details['total_pages']): ?>
                <a href="?id=<?= $id ?>&range=<?= $range ?>&from=<?= $custom_start ?>&to=<?= $custom_end ?>&refund_filter=<?= urlencode($refund_filter ?? '') ?>&refund_page=<?= $refund_page + 1 ?>" class="btn btn-small">Next →</a>
                <?php endif; ?>
            </div>
            <?php endif; ?>
        </div>
        <?php endif; ?>

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
                    <?php if (!empty($growth['yoy']['partial_data'])): ?>
                    <div class="growth-warning">⚠️ Limited comparison data</div>
                    <?php endif; ?>
                </div>
                <div class="growth-card">
                    <div class="growth-label">Like for Like (L4L)</div>
                    <div class="growth-trend <?= $growth['l4l']['direction'] ?>"><?= $growth['l4l']['label'] ?></div>
                    <div class="growth-period"><?= h($growth['l4l']['period']) ?></div>
                    <div class="growth-vs">vs <?= h($growth['l4l']['vs_period']) ?> (same stores)</div>
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
                <h2>Hourly Performance</h2>
                <?php if ($heatmap['max_orders'] > 0): ?>
                <!-- Summary Stats -->
                <div class="heatmap-stats">
                    <div class="heatmap-stat">
                        <span class="stat-label">Peak Hour</span>
                        <span class="stat-value-small"><?= $heatmap['peak_hour'] ?></span>
                    </div>
                    <div class="heatmap-stat">
                        <span class="stat-label">Busiest Day</span>
                        <span class="stat-value-small"><?= $heatmap['busiest_day'] ?></span>
                    </div>
                    <div class="heatmap-stat">
                        <span class="stat-label">Slowest Hour</span>
                        <span class="stat-value-small"><?= $heatmap['slowest_hour'] ?></span>
                    </div>
                    <div class="heatmap-stat">
                        <span class="stat-label">Slowest Day</span>
                        <span class="stat-value-small"><?= $heatmap['slowest_day'] ?></span>
                    </div>
                </div>

                <!-- Heatmap Grid -->
                <div class="heatmap-container">
                    <div class="heatmap-toggle">
                        <button class="btn btn-small active" onclick="toggleHeatmap('orders')">Orders</button>
                        <button class="btn btn-small" onclick="toggleHeatmap('revenue')">Revenue</button>
                    </div>
                    <div class="heatmap-grid" id="heatmapGrid">
                        <div class="heatmap-header">
                            <div class="heatmap-corner"></div>
                            <?php
                            // Reorder days starting from Monday
                            $day_order = [1, 2, 3, 4, 5, 6, 0];
                            foreach ($day_order as $d):
                            ?>
                            <div class="heatmap-day"><?= $heatmap['day_names'][$d] ?></div>
                            <?php endforeach; ?>
                        </div>
                        <?php
                        // Only show hours with data (typically 10-23)
                        $active_hours = [];
                        foreach ($heatmap['matrix'] as $h => $days) {
                            $has_data = false;
                            foreach ($days as $d => $data) {
                                if ($data['orders'] > 0) $has_data = true;
                            }
                            if ($has_data) $active_hours[] = $h;
                        }
                        if (empty($active_hours)) $active_hours = range(10, 22);
                        $min_hour = min($active_hours);
                        $max_hour = max($active_hours);

                        for ($h = $min_hour; $h <= $max_hour; $h++):
                        ?>
                        <div class="heatmap-row">
                            <div class="heatmap-hour"><?= sprintf('%02d', $h) ?></div>
                            <?php foreach ($day_order as $d):
                                $cell = $heatmap['matrix'][$h][$d];
                                $intensity = $heatmap['max_orders'] > 0 ? $cell['orders'] / $heatmap['max_orders'] : 0;
                            ?>
                            <div class="heatmap-cell"
                                 data-orders="<?= $cell['orders'] ?>"
                                 data-revenue="<?= number_format($cell['revenue'], 2) ?>"
                                 style="background: rgba(59, 130, 246, <?= $intensity ?>);"
                                 title="<?= $cell['orders'] ?> orders, <?= format_money($cell['revenue']) ?>">
                                <span class="cell-value"><?= $cell['orders'] > 0 ? $cell['orders'] : '' ?></span>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        <?php endfor; ?>
                    </div>
                    <div class="heatmap-legend">
                        <span>Low</span>
                        <div class="legend-gradient"></div>
                        <span>High</span>
                    </div>
                </div>
                <?php else: ?>
                <p class="empty">No hourly data for this period</p>
                <?php endif; ?>
            </div>
        </div>

        <!-- ROW 5: Performance Trend Chart -->
        <div class="card">
            <div class="chart-header">
                <h2>Performance Trend</h2>
                <div class="chart-controls">
                    <select id="chartKpi" onchange="updateChart()">
                        <option value="gross">Gross Revenue</option>
                        <option value="net">Net Payout</option>
                        <option value="orders">Orders</option>
                        <option value="aov">Avg Order Value</option>
                        <option value="margin">Margin %</option>
                    </select>
                    <label class="chart-checkbox">
                        <input type="checkbox" id="showComparison" onchange="updateChart()" checked>
                        Show previous period
                    </label>
                </div>
            </div>
            <canvas id="revenueChart" height="100"></canvas>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const chartData = <?= json_encode($daily_data) ?>;
        const chartDataPrev = <?= json_encode($daily_data_prev) ?>;
        const prevLabel = '<?= h($date_range['prev_label'] ?? 'Previous period') ?>';
        let chart = null;

        function toggleCustomRange() {
            const form = document.getElementById('customRangeForm');
            form.style.display = form.style.display === 'none' ? 'flex' : 'none';
        }

        function updateCompareFields() {
            const customFields = document.getElementById('customCompareFields');
            const compareType = document.querySelector('input[name="compare"]:checked')?.value;
            customFields.style.display = compareType === 'custom' ? 'flex' : 'none';
        }

        function suggestComparison() {
            // Smart suggestion: auto-fill YoY comparison dates
            const fromInput = document.querySelector('input[name="from"]');
            const toInput = document.querySelector('input[name="to"]');
            const compareFromInput = document.querySelector('input[name="compare_from"]');
            const compareToInput = document.querySelector('input[name="compare_to"]');

            if (fromInput.value && toInput.value && compareFromInput && compareToInput) {
                // Suggest same period last year
                const from = new Date(fromInput.value);
                const to = new Date(toInput.value);
                from.setFullYear(from.getFullYear() - 1);
                to.setFullYear(to.getFullYear() - 1);
                compareFromInput.value = from.toISOString().split('T')[0];
                compareToInput.value = to.toISOString().split('T')[0];
            }
        }

        const heatmapMaxRevenue = <?= $heatmap['max_revenue'] ?? 0 ?>;

        function toggleHeatmap(mode) {
            const cells = document.querySelectorAll('.heatmap-cell');
            const buttons = document.querySelectorAll('.heatmap-toggle .btn');

            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            cells.forEach(cell => {
                const orders = parseInt(cell.dataset.orders) || 0;
                const revenue = parseFloat(cell.dataset.revenue) || 0;
                const valueSpan = cell.querySelector('.cell-value');

                if (mode === 'orders') {
                    const maxOrders = <?= $heatmap['max_orders'] ?? 1 ?>;
                    const intensity = maxOrders > 0 ? orders / maxOrders : 0;
                    cell.style.background = `rgba(59, 130, 246, ${intensity})`;
                    valueSpan.textContent = orders > 0 ? orders : '';
                } else {
                    const intensity = heatmapMaxRevenue > 0 ? revenue / heatmapMaxRevenue : 0;
                    cell.style.background = `rgba(16, 185, 129, ${intensity})`;
                    valueSpan.textContent = revenue > 0 ? Math.round(revenue) + '€' : '';
                }
            });

            // Update legend gradient color
            const legend = document.querySelector('.legend-gradient');
            if (mode === 'orders') {
                legend.style.background = 'linear-gradient(to right, rgba(59, 130, 246, 0.1), rgba(59, 130, 246, 1))';
            } else {
                legend.style.background = 'linear-gradient(to right, rgba(16, 185, 129, 0.1), rgba(16, 185, 129, 1))';
            }
        }

        function updateChart() {
            const kpi = document.getElementById('chartKpi').value;
            const showComparison = document.getElementById('showComparison').checked;
            // Use actual dates instead of "Day 1, Day 2"
            const labels = chartData.map(d => {
                const date = new Date(d.order_date);
                return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
            });

            let data, dataPrev, label, color, isCurrency = true, isPercent = false;

            switch(kpi) {
                case 'gross':
                    data = chartData.map(d => d.gross);
                    dataPrev = chartDataPrev.map(d => d.gross);
                    label = 'Gross Revenue';
                    color = '#3b82f6';
                    break;
                case 'net':
                    data = chartData.map(d => d.net);
                    dataPrev = chartDataPrev.map(d => d.net);
                    label = 'Net Payout';
                    color = '#10b981';
                    break;
                case 'orders':
                    data = chartData.map(d => d.orders);
                    dataPrev = chartDataPrev.map(d => d.orders);
                    label = 'Orders';
                    color = '#8b5cf6';
                    isCurrency = false;
                    break;
                case 'aov':
                    data = chartData.map(d => d.aov);
                    dataPrev = chartDataPrev.map(d => d.aov);
                    label = 'Avg Order Value';
                    color = '#f59e0b';
                    break;
                case 'margin':
                    data = chartData.map(d => d.margin);
                    dataPrev = chartDataPrev.map(d => d.margin);
                    label = 'Margin %';
                    color = '#ef4444';
                    isCurrency = false;
                    isPercent = true;
                    break;
            }

            if (chart) {
                chart.destroy();
            }

            const datasets = [{
                label: label + ' (Current)',
                data: data,
                borderColor: color,
                backgroundColor: color + '20',
                fill: true,
                tension: 0.3,
                borderWidth: 2
            }];

            if (showComparison && dataPrev.length > 0) {
                datasets.push({
                    label: label + ' (Previous)',
                    data: dataPrev,
                    borderColor: '#9ca3af',
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.3,
                    borderWidth: 2,
                    borderDash: [5, 5]
                });
            }

            chart = new Chart(document.getElementById('revenueChart'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: showComparison && dataPrev.length > 0,
                            position: 'bottom'
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    const idx = context[0].dataIndex;
                                    const currentDate = chartData[idx]?.order_date || '';
                                    const prevDate = chartDataPrev[idx]?.order_date || '';
                                    return currentDate + (prevDate ? ' vs ' + prevDate : '');
                                }
                            }
                        }
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
