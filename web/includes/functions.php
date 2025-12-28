<?php
/**
 * Helper functions
 */

require_once __DIR__ . '/db.php';

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

// Dashboard stats
function get_dashboard_stats(?int $brand_id = null): array {
    $where = $brand_id ? "WHERE l.brand_id = ?" : "";
    $params = $brand_id ? [$brand_id] : [];

    $sql = "
        SELECT
            COUNT(DISTINCT o.id) as total_orders,
            COALESCE(SUM(o.gross_value), 0) as total_gross,
            COALESCE(SUM(o.commission), 0) as total_commission,
            COALESCE(SUM(o.net_payout), 0) as total_net,
            COALESCE(SUM(o.refund), 0) as total_refunds,
            COUNT(DISTINCT l.id) as total_locations,
            COUNT(DISTINCT l.brand_id) as total_brands
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        $where
    ";

    return query_one($sql, $params) ?: [];
}

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

function get_orders_by_date(?int $brand_id = null, int $days = 30): array {
    $where = $brand_id ? "AND l.brand_id = ?" : "";
    $params = [$days];
    if ($brand_id) $params[] = $brand_id;

    return query("
        SELECT
            o.order_date,
            COUNT(*) as order_count,
            SUM(o.gross_value) as gross,
            SUM(o.commission) as commission,
            SUM(o.net_payout) as net
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        WHERE o.order_date >= date('now', '-' || ? || ' days')
        $where
        GROUP BY o.order_date
        ORDER BY o.order_date
    ", $params);
}

function get_platform_breakdown(?int $brand_id = null): array {
    $where = $brand_id ? "WHERE l.brand_id = ?" : "";
    $params = $brand_id ? [$brand_id] : [];

    return query("
        SELECT
            o.platform,
            COUNT(*) as order_count,
            SUM(o.gross_value) as gross,
            SUM(o.commission) as commission,
            SUM(o.net_payout) as net,
            AVG(o.commission_rate) as avg_commission_rate
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        $where
        GROUP BY o.platform
        ORDER BY gross DESC
    ", $params);
}

function get_recent_orders(?int $brand_id = null, int $limit = 50): array {
    $where = $brand_id ? "WHERE l.brand_id = ?" : "";
    $params = $brand_id ? [$brand_id, $limit] : [$limit];

    return query("
        SELECT o.*, l.name as location_name, b.name as brand_name
        FROM orders o
        JOIN locations l ON o.location_id = l.id
        JOIN brands b ON l.brand_id = b.id
        $where
        ORDER BY o.order_date DESC, o.id DESC
        LIMIT ?
    ", $params);
}
