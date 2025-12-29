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
        case 'l4l': // Like for Like - last 4 weeks vs SAME 4 weeks LAST YEAR
            $start = (clone $last_date)->modify('-27 days')->format('Y-m-d');
            // Same period LAST YEAR (not previous 4 weeks)
            $prev_start = (clone $last_date)->modify('-1 year')->modify('-27 days')->format('Y-m-d');
            $prev_end = (clone $last_date)->modify('-1 year')->format('Y-m-d');
            return [
                'start' => $start,
                'end' => $end_date,
                'prev_start' => $prev_start,
                'prev_end' => $prev_end,
                'label' => 'Last 4 Weeks (L4L)',
                'prev_label' => 'vs ' . format_date_short($prev_start) . ' - ' . format_date_short($prev_end) . ' (LY)',
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
            COALESCE(SUM(o.gross_value), 0) as raw_gross,
            COALESCE(SUM(o.net_payout), 0) as net_payout,
            COUNT(o.id) as orders,
            COALESCE(SUM(o.promo_restaurant), 0) as promo_restaurant,
            COALESCE(SUM(o.commission), 0) as commission,
            COALESCE(SUM(o.discount_commission), 0) as discount_commission,
            COALESCE(SUM(o.refund), 0) as refunds,
            COALESCE(SUM(o.ad_fee), 0) as ad_fee
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $row = query_one($sql, [$brand_id, $start, $end]) ?: [
        'raw_gross' => 0, 'net_payout' => 0, 'orders' => 0, 'promo_restaurant' => 0,
        'commission' => 0, 'discount_commission' => 0, 'refunds' => 0, 'ad_fee' => 0
    ];

    // NEW CALCULATIONS:
    // Gross Revenue = SUM(gross_value) * 0.9 (remove 10% VAT)
    $gross = $row['raw_gross'] * 0.9;

    // Net Revenue = Gross Revenue - Restaurant Funded Discounts
    $net_revenue = $gross - $row['promo_restaurant'];

    // Net Payout = Net Revenue - Commission - Commission on Funded - Refunds - Ads
    $net_payout = $net_revenue - $row['commission'] - $row['discount_commission'] - $row['refunds'] - $row['ad_fee'];

    // AOV = Gross Revenue / Orders
    $aov = $row['orders'] > 0 ? $gross / $row['orders'] : 0;

    // Platform Margin = Net Payout / Gross Revenue × 100
    $margin = $gross > 0 ? ($net_payout / $gross) * 100 : 0;

    return [
        'gross' => $gross,
        'net_revenue' => $net_revenue,
        'net_payout' => $net_payout,
        'orders' => $row['orders'],
        'aov' => $aov,
        'margin' => $margin,
        // Keep raw values for other calculations
        'raw_gross' => $row['raw_gross'],
        'promo_restaurant' => $row['promo_restaurant'],
        'commission' => $row['commission'],
        'discount_commission' => $row['discount_commission'],
        'refunds' => $row['refunds'],
        'ad_fee' => $row['ad_fee']
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
        'net_payout' => [
            'value' => $current['net_payout'],
            'trend' => format_trend($current['net_payout'], $previous['net_payout'], $prev_label)
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
        ],
        // Pass through net_revenue for cost calculations
        'net_revenue' => $current['net_revenue']
    ];
}

// === PLATFORM COSTS ===

