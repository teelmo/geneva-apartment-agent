# Geneva apartment watch 🏠

**[View the live dashboard](https://teelmo.github.io/geneva-apartment-agent/)**

An automated agent that checks Geneva rental portals **every morning**, filters for
what your family needs, remembers what it has already shown you, and publishes a
dashboard of only the *new* matches — with **postcode 1205 ranked first**.

Sources: **Anibis, Homegate, ImmoScout24, Flatfox** (the richest ones for
*reprise de bail* / lease takeovers).

---

## The one thing to know about Swiss listings

"Pièces" counts the **living room**, so **3 bedrooms ≈ 4–4.5 pièces**. The filter
therefore targets **≥ 4 pièces**, not 3. This is set in `config.py` (`MIN_PIECES`).

---

## What each run does

1. Loads each portal's Geneva rentals search page (headless Chromium).
2. Extracts every listing + its price / pièces / m² / postcode.
3. Applies your filters (see `config.py`):
   - **≥ 4 pièces** (≈ 3 bedrooms) — hard filter
   - **70–135 m²**, ideal 90 — hard filter
   - **≤ CHF 3000** comfortable, up to **CHF 3600** shown as "stretch / good catch?", above that dropped
4. Ranks: **1205 first**, then central Geneva (1201–1209), then rest of canton.
   Lift / balcony / in-unit laundry / parking are **ranking bonuses**, not filters.
5. Compares against `seen.json` so you only get **new** listings.
6. Writes `public/index.html` (dashboard) + `public/listings.json`.
7. Optionally emails you the new ones (if SMTP secrets are set).

Change anything in **`config.py`** — you never need to edit the other files.

---

## Setup — GitHub Actions (recommended, runs in the cloud daily)

1. Create a new **private** GitHub repo and push these files to it.
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. In **Settings → Actions → General → Workflow permissions**, choose
   **Read and write permissions** (so it can save `seen.json`).
4. That's it. It runs daily at **06:30 Geneva time** (`.github/workflows/apartments.yml`).
   You can also trigger it any time from the **Actions** tab → *Run workflow*.
5. Your dashboard will be at `https://<your-username>.github.io/<repo>/`.
   (Optionally add a repo **Variable** `DASHBOARD_URL` with that address so it appears in emails.)

### Enable email digests (optional)
Add these as **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Example |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `you@gmail.com` |
| `SMTP_PASS` | *(an app password, not your login password)* |
| `SMTP_TO` | `you@gmail.com, partner@gmail.com` |

With Gmail, create an **App Password** (Google account → Security → App passwords).
Email is only sent when there's something new — no empty inboxes.

---

## Setup — run locally on your Mac instead

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
python3 main.py            # writes public/index.html
open public/index.html
```

To run it automatically every morning with **launchd**, create
`~/Library/LaunchAgents/ch.geneva.apartments.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>ch.geneva.apartments</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/full/path/to/apartment-agent/main.py</string>
  </array>
  <key>WorkingDirectory</key><string>/full/path/to/apartment-agent</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/apartments.log</string>
  <key>StandardErrorPath</key><string>/tmp/apartments.err</string>
</dict></plist>
```

Then: `launchctl load ~/Library/LaunchAgents/ch.geneva.apartments.plist`

---

## Testing without hitting the sites

```bash
python3 main.py --dry     # uses sample.json, exercises filtering + dashboard
```

---

## Source status — verified live 2026-07-22

All four portals were checked against their live Geneva searches and repaired:

| Source | Status | Notes |
|---|---|---|
| **Flatfox** | ✅ rewritten & verified | The public API ignores location/ordering filters, so the code now uses the site's real two-step flow: `/api/v1/pin/` (honours the Geneva bounding box) → batch `/api/v1/public-listing/?pk=…`. Correct field names, category + canton filtering, attributes → features. |
| **Homegate** | ✅ verified | 493 Geneva flats; detail URLs `/rent/<id>` match. |
| **ImmoScout24** | ✅ regex fixed | Now on the Swiss Marketplace Group platform using Homegate's `/rent/<id>` scheme; the old `/d/…` pattern was dead. |
| **Anibis** | ✅ verified | 697 listings; `/fr/(vi\|s)/…` detail URLs match; lots of *reprise de bail*. |

Also hardened along the way:
- **Swiss price parsing** now handles every real format: `CHF 1,970.–`, `2'950`, `1 680.- par mois`, `Fr. 3200.-`. (The original only parsed the separator-less sample data.)
- **Cross-portal de-duplication**: Homegate and ImmoScout24 list the *same* flat under identical `/rent/<id>` ids, so they're collapsed into one card.

If a source ever prints `0 raw listings` after a future site redesign, open `sources.py`
and adjust that source's `search` URL or `detail_re`. Each source is isolated, so one
failing source never breaks the others.

## Your confirmed preferences (baked in)

- **Budget: CHF 3,500 preference, up to CHF 4,000 shown.** 3,500 is a *soft* ceiling, not
  a hard cut — flats CHF 3,500–4,000 still appear, flagged "stretch" and ranked lower.
  Only above CHF 4,000 are dropped. Tune `BUDGET_CHF` / `STRETCH_MAX_CHF` in `config.py`.
- **Furnished & unfurnished both shown** — no furnishing filter.
- **Move-in flexible / ASAP** — no availability-date cutoff; good matches surface as they appear.
- **Delivery: email digest** — set the SMTP secrets below. The dashboard + `listings.json` are always written too.

## Hiding false positives

Portals occasionally return a mis-parsed or irrelevant listing. On the dashboard, hover any
card and click the **✕** (top-right) to hide it. Use **Show hidden (N)** to review what you
hid, **↩ restore** on any card to bring it back, or **Restore all** to clear them.

Hidden listings are remembered **in your browser** (localStorage) and stay hidden across the
daily rebuilds — so a false positive you dismiss won't keep reappearing each morning. Note
this is per-device (it doesn't sync between your phone and laptop, and isn't reflected in the
email digest).

## Facebook groups (quick links, not scraped)

The dashboard and every email include one-click links to your Geneva Facebook groups so you
can skim them by hand. Edit the list in `config.py` (`FACEBOOK_GROUPS`). See below for why
they're not automated.

## Facebook groups — deliberately *not* automated

You asked about pointing the agent at these groups using your logged-in Chrome:
`apartments.geneva`, `327007357342406`, `genevealouer`, `1889932788416549`, `393414324133485`.

I've left Facebook **out of the automated agent on purpose.** Facebook's Terms
prohibit automated collection of content, the groups sit behind a login, and a
GitHub-Actions cron can't (and shouldn't) drive your authenticated session. Building
scraping around your login would put your personal account at risk of restriction.

The compliant, genuinely-effective supplement:
- Turn on **in-app notifications** for each group (open group → 🔔 → *All posts*), and/or
  join Facebook's **email notifications** so new posts land in your inbox.
- Set up native **saved-search email alerts** on Homegate / ImmoScout / Flatfox / Anibis
  (5 min each) as a second net.
- Skim the FB groups manually — the agent already handles the portal firehose, so FB
  is just the occasional extra.

- **Be a good citizen.** It runs once a day at low volume — please keep it that way
  (don't crank `MAX_PAGES_PER_SOURCE` high or schedule it hourly).

---

## Files

| File | Purpose |
|---|---|
| `config.py` | **All your preferences.** Edit this. |
| `main.py` | Orchestrates a single run. |
| `sources.py` | The four portal scrapers. |
| `model.py` | Listing model, text parsing, filtering, scoring. |
| `store.py` | Remembers seen listings (`seen.json`). |
| `report.py` | Builds the HTML dashboard. |
| `notify.py` | Optional email digest. |
| `.github/workflows/apartments.yml` | Daily schedule + Pages deploy. |
