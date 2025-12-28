<?php
/**
 * Authentication helpers
 */

require_once __DIR__ . '/db.php';

session_start();

function is_logged_in(): bool {
    return isset($_SESSION['user_id']);
}

function require_login(): void {
    if (!is_logged_in()) {
        header('Location: login.php');
        exit;
    }
}

function require_admin(): void {
    require_login();
    if (get_user_role() !== 'admin') {
        http_response_code(403);
        die('Access denied');
    }
}

function get_user_id(): ?int {
    return $_SESSION['user_id'] ?? null;
}

function get_user_email(): ?string {
    return $_SESSION['user_email'] ?? null;
}

function get_user_role(): ?string {
    return $_SESSION['user_role'] ?? null;
}

function get_user_brand_id(): ?int {
    return $_SESSION['user_brand_id'] ?? null;
}

function can_view_brand(int $brand_id): bool {
    if (!is_logged_in()) return false;
    if (get_user_role() === 'admin') return true;
    return get_user_brand_id() === $brand_id;
}

function login(string $email, string $password): bool {
    $user = query_one(
        "SELECT id, email, password_hash, role, brand_id FROM users WHERE email = ?",
        [$email]
    );

    if (!$user || !password_verify($password, $user['password_hash'])) {
        return false;
    }

    $_SESSION['user_id'] = $user['id'];
    $_SESSION['user_email'] = $user['email'];
    $_SESSION['user_role'] = $user['role'];
    $_SESSION['user_brand_id'] = $user['brand_id'];

    return true;
}

function logout(): void {
    session_destroy();
    header('Location: login.php');
    exit;
}

function create_user(string $email, string $password, string $role = 'viewer', ?int $brand_id = null): int {
    $hash = password_hash($password, PASSWORD_DEFAULT);
    execute(
        "INSERT INTO users (email, password_hash, role, brand_id) VALUES (?, ?, ?, ?)",
        [$email, $hash, $role, $brand_id]
    );
    return get_db()->lastInsertId();
}

// Create default admin if no users exist
function ensure_admin_exists(): void {
    $count = query_one("SELECT COUNT(*) as c FROM users")['c'];
    if ($count === 0) {
        create_user('admin@example.com', 'admin123', 'admin', null);
    }
}
