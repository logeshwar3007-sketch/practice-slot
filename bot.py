"""
Slot Booking Bot for learner.saveetha.in
==========================================
Logs in with your credentials, then repeatedly checks the booking page.
Reads slots_wanted.json (created via the front page: run app.py first,
add your slots at http://127.0.0.1:5000, then run this).

For EACH slot in your watch list, it keeps checking until that slot is
open, books it, marks it "booked" in slots_wanted.json, and moves on to
still watching the rest -- so you can grab several slots in one run.

BEFORE YOU RUN THIS
--------------------
1. pip install -r requirements.txt
2. Fill in config.json with your real username/password and the direct
   URL of the booking page (see README.md).
3. You MUST edit the SELECTORS below to match the real page -- I can't
   see learner.saveetha.in myself since it's behind your login. See
   "HOW TO FIND THE REAL SELECTORS" at the bottom of this file, or the
   README, for how to get these from your browser in a couple of minutes.
4. Automate only your own account, and check your college's IT/portal
   policy on automated access before leaving this running unattended.
"""

import json
import re
import time
import sys
import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException
)
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("slot_bot")

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
WANTED_PATH = BASE / "slots_wanted.json"


# ----------------------------------------------------------------------
# SELECTORS -- YOU MUST EDIT THESE to match learner.saveetha.in's real HTML.
# Right-click the relevant element in Chrome -> Inspect -> copy its id/class.
# ----------------------------------------------------------------------
SELECTORS = {
    "username_field": (By.ID, "id_username"),
    "password_field": (By.ID, "id_password"),
    "login_button":   (By.XPATH, "//button[contains(text(),'Sign in')]"),

    "slot_items":       (By.XPATH, "//div[contains(@class,'card-body')][.//form[.//input[@name='action' and @value='book']]]"),  # confirmed
    "purpose_field":    (By.CSS_SELECTOR, "input[name='purpose']"),  # confirmed -- searched *within* each slot card
    "slot_book_button": (By.XPATH, ".//button[contains(text(),'Book Now')]"),   # confirmed
    "result_message":   (By.CSS_SELECTOR, ".alert"),  # Django's message banner after the form submits -- best guess, verify on first run
}


# ----------------------------------------------------------------------
# CONFIG / WATCH LIST HELPERS
# ----------------------------------------------------------------------
def load_config():
    if not CONFIG_PATH.exists():
        template = {
            "portal_url": "https://learner.saveetha.in/",
            "username": "YOUR_USERNAME_HERE",
            "password": "YOUR_PASSWORD_HERE",
            "booking_page_url": "https://learner.saveetha.in/academicevents/event-booking/",
            "poll_interval_seconds": 5
        }
        CONFIG_PATH.write_text(json.dumps(template, indent=2))
        log.warning(f"Created a blank config at {CONFIG_PATH}. Fill it in, then run again.")
        sys.exit(0)
    return json.loads(CONFIG_PATH.read_text())


def load_wanted():
    if not WANTED_PATH.exists():
        log.error("No slots_wanted.json found. Run 'python app.py', open "
                   "http://127.0.0.1:5000 and add at least one slot first.")
        sys.exit(1)
    items = json.loads(WANTED_PATH.read_text())
    if not items:
        log.error("Your watch list is empty. Add slots at http://127.0.0.1:5000 first.")
        sys.exit(1)
    return items


def save_wanted(items):
    WANTED_PATH.write_text(json.dumps(items, indent=2))


TIME_PATTERN = re.compile(r'(\d{1,2})(?:[:.](\d{2}))?\s*([ap])\.?\s*m\.?', re.IGNORECASE)


def normalize(text):
    """Lowercases, rewrites any time like '1 p.m.', '1.00 PM', '1:59 p.m.'
    into one consistent form (e.g. '1:00pm'), then strips all whitespace.
    This makes '1 p.m. - 1:59 p.m.' and '1.00 PM - 1.59 PM' compare equal."""
    text = text.lower()

    def canon(m):
        hour = int(m.group(1))
        minute = m.group(2) or "00"
        ampm = m.group(3)
        return f"{hour}:{minute}{ampm}m"

    text = TIME_PATTERN.sub(canon, text)
    text = re.sub(r"\s+", "", text)
    return text


