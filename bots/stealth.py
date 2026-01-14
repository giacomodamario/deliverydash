"""Stealth utilities for anti-bot detection evasion."""

import random
import math
import time
from typing import Tuple, List


def random_delay(base: float, variance: float = 0.3) -> float:
    """
    Return a randomized delay with human-like variance.

    Args:
        base: Base delay in seconds
        variance: Variance factor (0.3 = ±30%)

    Returns:
        Randomized delay value
    """
    min_delay = base * (1 - variance)
    max_delay = base * (1 + variance)
    return random.uniform(min_delay, max_delay)


def human_sleep(base: float, variance: float = 0.3):
    """Sleep for a randomized duration to appear human-like."""
    time.sleep(random_delay(base, variance))


def random_typing_delay() -> int:
    """
    Return a randomized typing delay in milliseconds.
    Humans type with variable rhythm - faster for common letters,
    slower for awkward key combinations.

    Returns:
        Delay in milliseconds (typically 30-150ms)
    """
    # Base delay with normal distribution around 70ms
    base = random.gauss(70, 25)
    # Clamp to reasonable bounds
    return max(30, min(180, int(base)))


def bezier_curve(
    start: Tuple[float, float],
    end: Tuple[float, float],
    control_points: int = 2
) -> List[Tuple[float, float]]:
    """
    Generate points along a bezier curve for natural mouse movement.

    Args:
        start: Starting (x, y) coordinates
        end: Ending (x, y) coordinates
        control_points: Number of random control points

    Returns:
        List of (x, y) points along the curve
    """
    points = [start]

    # Generate random control points
    controls = []
    for i in range(control_points):
        # Control points deviate from straight line
        t = (i + 1) / (control_points + 1)
        base_x = start[0] + (end[0] - start[0]) * t
        base_y = start[1] + (end[1] - start[1]) * t

        # Add random deviation (more in middle, less at ends)
        deviation = min(100, abs(end[0] - start[0]) * 0.3)
        offset_x = random.gauss(0, deviation * math.sin(t * math.pi))
        offset_y = random.gauss(0, deviation * math.sin(t * math.pi))

        controls.append((base_x + offset_x, base_y + offset_y))

    # Generate curve points
    all_points = [start] + controls + [end]
    num_steps = max(10, int(math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2) / 10))

    for step in range(1, num_steps + 1):
        t = step / num_steps
        # De Casteljau's algorithm for bezier curve
        temp_points = all_points.copy()
        while len(temp_points) > 1:
            new_points = []
            for i in range(len(temp_points) - 1):
                x = temp_points[i][0] * (1-t) + temp_points[i+1][0] * t
                y = temp_points[i][1] * (1-t) + temp_points[i+1][1] * t
                new_points.append((x, y))
            temp_points = new_points
        points.append(temp_points[0])

    return points


def human_mouse_move(page, target_x: float, target_y: float, duration: float = None):
    """
    Move mouse to target with human-like bezier curve path.

    Args:
        page: Playwright page object
        target_x: Target X coordinate
        target_y: Target Y coordinate
        duration: Optional total duration (auto-calculated if None)
    """
    # Get current mouse position (estimate from viewport center if unknown)
    try:
        current = page.evaluate("() => ({x: window.mouseX || window.innerWidth/2, y: window.mouseY || window.innerHeight/2})")
        start_x, start_y = current.get('x', 960), current.get('y', 540)
    except Exception:
        start_x, start_y = 960, 540

    # Generate bezier path
    path = bezier_curve((start_x, start_y), (target_x, target_y))

    # Calculate timing
    distance = math.sqrt((target_x - start_x)**2 + (target_y - start_y)**2)
    if duration is None:
        # Human mouse speed: roughly 500-1500 pixels per second
        speed = random.uniform(500, 1200)
        duration = distance / speed

    step_duration = duration / len(path)

    # Move along path with slight timing variance
    for point in path:
        page.mouse.move(point[0], point[1])
        time.sleep(step_duration * random.uniform(0.8, 1.2))


def human_click(page, x: float, y: float):
    """
    Perform a human-like click at coordinates.
    Includes pre-click hover, slight position variance, and natural timing.
    """
    # Add slight position variance (humans don't click exact center)
    variance = random.gauss(0, 3)
    click_x = x + variance
    click_y = y + random.gauss(0, 3)

    # Move to position
    human_mouse_move(page, click_x, click_y)

    # Brief hover before click
    human_sleep(0.1, 0.5)

    # Click with random duration
    page.mouse.down()
    human_sleep(0.08, 0.3)
    page.mouse.up()


