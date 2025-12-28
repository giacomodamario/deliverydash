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

function h(string $str): string {
    return htmlspecialchars($str, ENT_QUOTES, 'UTF-8');
}

function format_trend(float $current, float $previous): array {
    if ($previous == 0) {
        return ['value' => 0, 'direction' => 'neutral', 'label' => '—'];
    }
    $change = (($current - $previous) / $previous) * 100;
    $direction = $change > 0 ? 'up' : ($change < 0 ? 'down' : 'neutral');
    return [
        'value' => abs($change),
        'direction' => $direction,
        'label' => ($change >= 0 ? '+' : '') . number_format($change, 1) . '%'
    ];
}

// === DATE RANGE HELPERS ===

function get_date_range(string $range): array {
    $now = new DateTime();
    $today = $now->format('Y-m-d');

    switch ($range) {
        case 'today':
            return [
                'start' => $today,
                'end' => $today,
                'prev_start' => (clone $now)->modify('-1 day')->format('Y-m-d'),
                'prev_end' => (clone $now)->modify('-1 day')->format('Y-m-d'),
                'label' => 'Today'
            ];
        case 'week':
            $start = (clone $now)->modify('monday this week')->format('Y-m-d');
            $prev_start = (clone $now)->modify('monday last week')->format('Y-m-d');
            $prev_end = (clone $now)->modify('sunday last week')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $today,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'This Week'
            ];
        case 'month':
            $start = $now->format('Y-m-01');
            $prev_start = (clone $now)->modify('first day of last month')->format('Y-m-d');
            $prev_end = (clone $now)->modify('last day of last month')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $today,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'This Month'
            ];
        case 'year':
            $start = $now->format('Y-01-01');
            $prev_start = (clone $now)->modify('-1 year')->format('Y-01-01');
            $prev_end = (clone $now)->modify('-1 year')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $today,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'This Year'
            ];
        case 'l4w': // Last 4 weeks
            $start = (clone $now)->modify('-28 days')->format('Y-m-d');
            $prev_start = (clone $now)->modify('-56 days')->format('Y-m-d');
            $prev_end = (clone $now)->modify('-29 days')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $today,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'Last 4 Weeks'
            ];
        default: // last 30 days
            $start = (clone $now)->modify('-30 days')->format('Y-m-d');
            $prev_start = (clone $now)->modify('-60 days')->format('Y-m-d');
            $prev_end = (clone $now)->modify('-31 days')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $today,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'Last 30 Days'
            ];
    }
}

// === BRAND QUERIES ===