def matches(slot_text, wanted_item):
    slot_norm = normalize(slot_text)
    for key in ("hall", "date", "timing", "type"):
        val = (wanted_item.get(key) or "").strip()
        if val and normalize(val) not in slot_norm:
            return False
    return True


# ----------------------------------------------------------------------
# BOT LOGIC
# ----------------------------------------------------------------------
def build_driver():
    options = webdriver.ChromeOptions()
    # Leave this commented out the first few runs so you can WATCH it work.
    # options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def login(driver, wait, cfg):
    log.info("Opening login page...")
    driver.get(cfg["portal_url"])

    user_field = wait.until(EC.presence_of_element_located(SELECTORS["username_field"]))
    pass_field = driver.find_element(*SELECTORS["password_field"])

    user_field.clear()
    user_field.send_keys(cfg["username"])
    pass_field.clear()
    pass_field.send_keys(cfg["password"])

    driver.find_element(*SELECTORS["login_button"]).click()
    log.info("Submitted login. Waiting for dashboard to load...")
    time.sleep(3)


def try_book_one(driver, wait, slot_element, purpose_text):
    """Fills Purpose and clicks Book Now inside this one slot card.
    Book Now submits a real HTML form (full page reload), so after
    clicking we read whatever confirmation/error banner the portal shows.
    Returns (clicked: bool, message: str)."""

    # Fill the Purpose field, scoped to THIS slot card.
    try:
        purpose_field = slot_element.find_element(*SELECTORS["purpose_field"])
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", purpose_field)
        time.sleep(0.3)
        purpose_field.clear()
        purpose_field.send_keys(purpose_text)
    except NoSuchElementException:
        log.warning("Purpose field not found in this slot card -- continuing without it.")

    # Click Book Now -- this is a real form submit, page will reload.
    try:
        book_btn = slot_element.find_element(*SELECTORS["slot_book_button"])
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", book_btn)
        time.sleep(0.3)
        try:
            book_btn.click()
        except ElementClickInterceptedException:
            log.info("Normal click was blocked by an overlapping element -- retrying with a JS click.")
            driver.execute_script("arguments[0].click();", book_btn)
    except NoSuchElementException as e:
        log.warning(f"Could not find Book Now button: {e}")
        return False, f"Could not find Book Now button: {e}"

    time.sleep(2)  # let the page reload after the POST

    message = "Submitted -- no confirmation banner detected, please verify manually."
    try:
        alert_el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(SELECTORS["result_message"])
        )
        message = alert_el.text.strip()
    except TimeoutException:
        pass

    return True, message


