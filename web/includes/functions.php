<?php
/**
 * Dashboard Helper Functions
 */

require_once __DIR__ . '/db.php';

// === FORMATTING ===

function format_money(float $amount): string {
    return number_format($amount, 2, ',', '.') . ' €';
}

function format_percent(float $rate): string {
    return number_format($rate, 1, ',', '.') . '%';
}

function format_date(string $date): string {
    return date('d/m/Y', strtotime($date));
}

function format_date_short(string $date): string {
    return date('M j', strtotime($date));
}

function h(string $str): string {
    return htmlspecialchars($str, ENT_QUOTES, 'UTF-8');
}

function format_trend(float $current, float $previous, string $prev_label = ''): array {
    if ($previous == 0) {
        return ['value' => 0, 'direction' => 'neutral', 'label' => '—', 'comparison' => ''];
    }
    $change = (($current - $previous) / $previous) * 100;
    $direction = $change > 0 ? 'up' : ($change < 0 ? 'down' : 'neutral');
    return [
        'value' => abs($change),
        'direction' => $direction,
        'label' => ($change >= 0 ? '+' : '') . number_format($change, 1) . '%',
        'comparison' => $prev_label
    ];
}

// === DATE RANGE HELPERS ===

function get_last_order_date(): string {
    $result = query_one("SELECT MAX(order_date) as last_date FROM orders");
    return $result['last_date'] ?? date('Y-m-d');
}

function get_date_range(string $range, ?string $custom_start = null, ?string $custom_end = null): array {
    $last_date = new DateTime(get_last_order_date());
    $end_date = $last_date->format('Y-m-d');

    // Custom date range
    if ($range === 'custom' && $custom_start && $custom_end) {
        $start = new DateTime($custom_start);
        $end = new DateTime($custom_end);
        $days = $start->diff($end)->days + 1;
        $prev_end = (clone $start)->modify('-1 day');
        $prev_start = (clone $prev_end)->modify("-" . ($days - 1) . " days");

        return [
            'start' => $start->format('Y-m-d'),
            'end' => $end->format('Y-m-d'),
            'prev_start' => $prev_start->format('Y-m-d'),
            'prev_end' => $prev_end->format('Y-m-d'),
            'label' => format_date_short($start->format('Y-m-d')) . ' - ' . format_date_short($end->format('Y-m-d')),
            'prev_label' => format_date_short($prev_start->format('Y-m-d')) . ' - ' . format_date_short($prev_end->format('Y-m-d')),
            'days' => $days,
            'is_partial' => false
        ];
    }

    switch ($range) {
        case 'week':
            $start = (clone $last_date)->modify('monday this week')->format('Y-m-d');
            $prev_start = (clone $last_date)->modify('monday last week')->format('Y-m-d');
            $prev_end = (clone $last_date)->modify('sunday last week')->format('Y-m-d');
            $days_in_period = (new DateTime($end_date))->diff(new DateTime($start))->days + 1;
            // For equivalent comparison, use same number of days from last week
            $prev_end_adj = (clone (new DateTime($prev_start)))->modify("+".($days_in_period-1)." days")->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $end_date,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end_adj,
                'label' => 'This Week',
                'prev_label' => 'vs ' . format_date_short($prev_start) . ' - ' . format_date_short($prev_end_adj),
                'days' => $days_in_period,
                'is_partial' => $days_in_period < 7
            ];
        case 'month':
            $start = $last_date->format('Y-m-01');
            $prev_start = (clone $last_date)->modify('first day of last month')->format('Y-m-d');
            $days_in_period = (new DateTime($end_date))->diff(new DateTime($start))->days + 1;
            $prev_end_adj = (clone (new DateTime($prev_start)))->modify("+".($days_in_period-1)." days")->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $end_date,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end_adj,
                'label' => 'This Month',
                'prev_label' => 'vs ' . format_date_short($prev_start) . ' - ' . format_date_short($prev_end_adj),
                'days' => $days_in_period,
                'is_partial' => $days_in_period < 28
            ];
        case 'year':
            $start = $last_date->format('Y-01-01');
            $prev_start = (clone $last_date)->modify('-1 year')->format('Y-01-01');
            $days_in_period = (new DateTime($end_date))->diff(new DateTime($start))->days + 1;
            $prev_end_adj = (clone (new DateTime($prev_start)))->modify("+".($days_in_period-1)." days")->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $end_date,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end_adj,
                'label' => 'This Year',
                'prev_label' => 'vs ' . format_date_short($prev_start) . ' - ' . format_date_short($prev_end_adj),
                'days' => $days_in_period,
                'is_partial' => true
            ];
        case 'l4l': // Like for Like - last 4 weeks
            $start = (clone $last_date)->modify('-27 days')->format('Y-m-d');
            $prev_start = (clone $last_date)->modify('-55 days')->format('Y-m-d');
            $prev_end = (clone $last_date)->modify('-28 days')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $end_date,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'Last 4 Weeks',
                'prev_label' => 'vs ' . format_date_short($prev_start) . ' - ' . format_date_short($prev_end),
                'days' => 28,
                'is_partial' => false
            ];
        default: // last 30 days
            $start = (clone $last_date)->modify('-29 days')->format('Y-m-d');
            $prev_start = (clone $last_date)->modify('-59 days')->format('Y-m-d');
            $prev_end = (clone $last_date)->modify('-30 days')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $end_date,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'Last 30 Days',
                'prev_label' => 'vs ' . format_date_short($prev_start) . ' - ' . format_date_short($prev_end),
                'days' => 30,
                'is_partial' => false
            ];
    }
}

