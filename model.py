# model.py — the Listing data structure, parsing helpers, filtering and ranking.
import re
import hashlib
from dataclasses import dataclass, field, asdict

import config


@dataclass
class Listing:
  source: str
  url: str
  title: str = ''
  raw_text: str = ''
  price: float | None = None
  pieces: float | None = None
  size_m2: float | None = None
  postcode: str | None = None
  address: str = ''
  available: str = ''
  # derived / annotated at filter time:
  features: list = field(default_factory=list)
  is_takeover: bool = False
  area_rank: int = 99          # 0 = target postcode, 1 = acceptable, 2 = canton, 9 = unknown
  stretch_budget: bool = False
  score: float = 0.0

  @property
  def uid(self) -> str:
    """Stable id for dedup: prefer the URL, fall back to a text hash.
    Homegate and ImmoScout24 share the Swiss Marketplace Group platform and list
    the *same* flat under identical /rent/<id> ids, so we key those on the id to
    collapse cross-portal duplicates into one card."""
    m = re.search(r'/rent/(\d{5,})', self.url)
    if m and ('homegate' in self.url or 'immoscout' in self.url):
      basis = 'smg:' + m.group(1)
    else:
      basis = self.url.strip() or (self.title + self.raw_text)[:200]
    return hashlib.sha1(basis.encode('utf-8')).hexdigest()[:16]

  def to_dict(self) -> dict:
    d = asdict(self)
    d['uid'] = self.uid
    return d


# --- text parsing helpers -----------------------------------------------------
# These regexes are deliberately forgiving: even if a site changes its markup,
# as long as the human-readable card text is captured in raw_text we can recover
# price / pièces / size / postcode.

# Swiss rents come in many forms: "CHF 2'950", "CHF 1,970.–", "1 680.- par
# mois", "Fr. 3200.-". Thousands separators may be apostrophe, comma or space,
# and the amount may sit before *or* after the currency / "par mois" token.
_PRICE_AMOUNT = r"[0-9][0-9'’.,\s]{1,8}"
_PRICE_RE = re.compile(r"(?:CHF|Fr\.?)\s*(" + _PRICE_AMOUNT + r")", re.IGNORECASE)
_PRICE_RE_ALT = re.compile(r"(" + _PRICE_AMOUNT + r")\.?\s*[-–]?\s*"
                           r"(?:/\s*mois|par\s+mois|CHF|Fr\b)", re.IGNORECASE)
_PIECES_RE = re.compile(r"([\d]+(?:[.,]5)?)\s*(?:pi[eè]ces?|rooms?|Zimmer|zi\.)", re.IGNORECASE)
# immobilier.ch renders the m² sign as separate text nodes ("105 m 2"), so allow
# an optional space between the "m" and the "2".
_SIZE_RE = re.compile(r"([\d]{2,3}(?:[.,]\d)?)\s*(?:m\s?2|m²|m\^2)", re.IGNORECASE)
_POSTCODE_RE = re.compile(r"\b(1[02]\d{2})\b")  # Geneva-ish 4-digit codes (10xx/12xx)


def _to_float(s: str) -> float | None:
  if s is None:
    return None
  s = s.replace("'", '').replace('’', '').replace(' ', '').replace('\u00a0', '')
  s = s.replace(',', '.')
  s = re.sub(r'\.-$', '', s)
  # collapse multiple dots (thousands vs decimal): keep last as decimal only if 1-2 digits
  m = re.match(r'^(\d+)(?:\.(\d{1,2}))?$', s)
  try:
    return float(s) if m else float(re.sub(r'[^\d.]', '', s) or 0) or None
  except ValueError:
    return None


def _price_to_float(s: str) -> float | None:
  """For prices, apostrophe / comma / space / dot are all thousands separators
  (rents are whole francs), so strip them all and read the integer amount."""
  if s is None:
    return None
  s = re.sub(r"[.,]?\s*[-–]\s*$", '', s.strip())   # trailing '.-' / '.–' / '-'
  s = re.sub(r"[’'.,\s ]", '', s)             # thousands separators
  m = re.search(r'\d+', s)
  return float(m.group()) if m else None