def check_and_book_all(driver, wait, cfg, wanted):
    """Keeps fetching the booking page and booking any matching open slot,
    one after another (re-fetching between each, since Book Now reloads
    the page), until either every watched item is booked/failed or a full
    pass over the page finds no more matches -- so several ready slots
    get grabbed back-to-back instead of one per polling cycle."""

    while True:
        still_waiting = [w for w in wanted if w["status"] == "waiting"]
        if not still_waiting:
            log.info("Nothing left in 'waiting' status.")
            return

        driver.get(cfg["booking_page_url"])
        try:
            slots = wait.until(EC.presence_of_all_elements_located(SELECTORS["slot_items"]))
        except TimeoutException:
            log.info("No slots listed on page right now. Will retry next cycle.")
            return

        log.info(f"Found {len(slots)} slot card(s) on the page. Watching {len(still_waiting)} item(s).")

        page_reloaded = False
        any_match = False
        for slot in slots:
            text = slot.text
            matched_item = None
            for item in still_waiting:
                if matches(text, item):
                    matched_item = item
                    break
            if not matched_item:
                continue

            any_match = True
            log.info(f"Match found for {matched_item} -- attempting to book: '{text.strip()[:60]}'")
            try:
                clicked, message = try_book_one(driver, wait, slot, matched_item.get("purpose", ""))
            except Exception as e:
                clicked, message = False, f"Unexpected error: {e}"

            matched_item["message"] = message

            if clicked:
                lowered = message.lower()
                if any(w in lowered for w in ("success", "booked", "confirmed")):
                    matched_item["status"] = "booked"
                elif any(w in lowered for w in ("full", "closed", "already", "error", "fail")):
                    matched_item["status"] = "failed"
                else:
                    matched_item["status"] = "booked"  # submitted, unclear banner -- verify manually
                save_wanted(wanted)
                log.info(f"Result for {matched_item['hall']} / {matched_item.get('date','')} / {matched_item['timing']}: {message}")
                page_reloaded = True
                break  # the form submit really reloaded the page -- rest of `slots` is now stale, go refetch
            else:
                # nothing was actually submitted (e.g. couldn't find the
                # button) -- page didn't reload, leave status as "waiting"
                # so the next normal poll cycle retries it, and keep
                # scanning the rest of the still-valid `slots` list now.
                save_wanted(wanted)
                log.warning(f"Could not book {matched_item['hall']} / {matched_item.get('date','')} / {matched_item['timing']}: {message}")
                continue

        if page_reloaded:
            time.sleep(1)  # brief pause between back-to-back bookings, then loop to fetch a fresh page
            continue

        if not any_match:
            log.info("No match this cycle. Here's what's actually on the page vs. what you're watching for:")
            for i, slot in enumerate(slots):
                log.info(f"  Card {i+1} text: {slot.text.strip()[:150]!r}")
            for item in still_waiting:
                log.info(f"  Watching for: hall={item.get('hall')!r} date={item.get('date')!r} timing={item.get('timing')!r} type={item.get('type')!r}")

        return  # no more bookable matches this pass -- wait for next poll cycle


def main():
    cfg = load_config()
    if "YOUR_USERNAME_HERE" in cfg.get("username", ""):
        log.error(f"Please edit {CONFIG_PATH} with your real credentials and booking page URL first.")
        sys.exit(1)

    wanted = load_wanted()

    driver = build_driver()
    wait = WebDriverWait(driver, 15)

    try:
        login(driver, wait, cfg)

        interval = cfg.get("poll_interval_seconds", 20)
        log.info(f"Watching {len(wanted)} slot(s). Checking every {interval}s. Press Ctrl+C to stop.")

        while True:
            wanted = json.loads(WANTED_PATH.read_text())  # pick up any edits made via the front page
            if all(w["status"] == "booked" for w in wanted):
                log.info("All watched slots are booked. Done!")
                break

            try:
                check_and_book_all(driver, wait, cfg, wanted)
            except Exception as e:
                log.error(f"Error during check: {e}. Will retry next cycle.")

            time.sleep(interval)

    except KeyboardInterrupt:
        log.info("Stopped by user.")
    finally:
        input("Press Enter to close the browser window...")
        driver.quit()


if __name__ == "__main__":
    main()


# ----------------------------------------------------------------------
# HOW TO FIND THE REAL SELECTORS (do this once, takes a few minutes)
# ----------------------------------------------------------------------
# 1. Open learner.saveetha.in in Chrome, log in manually.
# 2. Right-click the username field -> Inspect. Note its id or name
#    attribute -> put into SELECTORS["username_field"] above.
#    Repeat for the password field and login button.
# 3. Go to the slot booking page. Copy its exact URL into config.json's
#    "booking_page_url".
# 4. Right-click one slot entry -> Inspect. Find the repeating parent
#    element (a div/li that repeats once per slot) and its class ->
#    SELECTORS["slot_items"].
# 5. Inside that element, find the "Book" button's class/id ->
#    SELECTORS["slot_book_button"].
# 6. If a confirmation popup appears after clicking Book, inspect its
#    confirm button too -> SELECTORS["confirm_button"].
# 7. Save, then run with the browser visible first to confirm it clicks
#    the right things before trusting it unattended.
