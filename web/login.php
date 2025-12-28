<?php
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/functions.php';

// Ensure admin exists
ensure_admin_exists();

// Handle logout
if (isset($_GET['logout'])) {
    logout();
}

// Already logged in?
if (is_logged_in()) {
    header('Location: index.php');
    exit;
}

$error = '';

// Handle login
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';

    if (login($email, $password)) {
        header('Location: index.php');
        exit;
    } else {
        $error = 'Invalid email or password';
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Delivery Analytics</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body class="login-page">
    <div class="login-container">
        <h1>Delivery Analytics</h1>
        <p class="subtitle">Multi-brand delivery platform dashboard</p>

        <?php if ($error): ?>
            <div class="alert alert-error"><?= h($error) ?></div>
        <?php endif; ?>

        <form method="POST" class="login-form">
            <label for="email">Email</label>
            <input type="email" name="email" id="email" required placeholder="admin@example.com">

            <label for="password">Password</label>
            <input type="password" name="password" id="password" required placeholder="Enter password">

            <button type="submit" class="btn btn-primary btn-block">Log In</button>
        </form>

        <p class="login-hint">
            Default: admin@example.com / admin123
        </p>
    </div>
</body>
</html>