def parse_from_text(text: str) -> dict:
  """Best-effort extraction of numeric fields from a listing's visible text."""
  out = {}
  if not text:
    return out

  pm = _PRICE_RE.search(text) or _PRICE_RE_ALT.search(text)
  if pm:
    val = _price_to_float(pm.group(1))
    # sanity: Geneva rents roughly 800–12000
    if val and 400 <= val <= 15000:
      out['price'] = val

  rm = _PIECES_RE.search(text)
  if rm:
    out['pieces'] = _to_float(rm.group(1))

  sm = _SIZE_RE.search(text)
  if sm:
    val = _to_float(sm.group(1))
    if val and 10 <= val <= 400:
      out['size_m2'] = val

  cm = _POSTCODE_RE.search(text)
  if cm:
    out['postcode'] = cm.group(1)

  return out


def enrich(listing: Listing) -> Listing:
  """Fill any missing numeric fields from raw_text, then annotate features."""
  parsed = parse_from_text(listing.raw_text or listing.title)
  for k, v in parsed.items():
    if getattr(listing, k) in (None, '', 0):
      setattr(listing, k, v)

  text = f'{listing.title} {listing.raw_text}'.lower()

  # features
  feats = []
  for name, kws in config.FEATURE_KEYWORDS.items():
    if any(kw in text for kw in kws):
      feats.append(name)
  listing.features = feats

  # lease takeover
  listing.is_takeover = any(kw in text for kw in config.TAKEOVER_KEYWORDS)

  # area ranking
  pc = listing.postcode
  if pc == config.TARGET_POSTCODE:
    listing.area_rank = 0
  elif pc in config.ACCEPTABLE_POSTCODES:
    listing.area_rank = 1
  elif pc and any(pc.startswith(p) for p in config.CANTON_PREFIXES):
    listing.area_rank = 2
  else:
    listing.area_rank = 9

  return listing


# --- filtering & scoring ------------------------------------------------------
def passes_hard_filters(l: Listing) -> tuple[bool, str]:
  """Returns (ok, reason_if_dropped)."""
  # pièces (bedrooms). If unknown, keep it (don't discard on missing data) but it
  # will score lower.
  if l.pieces is not None and l.pieces < config.MIN_PIECES:
    return False, f'only {l.pieces} pièces (< {config.MIN_PIECES})'

  if l.size_m2 is not None:
    if l.size_m2 < config.MIN_SIZE_M2:
      return False, f'{l.size_m2} m² too small'
    if l.size_m2 > config.MAX_SIZE_M2:
      return False, f'{l.size_m2} m² too big'

  if l.price is not None:
    if l.price > config.STRETCH_MAX_CHF:
      return False, f'CHF {l.price:.0f} over stretch ceiling'
    if l.price > config.BUDGET_CHF:
      l.stretch_budget = True

  return True, ''


def score(l: Listing) -> float:
  """Higher is better. Drives ordering within the dashboard."""
  s = 0.0

  # area is the strongest signal
  s += {0: 1000, 1: 400, 2: 100, 9: 0}[l.area_rank]

  # closeness to ideal size
  if l.size_m2:
    s += max(0, 60 - abs(l.size_m2 - config.IDEAL_SIZE_M2))

  # budget headroom (cheaper scores a little higher; stretch penalised)
  if l.price:
    if l.stretch_budget:
      s -= 40
    else:
      s += max(0, (config.BUDGET_CHF - l.price) / 30)

  # more pièces is good up to a point
  if l.pieces:
    s += min(l.pieces, 5.5) * 15

  # feature bonuses
  bonus = {'elevator': 25, 'ground_floor': 20, 'outdoor': 25, 'laundry': 15, 'parking': 15}
  for f in l.features:
    s += bonus.get(f, 0)

  # lease takeovers often move fastest — small nudge
  if l.is_takeover:
    s += 10

  l.score = s
  return s
