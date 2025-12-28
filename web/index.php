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

    <div class="container brand-selector">
        <h1>Select Brand</h1>

        <?php if (empty($brands)): ?>
        <p class="empty">No brands yet. Import some invoices first.</p>
        <?php else: ?>
        <ul class="brand-list">
            <?php foreach ($brands as $brand): ?>
            <li>
                <a href="brand.php?id=<?= $brand['id'] ?>"><?= h($brand['name']) ?></a>
            </li>
            <?php endforeach; ?>
        </ul>
        <?php endif; ?>
    </div>
</body>
</html>