// === BRAND QUERIES ===

function get_brands(): array {
    return query("SELECT id, name, slug FROM brands ORDER BY name ASC");
}

function get_brand(int $id): ?array {
    return query_one("SELECT * FROM brands WHERE id = ?", [$id]);
}

// === HERO METRICS ===

function get_hero_metrics(int $brand_id, string $start, string $end): array {
    $sql = "
        SELECT
            COALESCE(SUM(o.gross_value), 0) as gross,
            COALESCE(SUM(o.net_payout), 0) as net,
            COUNT(o.id) as orders,
            COALESCE(AVG(o.gross_value), 0) as aov,
            CASE WHEN SUM(o.gross_value) > 0
                THEN (SUM(o.net_payout) / SUM(o.gross_value)) * 100
                ELSE 0 END as margin
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    return query_one($sql, [$brand_id, $start, $end]) ?: [
        'gross' => 0, 'net' => 0, 'orders' => 0, 'aov' => 0, 'margin' => 0
    ];
}

function get_hero_metrics_with_trends(int $brand_id, array $date_range): array {
    $current = get_hero_metrics($brand_id, $date_range['start'], $date_range['end']);
    $previous = get_hero_metrics($brand_id, $date_range['prev_start'], $date_range['prev_end']);
    $prev_label = $date_range['prev_label'] ?? '';

    return [
        'gross' => [
            'value' => $current['gross'],
            'trend' => format_trend($current['gross'], $previous['gross'], $prev_label)
        ],
        'net' => [
            'value' => $current['net'],
            'trend' => format_trend($current['net'], $previous['net'], $prev_label)
        ],
        'orders' => [
            'value' => $current['orders'],
            'trend' => format_trend($current['orders'], $previous['orders'], $prev_label)
        ],
        'aov' => [
            'value' => $current['aov'],
            'trend' => format_trend($current['aov'], $previous['aov'], $prev_label)
        ],
        'margin' => [
            'value' => $current['margin'],
            'trend' => format_trend($current['margin'], $previous['margin'], $prev_label)
        ]
    ];
}

// === PLATFORM COSTS ===

function get_platform_costs(int $brand_id, string $start, string $end, float $gross = 0): array {
    $sql = "
        SELECT
            COALESCE(SUM(o.commission), 0) as commission,
            COALESCE(SUM(o.refund), 0) as refunds,
            COALESCE(SUM(o.gross_value), 0) as period_gross,
            COALESCE(SUM(o.net_payout), 0) as period_net,
            COALESCE(SUM(o.vat), 0) as vat
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $result = query_one($sql, [$brand_id, $start, $end]) ?: [
        'commission' => 0, 'refunds' => 0, 'period_gross' => 0, 'period_net' => 0, 'vat' => 0
    ];

    // Calculate avg_rate from actual values (commission / gross * 100)
    $result['avg_rate'] = $result['period_gross'] > 0
        ? ($result['commission'] / $result['period_gross']) * 100
        : 0;

    // Calculate refund % of net
    $result['refund_pct'] = $result['period_net'] > 0
        ? ($result['refunds'] / $result['period_net']) * 100
        : 0;

    $result['total'] = $result['commission'] + $result['refunds'];

    return $result;
}

// === PROMOS & MARKETING ===

