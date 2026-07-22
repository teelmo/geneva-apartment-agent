# config.py — all your search preferences live here.
# Change anything in this file; no need to touch the rest of the code.

# --- Location -----------------------------------------------------------------
# Your preferred postcode (kindergarten application is tied to it).
TARGET_POSTCODE = '1205'

# Other postcodes we'll still show, but rank below 1205.
# These are Geneva-city postcodes (1201–1209) plus a couple of very close ones.
ACCEPTABLE_POSTCODES = [
  '1201', '1202', '1203', '1204', '1206', '1207', '1208', '1209',
]

# Anything else in the canton (12xx, 122x, 123x…) is shown last, clearly flagged.
CANTON_PREFIXES = ['12']

# --- Size of home -------------------------------------------------------------
# NOTE ON SWISS "PIÈCES": a listing's "pièces" count includes the living room.
# So 3 bedrooms ≈ 4 to 4.5 pièces. We filter on pièces, not bedrooms.
MIN_PIECES = 4.0          # ≈ 3 bedrooms / sleeping rooms (baby + you + guests)
IDEAL_SIZE_M2 = 90        # your sweet spot
MIN_SIZE_M2 = 70          # accept a bit smaller if otherwise great
MAX_SIZE_M2 = 135         # accept a bit bigger too

# --- Budget -------------------------------------------------------------------
# Rent here means the "loyer" figure the listing shows. Where a listing clearly
# separates charges, we try to use rent-incl-charges; otherwise we use what's shown.
BUDGET_CHF = 3500         # comfortable ceiling (a preference, NOT a hard cut-off)
STRETCH_MAX_CHF = 4000    # flats CHF 3500–4000 still shown, flagged "stretch / good catch?"
# Only listings above STRETCH_MAX_CHF are dropped, so CHF 3500 stays a soft
# preference with real headroom above it (stretch flats are just ranked lower).

# --- Feature bonuses (ranking only, NOT hard filters) -------------------------
# Detected from listing text. Each present feature nudges a listing up the list.
FEATURE_KEYWORDS = {
  'elevator':  ['ascenseur', 'lift', 'aufzug'],
  'ground_floor': ['rez-de-chaussée', 'rez ', 'rdc', 'erdgeschoss', 'ground floor'],
  'outdoor':   ['balcon', 'terrasse', 'jardin', 'loggia', 'balcony', 'terrace', 'garden'],
  'laundry':   ['lave-linge', 'machine à laver', 'laver', 'washing machine', 'waschmaschine', 'buanderie'],
  'parking':   ['parking', 'place de parc', 'garage', 'parc ', 'stationnement'],
}

# --- Lease-takeover preference ------------------------------------------------
# Lease takeovers ("reprise de bail") are common in Geneva and often the fastest
# path. We detect and highlight them, but do not require them.
TAKEOVER_KEYWORDS = ['reprise de bail', 'reprise du bail', 'lease takeover', 'à remettre', 'remise de bail']

# --- Scheduling / behaviour ---------------------------------------------------
MAX_PAGES_PER_SOURCE = 3   # how deep to paginate each site per run (keep modest)
REQUEST_TIMEOUT = 30       # seconds

# --- Delivery -----------------------------------------------------------------
# The HTML dashboard is always written. Email is optional: it only sends if the
# SMTP_* environment variables (GitHub Secrets) are set. See README.
DASHBOARD_TITLE = 'Geneva apartment watch — 1205 first'

# --- Facebook groups (manual check — NOT scraped) -----------------------------
# We don't automate Facebook (their terms forbid it and it's behind a login), but
# we surface quick links on the dashboard and in the email so you can skim them by
# hand in one click. Add/remove groups freely — {name: url}.
FACEBOOK_GROUPS = {
  'Apartments Geneva': 'https://www.facebook.com/groups/apartments.geneva',
  'Genève à louer': 'https://www.facebook.com/groups/genevealouer',
  'Group 327007357342406': 'https://www.facebook.com/groups/327007357342406',
  'Group 1889932788416549': 'https://www.facebook.com/groups/1889932788416549',
  'Group 393414324133485': 'https://www.facebook.com/groups/393414324133485',
}
