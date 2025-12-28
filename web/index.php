<?php
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/functions.php';

require_login();

$brands = get_brands();

// If user is tied to a single brand, redirect to their dashboard
$user_brand_id = get_user_brand_id();
if ($user_brand_id && get_user_role() !== 'admin') {
    header("Location: brand.php?id=" . $user_brand_id);
    exit;
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Brand - Delivery Analytics</title>
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
        <h1>Select Brand</h1>

        <?php if (empty($brands)): ?>
        <div class="card">
            <p class="empty">No brands yet. Import some invoices first using <code>python import.py</code></p>
        </div>
        <?php else: ?>
        <div class="brand-grid">
            <?php foreach ($brands as $brand): ?>
            <a href="brand.php?id=<?= $brand['id'] ?>" class="brand-card">
                <div class="brand-name"><?= h($brand['name']) ?></div>
                <div class="brand-stats">
                    <span><?= $brand['location_count'] ?> location<?= $brand['location_count'] != 1 ? 's' : '' ?></span>
                    <span class="separator">•</span>
                    <span><?= number_format($brand['order_count']) ?> orders</span>
                </div>
                <div class="brand-revenue">
                    <span class="revenue-label">Total Gross</span>
                    <span class="revenue-value"><?= format_money($brand['total_gross']) ?></span>
                </div>
            </a>
            <?php endforeach; ?>
        </div>
        <?php endif; ?>
    </div>
</body>
</html>