function get_platform_costs(int $brand_id, string $start, string $end, float $net_revenue = 0): array {
    $sql = "
        SELECT
            COALESCE(SUM(o.commission), 0) as commission,
            COALESCE(SUM(o.refund), 0) as refunds,
            COALESCE(SUM(o.gross_value), 0) as period_gross,
            COALESCE(SUM(o.net_payout), 0) as period_net,
            COALESCE(SUM(o.vat), 0) as vat,
            COALESCE(SUM(o.ad_fee), 0) as ad_fee,
            COALESCE(SUM(o.discount_commission), 0) as discount_commission,
            COALESCE(SUM(o.promo_restaurant), 0) as promo_restaurant,
            COALESCE(SUM(o.promo_platform), 0) as promo_platform
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $result = query_one($sql, [$brand_id, $start, $end]) ?: [
        'commission' => 0, 'refunds' => 0, 'period_gross' => 0, 'period_net' => 0,
        'vat' => 0, 'ad_fee' => 0, 'discount_commission' => 0, 'promo_restaurant' => 0, 'promo_platform' => 0
    ];

    // Calculate net_revenue if not provided
    // Net Revenue = Gross (with VAT removed) - Restaurant Funded Discounts
    $gross_no_vat = $result['period_gross'] * 0.9;
    $calculated_net_revenue = $net_revenue > 0 ? $net_revenue : ($gross_no_vat - $result['promo_restaurant']);
    $result['net_revenue'] = $calculated_net_revenue;

    // All percentages are now "% of net revenue"
    $result['commission_pct'] = $calculated_net_revenue > 0
        ? ($result['commission'] / $calculated_net_revenue) * 100
        : 0;

    $result['discount_commission_pct'] = $calculated_net_revenue > 0
        ? ($result['discount_commission'] / $calculated_net_revenue) * 100
        : 0;

    $result['refund_pct'] = $calculated_net_revenue > 0
        ? ($result['refunds'] / $calculated_net_revenue) * 100
        : 0;

    $result['ad_fee_pct'] = $calculated_net_revenue > 0
        ? ($result['ad_fee'] / $calculated_net_revenue) * 100
        : 0;

    $result['platform_promo_pct'] = $calculated_net_revenue > 0
        ? ($result['promo_platform'] / $calculated_net_revenue) * 100
        : 0;

    $result['total'] = $result['commission'] + $result['discount_commission'] + $result['refunds'] + $result['ad_fee'];

    return $result;
}

// === PROMOS & MARKETING ===

function get_promo_stats(int $brand_id, string $start, string $end, float $net_revenue = 0): array {
    $sql = "
        SELECT
            COALESCE(SUM(o.promo_restaurant), 0) as restaurant_promos,
            COALESCE(SUM(o.promo_platform), 0) as platform_promos,
            COALESCE(SUM(o.ad_fee), 0) as ads,
            COALESCE(SUM(o.gross_value), 0) as period_gross
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
    ";
    $result = query_one($sql, [$brand_id, $start, $end]) ?: [
        'restaurant_promos' => 0, 'platform_promos' => 0, 'ads' => 0, 'period_gross' => 0
    ];
    $result['total_promos'] = $result['restaurant_promos'] + $result['platform_promos'];

    // Calculate net_revenue if not provided
    $gross_no_vat = $result['period_gross'] * 0.9;
    $calculated_net_revenue = $net_revenue > 0 ? $net_revenue : ($gross_no_vat - $result['restaurant_promos']);
    $result['net_revenue'] = $calculated_net_revenue;

    // All percentages are now "% of net revenue"
    $result['restaurant_pct'] = $calculated_net_revenue > 0 ? ($result['restaurant_promos'] / $calculated_net_revenue) * 100 : 0;
    $result['platform_pct'] = $calculated_net_revenue > 0 ? ($result['platform_promos'] / $calculated_net_revenue) * 100 : 0;
    $result['ads_pct'] = $calculated_net_revenue > 0 ? ($result['ads'] / $calculated_net_revenue) * 100 : 0;
    $result['total_pct'] = $calculated_net_revenue > 0 ? ($result['total_promos'] / $calculated_net_revenue) * 100 : 0;

    return $result;
}

// === REFUNDS BREAKDOWN ===

function normalize_fault(string $fault): string {
    $fault = trim($fault);
    if (empty($fault) || $fault === 'Unknown' || $fault === 'null') {
        return 'Unknown';
    }
    $lower = strtolower($fault);
    if (strpos($lower, 'platform') !== false || strpos($lower, 'deliveroo') !== false) {
        return 'Platform';
    }
    if (strpos($lower, 'restaurant') !== false) {
        return 'Restaurant';
    }
    return ucfirst($fault);
}

