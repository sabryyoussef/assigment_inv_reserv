"""
Playwright script: run 50-user and 100-user Locust tests and capture
screenshots at each meaningful stage into screenshots/.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

LOCUST_URL = "http://127.0.0.1:8089"
SCREENSHOTS = Path(__file__).parent / "screenshots"
SCREENSHOTS.mkdir(exist_ok=True)


def save(page, name: str):
    path = SCREENSHOTS / name
    page.screenshot(path=str(path), full_page=True)
    print(f"  saved -> {path.name}")


def wait_for_users(page, expected: int, timeout: int = 60):
    """Poll until the Users counter in the header reaches expected value."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            text = page.locator("text=Users").locator("..").locator("nth=0").inner_text(timeout=2000)
        except Exception:
            text = ""
        # also check via all matching elements
        users_els = page.get_by_text(str(expected)).all()
        header_users = page.locator(".stats-header").all_inner_texts() if page.locator(".stats-header").count() else []
        # simpler: read the badge next to "Users" label
        try:
            badge = page.locator("[class*='stats'] >> text=Users").locator("xpath=following-sibling::*[1]").inner_text(timeout=1000)
            if badge.strip() == str(expected):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False  # timed out, continue anyway


def ensure_new_form(page):
    """Make sure we're on the new-test form, handling any existing test state."""
    page.goto(LOCUST_URL, wait_until="networkidle")
    page.wait_for_timeout(1500)

    # If a test is running, stop it first
    stop_btn = page.locator('button:has-text("Stop")')
    if stop_btn.count() and stop_btn.is_visible():
        stop_btn.click()
        page.wait_for_timeout(2000)

    # If reset is available, reset
    reset_btn = page.locator('button:has-text("Reset")')
    if reset_btn.count() and reset_btn.is_visible():
        reset_btn.click()
        page.wait_for_timeout(1500)

    # Click "New" to show the new-test form if needed
    new_btn = page.locator('button:has-text("New")')
    if new_btn.count() and new_btn.is_visible():
        new_btn.click()
        page.wait_for_timeout(1000)


def run_test(page, users: int, spawn_rate: int, label: str):
    """Configure and run one Locust scenario, capture screenshots throughout."""
    print(f"\n=== {label}: {users} users @ {spawn_rate}/s ===")

    # ── 1. Home / configuration form ──────────────────────────────────────
    ensure_new_form(page)
    save(page, f"{label}_01_home.png")

    # Fill users and spawn rate using visible label text
    page.get_by_label("Number of users (peak concurrency)").fill(str(users))
    page.get_by_label("Ramp up (users started/second)").fill(str(spawn_rate))

    save(page, f"{label}_02_configured.png")

    # ── 2. Start test ──────────────────────────────────────────────────────
    page.locator('button:has-text("Start")').last.click()
    page.wait_for_timeout(2000)
    save(page, f"{label}_03_starting.png")

    # Wait for ramp-up to finish (all users spawned)
    print(f"  Ramping up to {users} users...")
    time.sleep(users / spawn_rate + 3)  # rough ramp time + buffer
    save(page, f"{label}_04_ramped_up.png")

    # Mid-test: switch to Charts tab
    page.locator('role=tab[name="Charts"]').click()
    page.wait_for_timeout(2000)
    save(page, f"{label}_05_charts_midtest.png")

    # Switch to Failures tab
    page.locator('role=tab[name="Failures"]').click()
    page.wait_for_timeout(1500)
    save(page, f"{label}_06_failures_midtest.png")

    # Back to Statistics for final read
    page.locator('role=tab[name="Statistics"]').click()
    page.wait_for_timeout(1500)

    # Wait for ~60 s total run (already spent ramp + some time above)
    remaining = max(0, 60 - (users / spawn_rate) - 10)
    print(f"  Waiting {int(remaining)}s for test to complete...")
    time.sleep(remaining)

    # ── 3. Final statistics ────────────────────────────────────────────────
    page.locator('role=tab[name="Statistics"]').click()
    page.wait_for_timeout(2000)
    save(page, f"{label}_07_statistics_final.png")

    # Final charts
    page.locator('role=tab[name="Charts"]').click()
    page.wait_for_timeout(2000)
    save(page, f"{label}_08_charts_final.png")

    # Final failures
    page.locator('role=tab[name="Failures"]').click()
    page.wait_for_timeout(1500)
    save(page, f"{label}_09_failures_final.png")

    # ── 4. Stop and reset ─────────────────────────────────────────────────
    stop_btn = page.locator('button:has-text("Stop")')
    if stop_btn.is_visible():
        stop_btn.click()
        page.wait_for_timeout(2000)

    save(page, f"{label}_10_stopped.png")

    page.locator('button:has-text("Reset")').click()
    page.wait_for_timeout(2000)

    # Click "New" to return to form
    new_btn = page.locator('button:has-text("New")')
    if new_btn.is_visible():
        new_btn.click()
        page.wait_for_timeout(1000)

    print(f"  Done - 10 screenshots saved for {label}")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # ── Scenario A: 50 concurrent users ───────────────────────────────
        run_test(page, users=50, spawn_rate=10, label="50users")

        # ── Scenario B: 100 concurrent users ──────────────────────────────
        run_test(page, users=100, spawn_rate=20, label="100users")

        browser.close()

    print(f"\nAll screenshots saved to: {SCREENSHOTS}")
    for f in sorted(SCREENSHOTS.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