function get_promo_stats(int $brand_id, string $start, string $end): array {
    $sql = "
        SELECT
            COALESCE(SUM(o.promo_restaurant), 0) as restaurant_promos,
            COALESCE(SUM(o.promo_platform), 0) as platform_promos,
            COALESCE(SUM(o.tips), 0) as tips,
            COALESCE(SUM(o.gross_value), 0) as period_gross
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $result = query_one($sql, [$brand_id, $start, $end]) ?: [
        'restaurant_promos' => 0, 'platform_promos' => 0, 'tips' => 0, 'period_gross' => 0
    ];
    $result['total_promos'] = $result['restaurant_promos'] + $result['platform_promos'];

    // Calculate percentages of gross
    $gross = $result['period_gross'];
    $result['restaurant_pct'] = $gross > 0 ? ($result['restaurant_promos'] / $gross) * 100 : 0;
    $result['platform_pct'] = $gross > 0 ? ($result['platform_promos'] / $gross) * 100 : 0;
    $result['total_pct'] = $gross > 0 ? ($result['total_promos'] / $gross) * 100 : 0;

    return $result;
}

// === ORDER BREAKDOWN ===

function get_order_breakdown(int $brand_id, string $start, string $end): array {
    // Cash vs Card
    $cash_sql = "
        SELECT
            SUM(CASE WHEN o.is_cash = 1 THEN 1 ELSE 0 END) as cash_orders,
            SUM(CASE WHEN o.is_cash = 0 THEN 1 ELSE 0 END) as card_orders,
            SUM(CASE WHEN o.is_cash = 1 THEN o.gross_value ELSE 0 END) as cash_value,
            SUM(CASE WHEN o.is_cash = 0 THEN o.gross_value ELSE 0 END) as card_value
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $cash = query_one($cash_sql, [$brand_id, $start, $end]) ?: [
        'cash_orders' => 0, 'card_orders' => 0, 'cash_value' => 0, 'card_value' => 0
    ];

    // By platform - calculate avg_rate from actual values
    $platform_sql = "
        SELECT
            o.platform,
            COUNT(o.id) as orders,
            SUM(o.gross_value) as gross,
            SUM(o.net_payout) as net,
            SUM(o.commission) as commission
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        GROUP BY o.platform
        ORDER BY gross DESC
    ";
    $platforms = query($platform_sql, [$brand_id, $start, $end]);

    // Calculate avg_rate for each platform
    foreach ($platforms as &$p) {
        $p['avg_rate'] = $p['gross'] > 0 ? ($p['commission'] / $p['gross']) * 100 : 0;
    }

    return [
        'cash' => $cash,
        'platforms' => $platforms
    ];
}

// === GROWTH COMPARISONS ===

function get_growth_comparisons(int $brand_id): array {
    $last_date = new DateTime(get_last_order_date());
    $end_date = $last_date->format('Y-m-d');

    // Week over Week
    $this_week_start = (clone $last_date)->modify('monday this week')->format('Y-m-d');
    $last_week_start = (clone $last_date)->modify('monday last week')->format('Y-m-d');
    $days_this_week = $last_date->diff(new DateTime($this_week_start))->days + 1;
    $last_week_end = (clone (new DateTime($last_week_start)))->modify("+".($days_this_week-1)." days")->format('Y-m-d');

    $this_week = get_hero_metrics($brand_id, $this_week_start, $end_date);
    $last_week = get_hero_metrics($brand_id, $last_week_start, $last_week_end);
    $wow = format_trend($this_week['gross'], $last_week['gross']);
    $wow['period'] = format_date_short($this_week_start) . ' - ' . format_date_short($end_date);
    $wow['vs_period'] = format_date_short($last_week_start) . ' - ' . format_date_short($last_week_end);

    // Month over Month
    $this_month_start = $last_date->format('Y-m-01');
    $last_month_start = (clone $last_date)->modify('first day of last month')->format('Y-m-d');
    $days_this_month = $last_date->diff(new DateTime($this_month_start))->days + 1;
    $last_month_end = (clone (new DateTime($last_month_start)))->modify("+".($days_this_month-1)." days")->format('Y-m-d');

    $this_month = get_hero_metrics($brand_id, $this_month_start, $end_date);
    $last_month = get_hero_metrics($brand_id, $last_month_start, $last_month_end);
    $mom = format_trend($this_month['gross'], $last_month['gross']);
    $mom['period'] = format_date_short($this_month_start) . ' - ' . format_date_short($end_date);
    $mom['vs_period'] = format_date_short($last_month_start) . ' - ' . format_date_short($last_month_end);

    // Year over Year - same period last year
    $yoy_end_last_year = (clone $last_date)->modify('-1 year')->format('Y-m-d');
    $yoy_start_last_year = (clone $last_date)->modify('-1 year')->format('Y-01-01');
    $this_year_start = $last_date->format('Y-01-01');

    $this_year = get_hero_metrics($brand_id, $this_year_start, $end_date);
    $last_year = get_hero_metrics($brand_id, $yoy_start_last_year, $yoy_end_last_year);
    $yoy = format_trend($this_year['gross'], $last_year['gross']);
    $yoy['period'] = format_date_short($this_year_start) . ' - ' . format_date_short($end_date);
    $yoy['vs_period'] = format_date_short($yoy_start_last_year) . ' - ' . format_date_short($yoy_end_last_year);

    // Like for Like (L4W vs previous 4 weeks)
    $l4l_start = (clone $last_date)->modify('-27 days')->format('Y-m-d');
    $prev_l4l_start = (clone $last_date)->modify('-55 days')->format('Y-m-d');
    $prev_l4l_end = (clone $last_date)->modify('-28 days')->format('Y-m-d');

    $l4l_current = get_hero_metrics($brand_id, $l4l_start, $end_date);
    $l4l_prev = get_hero_metrics($brand_id, $prev_l4l_start, $prev_l4l_end);
    $l4l = format_trend($l4l_current['gross'], $l4l_prev['gross']);
    $l4l['period'] = format_date_short($l4l_start) . ' - ' . format_date_short($end_date);
    $l4l['vs_period'] = format_date_short($prev_l4l_start) . ' - ' . format_date_short($prev_l4l_end);

    return [
        'wow' => $wow,
        'mom' => $mom,
        'yoy' => $yoy,
        'l4l' => $l4l
    ];
}

