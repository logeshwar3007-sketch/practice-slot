# Slot Booking Bot — learner.saveetha.in

Watches for one or more slots (hall + timing + type) to open on the portal
and books them automatically, using your own login.

**Important:** I don't have access to learner.saveetha.in myself (it's
behind your login), so the bot ships with placeholder selectors that
**you must fill in once** using your browser's Inspect tool. Takes about
5–10 minutes. Full instructions are in Step 5 below and at the bottom of
`bot.py`.

Also check your college's IT/portal usage policy before leaving this
running unattended — some institutions restrict automated/bot access.

## Setup (one time)

**1. Install Python 3.9+** from python.org if you don't have it
(check "Add to PATH" on Windows). Verify: `python --version`

**2. Open a terminal in this folder and install dependencies:**
```
pip install -r requirements.txt
```
(On Mac/Linux, if that errors, try: `pip install -r requirements.txt --break-system-packages`)

**3. Run the bot once to generate the config file:**
```
python bot.py
```
This creates `config.json` and stops — that's expected on first run.

**4. Edit `config.json`** with a text editor:
- `username` / `password` — your real portal login
- `booking_page_url` — the exact URL of the slot booking page (get this
  after logging in manually and navigating there)
- `poll_interval_seconds` — how often to check (20–30s is a reasonable default)

**5. Find the real page selectors (one-time, ~5-10 min):**
- Open learner.saveetha.in in Chrome, log in manually.
- Right-click the username box → **Inspect**. Note the `id` or `name`
  shown in the highlighted HTML.
- Do the same for the password box and the login button.
- Open `bot.py` in a text editor, find the `SELECTORS = { ... }` block
  near the top, and replace the placeholder values with what you found.
- Go to the actual booking page. Right-click one slot listing → Inspect.
  Find the repeating element (usually a `<div>` or `<li>` that repeats
  once per slot) and its class → update `slot_items`.
- Inside that same element, find the "Book" button and update `slot_book_button`.
- If clicking Book shows a confirm popup, inspect that button too → `confirm_button`.

If you're not comfortable doing this yourself, copy the HTML of the
login form and one slot entry (right-click → Inspect → right-click the
highlighted line → Copy → Copy outerHTML) and send it to me — I'll write
the exact selectors for you.

## Running it

**Step A — Tell it which slots you want:**
```
python app.py
```
Open **http://127.0.0.1:5000** in your browser. Add each slot you want
(hall, timing, type, and the purpose text you'd type into "Purpose for
attending") — add as many as you like, it'll try to grab all of them.
The bot types the purpose in and clicks "View More" first if the portal
needs that to reveal the Purpose box, so you don't have to type it yourself.

**Step B — Start the bot:**
In a separate terminal (leave app.py's terminal running too):
```
python bot.py
```
It logs in, then checks the booking page on a loop. The moment a slot
matching one of your entries opens, it books it, marks that entry
"booked" on the front page, and keeps watching the rest of your list
until they're all booked — or until you press Ctrl+C.

**First run:** keep the browser window visible (don't enable headless
mode — it's already commented out) so you can confirm it's clicking the
right things before trusting it unattended.

## Files
- `app.py` — front page where you enter what slots you want
- `templates/index.html` — the form itself
- `bot.py` — the actual login + polling + booking logic
- `config.json` — your credentials + portal URLs (created on first run)
- `slots_wanted.json` — your watch list (created when you add a slot via the front page)
- `requirements.txt` — Python packages needed