def human_press_and_hold(page, x: float, y: float, hold_duration: float = 5.0):
    """
    Perform a human-like press and hold action.

    Includes:
    - Natural movement to target
    - Micro-movements during hold (humans can't hold perfectly still)
    - Variable hold duration

    Args:
        page: Playwright page object
        x: Target X coordinate
        y: Target Y coordinate
        hold_duration: Base hold duration in seconds
    """
    # Move to target with natural curve
    human_mouse_move(page, x, y)

    # Brief pause before pressing
    human_sleep(0.15, 0.4)

    # Press down
    page.mouse.down()

    # Hold with micro-movements (humans have slight tremor)
    actual_duration = hold_duration * random.uniform(0.95, 1.15)
    start_time = time.time()

    while time.time() - start_time < actual_duration:
        # Small micro-movement
        micro_x = x + random.gauss(0, 1.5)
        micro_y = y + random.gauss(0, 1.5)
        page.mouse.move(micro_x, micro_y)
        human_sleep(0.1, 0.5)

    # Release
    page.mouse.up()

    # Brief pause after release
    human_sleep(0.2, 0.3)


def human_type(page, selector: str, text: str, clear_first: bool = True):
    """
    Type text with human-like variable rhythm.

    Args:
        page: Playwright page object
        selector: Input field selector
        text: Text to type
        clear_first: Whether to clear existing text first
    """
    element = page.locator(selector).first
    element.click()
    human_sleep(0.1, 0.3)

    if clear_first:
        element.fill('')
        human_sleep(0.1, 0.2)

    # Type character by character with variable delays
    for i, char in enumerate(text):
        delay_ms = random_typing_delay()

        # Occasional longer pauses (like thinking/correcting)
        if random.random() < 0.05:
            delay_ms += random.randint(100, 300)

        # Slightly faster for repeated characters
        if i > 0 and char == text[i-1]:
            delay_ms = int(delay_ms * 0.7)

        page.keyboard.type(char, delay=delay_ms)


def get_random_viewport() -> dict:
    """
    Return a randomized but realistic viewport size.
    Based on common screen resolutions with slight variance.
    """
    # Common resolutions with weights
    resolutions = [
        (1920, 1080, 0.35),  # Full HD - most common
        (1366, 768, 0.20),   # Laptop HD
        (1536, 864, 0.15),   # Laptop scaled
        (1440, 900, 0.10),   # MacBook
        (1680, 1050, 0.10),  # WSXGA+
        (2560, 1440, 0.10),  # QHD
    ]

    # Weighted random selection
    total = sum(w for _, _, w in resolutions)
    r = random.uniform(0, total)
    cumulative = 0

    for width, height, weight in resolutions:
        cumulative += weight
        if r <= cumulative:
            # Add slight variance (browser chrome, etc.)
            width += random.randint(-20, 0)
            height += random.randint(-50, -20)
            return {"width": width, "height": height}

    return {"width": 1920, "height": 1080}


def get_random_user_agent() -> str:
    """
    Return a current, realistic Chrome user agent.
    Rotates between recent Chrome versions on common platforms.
    """
    # Recent Chrome versions (update periodically)
    chrome_versions = ["130.0.0.0", "131.0.0.0", "129.0.0.0"]

    platforms = [
        ("Windows NT 10.0; Win64; x64", 0.65),
        ("Macintosh; Intel Mac OS X 10_15_7", 0.25),
        ("X11; Linux x86_64", 0.10),
    ]

    chrome_version = random.choice(chrome_versions)

    # Weighted platform selection
    total = sum(w for _, w in platforms)
    r = random.uniform(0, total)
    cumulative = 0

    for platform, weight in platforms:
        cumulative += weight
        if r <= cumulative:
            return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"

    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"


def random_scroll(page, direction: str = "down", amount: int = None):
    """
    Perform a human-like scroll action.

    Args:
        page: Playwright page object
        direction: "up" or "down"
        amount: Scroll amount in pixels (randomized if None)
    """
    if amount is None:
        amount = random.randint(100, 400)

    if direction == "up":
        amount = -amount

    # Scroll in small increments for more natural appearance
    steps = random.randint(3, 8)
    step_amount = amount / steps

    for _ in range(steps):
        page.mouse.wheel(0, step_amount)
        human_sleep(0.03, 0.5)