// === DAY PATTERNS ===

function get_day_patterns(int $brand_id, string $start, string $end): array {
    // Get average daily revenue by day of week
    $sql = "
        SELECT
            strftime('%w', o.order_date) as day_num,
            CASE strftime('%w', o.order_date)
                WHEN '0' THEN 'Sunday'
                WHEN '1' THEN 'Monday'
                WHEN '2' THEN 'Tuesday'
                WHEN '3' THEN 'Wednesday'
                WHEN '4' THEN 'Thursday'
                WHEN '5' THEN 'Friday'
                WHEN '6' THEN 'Saturday'
            END as day_name,
            COUNT(DISTINCT o.order_date) as num_days,
            COUNT(o.id) as total_orders,
            SUM(o.gross_value) as total_gross,
            SUM(o.gross_value) / COUNT(DISTINCT o.order_date) as avg_daily_gross,
            COUNT(o.id) * 1.0 / COUNT(DISTINCT o.order_date) as avg_daily_orders
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        GROUP BY day_num
        ORDER BY day_num
    ";
    $days = query($sql, [$brand_id, $start, $end]);

    // Reorder to start from Monday (1,2,3,4,5,6,0)
    $reordered = [];
    foreach ([1,2,3,4,5,6,0] as $target) {
        foreach ($days as $day) {
            if ((int)$day['day_num'] === $target) {
                $reordered[] = $day;
                break;
            }
        }
    }

    $best = null;
    $worst = null;
    foreach ($reordered as $day) {
        if ($best === null || $day['avg_daily_gross'] > $best['avg_daily_gross']) {
            $best = $day;
        }
        if ($worst === null || $day['avg_daily_gross'] < $worst['avg_daily_gross']) {
            $worst = $day;
        }
    }

    return [
        'days' => $reordered,
        'best' => $best,
        'worst' => $worst
    ];
}

// === DAILY DATA FOR CHARTS ===

function get_daily_data(int $brand_id, string $start, string $end): array {
    $sql = "
        SELECT
            o.order_date,
            COUNT(o.id) as orders,
            SUM(o.gross_value) as gross,
            SUM(o.net_payout) as net,
            SUM(o.commission) as commission,
            AVG(o.gross_value) as aov,
            CASE WHEN SUM(o.gross_value) > 0
                THEN (SUM(o.net_payout) / SUM(o.gross_value)) * 100
                ELSE 0 END as margin
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        GROUP BY o.order_date
        ORDER BY o.order_date
    ";
    return query($sql, [$brand_id, $start, $end]);
}

// === KPI INFO TOOLTIPS ===

function get_kpi_tooltips(): array {
    return [
        'gross' => 'Total order value including VAT',
        'net' => 'Amount received after all platform costs (commission, refunds, fees)',
        'orders' => 'Total number of orders in the period',
        'aov' => 'Average Order Value = Gross Revenue / Number of Orders',
        'margin' => 'Platform Margin = (Net / Gross) × 100 - what you keep after fees',
        'commission' => 'Platform fee charged on each order',
        'avg_rate' => 'Average Commission Rate = (Total Commission / Gross) × 100',
        'refunds' => 'Money returned to customers for cancelled or problematic orders',
        'restaurant_promos' => 'Discounts funded by your restaurant',
        'platform_promos' => 'Discounts funded by the delivery platform',
        'tips' => 'Customer tips received'
    ];
}