function get_brands(): array {
    return query("
        SELECT b.*,
            COUNT(DISTINCT l.id) as location_count,
            COUNT(DISTINCT o.id) as order_count,
            COALESCE(SUM(o.gross_value), 0) as total_gross,
            COALESCE(SUM(o.net_payout), 0) as total_net
        FROM brands b
        LEFT JOIN locations l ON l.brand_id = b.id
        LEFT JOIN orders o ON o.location_id = l.id
        GROUP BY b.id
        ORDER BY total_gross DESC
    ");
}

function get_brand(int $id): ?array {
    return query_one("SELECT * FROM brands WHERE id = ?", [$id]);
}

function get_brand_locations(int $brand_id): array {
    return query("
        SELECT l.*,
            COUNT(o.id) as order_count,
            COALESCE(SUM(o.gross_value), 0) as total_gross,
            COALESCE(SUM(o.net_payout), 0) as total_net
        FROM locations l
        LEFT JOIN orders o ON o.location_id = l.id
        WHERE l.brand_id = ?
        GROUP BY l.id
        ORDER BY total_gross DESC
    ", [$brand_id]);
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

    return [
        'gross' => [
            'value' => $current['gross'],
            'trend' => format_trend($current['gross'], $previous['gross'])
        ],
        'net' => [
            'value' => $current['net'],
            'trend' => format_trend($current['net'], $previous['net'])
        ],
        'orders' => [
            'value' => $current['orders'],
            'trend' => format_trend($current['orders'], $previous['orders'])
        ],
        'aov' => [
            'value' => $current['aov'],
            'trend' => format_trend($current['aov'], $previous['aov'])
        ],
        'margin' => [
            'value' => $current['margin'],
            'trend' => format_trend($current['margin'], $previous['margin'])
        ]
    ];
}

// === PLATFORM COSTS ===

function get_platform_costs(int $brand_id, string $start, string $end): array {
    $sql = "
        SELECT
            COALESCE(SUM(o.commission), 0) as commission,
            COALESCE(SUM(o.refund), 0) as refunds,
            COALESCE(AVG(o.commission_rate), 0) as avg_rate,
            COALESCE(SUM(o.vat), 0) as vat
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $result = query_one($sql, [$brand_id, $start, $end]) ?: [
        'commission' => 0, 'refunds' => 0, 'avg_rate' => 0, 'vat' => 0
    ];
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
            COALESCE(SUM(o.adjustments), 0) as adjustments
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $result = query_one($sql, [$brand_id, $start, $end]) ?: [
        'restaurant_promos' => 0, 'platform_promos' => 0, 'tips' => 0, 'adjustments' => 0
    ];
    $result['total_promos'] = $result['restaurant_promos'] + $result['platform_promos'];
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

    // By platform
    $platform_sql = "
        SELECT
            o.platform,
            COUNT(o.id) as orders,
            SUM(o.gross_value) as gross,
            SUM(o.net_payout) as net,
            AVG(o.commission_rate) as avg_rate
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        GROUP BY o.platform
        ORDER BY gross DESC
    ";
    $platforms = query($platform_sql, [$brand_id, $start, $end]);

    return [
        'cash' => $cash,
        'platforms' => $platforms
    ];
}

// === GROWTH COMPARISONS ===

function get_growth_comparisons(int $brand_id): array {
    $now = new DateTime();
    $today = $now->format('Y-m-d');

    // Week over Week
    $this_week_start = (clone $now)->modify('monday this week')->format('Y-m-d');
    $last_week_start = (clone $now)->modify('monday last week')->format('Y-m-d');
    $last_week_end = (clone $now)->modify('sunday last week')->format('Y-m-d');

    $this_week = get_hero_metrics($brand_id, $this_week_start, $today);
    $last_week = get_hero_metrics($brand_id, $last_week_start, $last_week_end);
    $wow = format_trend($this_week['gross'], $last_week['gross']);

    // Month over Month
    $this_month_start = $now->format('Y-m-01');
    $last_month_start = (clone $now)->modify('first day of last month')->format('Y-m-d');
    $last_month_end = (clone $now)->modify('last day of last month')->format('Y-m-d');

    $this_month = get_hero_metrics($brand_id, $this_month_start, $today);
    $last_month = get_hero_metrics($brand_id, $last_month_start, $last_month_end);
    $mom = format_trend($this_month['gross'], $last_month['gross']);

    // Year over Year
    $this_year_start = $now->format('Y-01-01');
    $last_year_start = (clone $now)->modify('-1 year')->format('Y-01-01');
    $last_year_end = (clone $now)->modify('-1 year')->format('Y-m-d');

    $this_year = get_hero_metrics($brand_id, $this_year_start, $today);
    $last_year = get_hero_metrics($brand_id, $last_year_start, $last_year_end);
    $yoy = format_trend($this_year['gross'], $last_year['gross']);

    // Like for Like (L4W vs previous 4 weeks)
    $l4w_start = (clone $now)->modify('-28 days')->format('Y-m-d');
    $prev_l4w_start = (clone $now)->modify('-56 days')->format('Y-m-d');
    $prev_l4w_end = (clone $now)->modify('-29 days')->format('Y-m-d');

    $l4w = get_hero_metrics($brand_id, $l4w_start, $today);
    $prev_l4w = get_hero_metrics($brand_id, $prev_l4w_start, $prev_l4w_end);
    $l4l = format_trend($l4w['gross'], $prev_l4w['gross']);

    return [
        'wow' => $wow,
        'mom' => $mom,
        'yoy' => $yoy,
        'l4l' => $l4l
    ];
}

// === DAY PATTERNS ===

function get_day_patterns(int $brand_id, string $start, string $end): array {
    $sql = "
        SELECT
            strftime('%w', o.order_date) as day_num,
            CASE strftime('%w', o.order_date)
                WHEN '0' THEN 'Sun'
                WHEN '1' THEN 'Mon'
                WHEN '2' THEN 'Tue'
                WHEN '3' THEN 'Wed'
                WHEN '4' THEN 'Thu'
                WHEN '5' THEN 'Fri'
                WHEN '6' THEN 'Sat'
            END as day_name,
            COUNT(o.id) as orders,
            SUM(o.gross_value) as gross,
            AVG(o.gross_value) as avg_order
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        GROUP BY day_num
        ORDER BY day_num
    ";
    $days = query($sql, [$brand_id, $start, $end]);

    $best = null;
    $worst = null;
    foreach ($days as $day) {
        if ($best === null || $day['gross'] > $best['gross']) {
            $best = $day;
        }
        if ($worst === null || $day['gross'] < $worst['gross']) {
            $worst = $day;
        }
    }

    return [
        'days' => $days,
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
            SUM(o.commission) as commission
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        GROUP BY o.order_date
        ORDER BY o.order_date
    ";
    return query($sql, [$brand_id, $start, $end]);
}

// === RECENT ORDERS ===

function get_recent_orders(int $brand_id, int $limit = 50): array {
    return query("
        SELECT o.*, l.name as location_name
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        ORDER BY o.order_date DESC, o.id DESC
        LIMIT ?
    ", [$brand_id, $limit]);
}

// === LOCATION BREAKDOWN ===

function get_location_breakdown(int $brand_id, string $start, string $end): array {
    return query("
        SELECT
            l.id,
            l.name,
            l.platform,
            COUNT(o.id) as orders,
            COALESCE(SUM(o.gross_value), 0) as gross,
            COALESCE(SUM(o.net_payout), 0) as net,
            COALESCE(AVG(o.gross_value), 0) as aov
        FROM locations l
        LEFT JOIN orders o ON o.location_id = l.id
            AND o.order_date BETWEEN ? AND ?
        WHERE l.brand_id = ?
        GROUP BY l.id
        ORDER BY gross DESC
    ", [$start, $end, $brand_id]);
}
