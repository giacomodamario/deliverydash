<?php
/**
 * JSON API endpoints
 */

require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

header('Content-Type: application/json');

if (!is_logged_in()) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

$action = $_GET['action'] ?? '';
$brand_id = get_user_brand_id();

// Admin can view any brand
if (get_user_role() === 'admin' && isset($_GET['brand_id'])) {
    $brand_id = (int)$_GET['brand_id'];
}

switch ($action) {
    case 'stats':
        echo json_encode(get_dashboard_stats($brand_id));
        break;

    case 'brands':
        if (get_user_role() !== 'admin') {
            http_response_code(403);
            echo json_encode(['error' => 'Forbidden']);
            exit;
        }
        echo json_encode(get_brands());
        break;

    case 'brand':
        $id = (int)($_GET['id'] ?? 0);
        if (!can_view_brand($id)) {
            http_response_code(403);
            echo json_encode(['error' => 'Forbidden']);
            exit;
        }
        echo json_encode([
            'brand' => get_brand($id),
            'locations' => get_brand_locations($id),
            'stats' => get_dashboard_stats($id),
        ]);
        break;

    case 'orders_by_date':
        $days = (int)($_GET['days'] ?? 30);
        echo json_encode(get_orders_by_date($brand_id, $days));
        break;

    case 'platform_breakdown':
        echo json_encode(get_platform_breakdown($brand_id));
        break;

    case 'recent_orders':
        $limit = min((int)($_GET['limit'] ?? 50), 500);
        echo json_encode(get_recent_orders($brand_id, $limit));
        break;

    default:
        http_response_code(400);
        echo json_encode(['error' => 'Unknown action']);
}