function get_refund_breakdown(int $brand_id, string $start, string $end): array {
    // Get refunds by reason
    $sql = "
        SELECT
            COALESCE(o.refund_reason, 'Unknown') as reason,
            COALESCE(o.refund_fault, 'Unknown') as fault,
            COUNT(*) as count,
            SUM(o.refund) as amount
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE l.brand_id = ?
        AND o.order_date BETWEEN ? AND ?
        AND o.refund > 0
        GROUP BY o.refund_reason, o.refund_fault
        ORDER BY amount DESC
    ";
    $refunds = query($sql, [$brand_id, $start, $end]);

    // Calculate totals
    $total_amount = array_sum(array_column($refunds, 'amount'));
    $total_count = array_sum(array_column($refunds, 'count'));

    // Normalize fault values and add percentages
    $by_fault = ['Restaurant' => ['count' => 0, 'amount' => 0], 'Platform' => ['count' => 0, 'amount' => 0], 'Unknown' => ['count' => 0, 'amount' => 0]];

    foreach ($refunds as &$r) {
        $r['fault'] = normalize_fault($r['fault']);
        $r['pct'] = $total_amount > 0 ? ($r['amount'] / $total_amount) * 100 : 0;

        // Aggregate by fault party
        $fault_key = $r['fault'];
        if (!isset($by_fault[$fault_key])) {
            $by_fault[$fault_key] = ['count' => 0, 'amount' => 0];
        }
        $by_fault[$fault_key]['count'] += $r['count'];
        $by_fault[$fault_key]['amount'] += $r['amount'];
    }

    // Add percentages to by_fault
    foreach ($by_fault as $key => &$data) {
        $data['pct'] = $total_amount > 0 ? ($data['amount'] / $total_amount) * 100 : 0;
    }

    // Sort by_fault by amount descending
    uasort($by_fault, fn($a, $b) => $b['amount'] <=> $a['amount']);

    $restaurant_fault_amount = $by_fault['Restaurant']['amount'] ?? 0;
    $platform_fault_amount = $by_fault['Platform']['amount'] ?? 0;

    return [
        'items' => $refunds,
        'by_fault' => $by_fault,
        'total_amount' => $total_amount,
        'total_count' => $total_count,
        'restaurant_fault_amount' => $restaurant_fault_amount,
        'restaurant_fault_pct' => $total_amount > 0 ? ($restaurant_fault_amount / $total_amount) * 100 : 0,
        'platform_fault_amount' => $platform_fault_amount,
        'platform_fault_pct' => $total_amount > 0 ? ($platform_fault_amount / $total_amount) * 100 : 0
    ];
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

    // Like for Like - Last 4 weeks vs same 4 weeks LAST YEAR
    $l4l_start = (clone $last_date)->modify('-27 days')->format('Y-m-d');
    $l4l_end = $end_date;
    // Same period last year
    $l4l_start_ly = (clone $last_date)->modify('-1 year')->modify('-27 days')->format('Y-m-d');
    $l4l_end_ly = (clone $last_date)->modify('-1 year')->format('Y-m-d');

    $l4l_current = get_hero_metrics($brand_id, $l4l_start, $l4l_end);
    $l4l_prev = get_hero_metrics($brand_id, $l4l_start_ly, $l4l_end_ly);
    $l4l = format_trend($l4l_current['gross'], $l4l_prev['gross']);
    $l4l['period'] = format_date_short($l4l_start) . ' - ' . format_date_short($l4l_end);
    $l4l['vs_period'] = format_date_short($l4l_start_ly) . ' - ' . format_date_short($l4l_end_ly) . ' (LY)';

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
        'gross' => 'Total order value net of 10% VAT',
        'net_revenue' => 'Gross revenue minus restaurant-funded discounts',
        'net_payout' => 'Amount received after all platform costs and fees',
        'orders' => 'Total number of orders',
        'aov' => 'Average Order Value = Gross Revenue / Orders',
        'margin' => 'Net Payout / Gross Revenue × 100 - what you keep',
        'commission' => 'Platform fee on each order',
        'discount_commission' => 'Commission charged on restaurant-funded discount amounts',
        'refunds' => 'Money returned to customers for complaints',
        'ad_fee' => 'Annunci Marketer - paid advertising on the platform',
        'restaurant_promos' => 'Discount amounts funded by the restaurant for promotions',
        'platform_promos' => 'Discount amounts funded by Deliveroo'
    ];
}
