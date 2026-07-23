# sources.py — one fetcher per portal.
#
# DESIGN NOTE (please read once):
# These sites are JavaScript-heavy and change their markup periodically. Rather
# than depend on fragile CSS classes, each fetcher uses a resilient strategy:
#   1. Render the search page with a headless browser (Playwright).
#   2. Collect every link that looks like a *listing detail* page.
#   3. Capture the human-readable text around each link.
#   4. Hand that text to model.parse_from_text(), which regex-extracts
#      price / pièces / m² / postcode.
# This survives most redesigns. If a source ever returns 0 results, the only
# thing you usually need to update is SEARCH_URLS or DETAIL_HREF below.
#
# Each fetcher is wrapped in try/except by main.py, so one broken source never
# stops the others.

import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

import config
from model import Listing

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')


# ------------------------------------------------------------------ Playwright
def render(url: str, scrolls: int = 4) -> str:
  """Load a URL in headless Chromium and return the settled HTML."""
  from playwright.sync_api import sync_playwright
  html = ''
  with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(user_agent=UA, locale='fr-CH',
                              viewport={'width': 1280, 'height': 2000})
    page = ctx.new_page()
    try:
      page.goto(url, timeout=config.REQUEST_TIMEOUT * 1000, wait_until='domcontentloaded')
      page.wait_for_timeout(2500)
      for _ in range(scrolls):  # trigger lazy loading
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(800)
      html = page.content()
    finally:
      browser.close()
  return html


def _extract_cards(html: str, base: str, detail_re: re.Pattern, source: str,
                    require_geneva_text: bool = True) -> list[Listing]:
  """Generic: every detail link + its nearest text block becomes a Listing.
  `require_geneva_text` guards against noise on canton-wide searches (e.g.
  Anibis); skip it when the search URL itself is already Geneva-scoped and the
  card text may legitimately omit "Genève"/a postcode (e.g. immobilier.ch cards
  for communes like Carouge or Onex)."""
  soup = BeautifulSoup(html, 'html.parser')
  seen_urls = set()
  out = []
  for a in soup.find_all('a', href=True):
    href = a['href']
    if not detail_re.search(href):
      continue
    full = urllib.parse.urljoin(base, href.split('?')[0])
    if full in seen_urls:
      continue
    # climb up a few parents to grab a meaningful text block
    node = a
    text = ''
    for _ in range(4):
      node = node.parent if node.parent else node
      t = node.get_text(' ', strip=True)
      if len(t) > len(text):
        text = t
      if len(text) > 80:
        break
    text = re.sub(r'\s+', ' ', text)[:600]
    # only keep Geneva-relevant cards to cut noise
    if require_geneva_text and 'genè' not in text.lower() and 'genf' not in text.lower() \
       and not re.search(r'\b1[02]\d{2}\b', text):
      continue
    seen_urls.add(full)
    out.append(Listing(source=source, url=full, title=text[:120], raw_text=text))
  return out


# ------------------------------------------------------------------ Anibis
def fetch_anibis() -> list[Listing]:
  base = 'https://www.anibis.ch'
  # Geneva canton, apartments, rent (URL taken from a live search).
  search = ('https://www.anibis.ch/fr/q/immobilier-geneve-appartements-louer/'
            'Ak8CqcmVhbEVzdGF0ZZSSkqtsaXN0aW5nVHlwZalhcGFydG1lbnSSqXByaWNlVHlwZaRSRU5UwMCRk6hsb2NhdGlvbrFnZW8tY2FudG9uLWdlbmV2ZcA')
  detail_re = re.compile(r'/fr/(vi|s)/')
  cards = []
  for page in range(1, config.MAX_PAGES_PER_SOURCE + 1):
    url = search if page == 1 else f'{search}?page={page}'
    html = render(url)
    found = _extract_cards(html, base, detail_re, 'anibis')
    if not found:
      break
    cards.extend(found)
  return cards


# ------------------------------------------------------------------ Homegate
def fetch_homegate() -> list[Listing]:
  base = 'https://www.homegate.ch'
  search = 'https://www.homegate.ch/rent/apartment/city-geneva/matching-list'
  detail_re = re.compile(r'/rent/\d')
  cards = []
  for page in range(1, config.MAX_PAGES_PER_SOURCE + 1):
    url = search if page == 1 else f'{search}?ep={page}'
    html = render(url)
    found = _extract_cards(html, base, detail_re, 'homegate')
    if not found:
      break
    cards.extend(found)
  return cards


# ------------------------------------------------------------------ ImmoScout24
def fetch_immoscout() -> list[Listing]:
  base = 'https://www.immoscout24.ch'
  search = 'https://www.immoscout24.ch/en/flat/rent/city-geneve'
  # ImmoScout24 is now on the Swiss Marketplace Group platform and uses the same
  # /rent/<id> detail URLs as Homegate (verified live 2026-07).
  detail_re = re.compile(r'/rent/\d')
  cards = []
  for page in range(1, config.MAX_PAGES_PER_SOURCE + 1):
    url = search if page == 1 else f'{search}?pn={page}'
    html = render(url)
    found = _extract_cards(html, base, detail_re, 'immoscout')
    if not found:
      break
    cards.extend(found)
  return cards


# ------------------------------------------------------------------ Flatfox
# Attribute tokens the Flatfox API returns, mapped to the visible-text keywords
# our model already understands (so enrich() detects the same features).
_FLATFOX_ATTR_TEXT = {
  'lift': 'ascenseur lift',
  'balconygarden': 'balcon terrasse jardin',
  'balcony': 'balcon', 'terrace': 'terrasse', 'garden': 'jardin',
  'washingmachine': 'lave-linge machine à laver',
  'tumbler': 'sèche-linge',
  'parking': 'parking place de parc', 'garage': 'garage',
  'wheelchairaccessible': 'rez-de-chaussée accessible',
}


# Canton-Geneva bounding box for the Flatfox map/pin endpoint.
_FLATFOX_BBOX = {'west': 5.90, 'south': 46.10, 'east': 6.35, 'north': 46.37}


def _flatfox_is_geneva(it: dict) -> bool:
  """Keep only canton-Geneva listings (zipcode 1200–1299 or state GE)."""
  zc = it.get('zipcode')
  try:
    if zc is not None and 1200 <= int(zc) <= 1299:
      return True
  except (TypeError, ValueError):
    pass
  return str(it.get('state') or '').upper() == 'GE'


def _flatfox_to_listing(it: dict) -> Listing:
  detail = it.get('url') or it.get('short_url') or ''
  full = urllib.parse.urljoin('https://flatfox.ch', detail)
  title = (it.get('public_title') or it.get('short_title')
           or it.get('rent_title') or '')
  attrs = [a.get('name', '') for a in (it.get('attributes') or [])]
  attr_text = ' '.join(_FLATFOX_ATTR_TEXT.get(a, a) for a in attrs)
  price = _num(it.get('rent_gross'))
  if price is None and str(it.get('price_unit')) == 'monthly':
    price = _num(it.get('price_display'))
  size = _num(it.get('surface_living') or it.get('livingspace')
              or it.get('space_display'))
  raw_text = ' '.join(str(b) for b in [
    title, it.get('description_title'), it.get('description'),
    it.get('public_address'), attr_text,
    'meublé furnished' if it.get('is_furnished') else '',
  ] if b)
  return Listing(
    source='flatfox', url=full, title=title[:120], raw_text=raw_text,
    price=price,
    pieces=_num(it.get('number_of_rooms')),
    size_m2=size,
    postcode=str(it.get('zipcode') or '') or None,
    address=it.get('public_address') or it.get('street') or '',
    available=str(it.get('moving_date') or ''))


def fetch_flatfox() -> list[Listing]:
  """Flatfox's public API ignores location/ordering params on public-listing.
  Its site actually filters via the /pin/ endpoint (honours the map bounding
  box), then batch-fetches the matched listings by pk. We replicate that:
      1) GET /api/v1/pin/  with the Geneva bbox  -> list of {pk, ...}
      2) GET /api/v1/public-listing/?pk=..&pk=.. -> full listing dicts
  """
  headers = {'User-Agent': UA, 'Accept': 'application/json'}
  out = []
  try:
    pin_params = {'offer_type': 'RENT', 'object_category': 'APARTMENT',
                  'max_count': 400, **_FLATFOX_BBOX}
    r = requests.get('https://flatfox.ch/api/v1/pin/', params=pin_params,
                     headers=headers, timeout=config.REQUEST_TIMEOUT)
    r.raise_for_status()
    pins = r.json()
    pks = [p.get('pk') for p in pins if p.get('pk')]

    # batch-fetch full details, chunked to keep URLs sane
    for i in range(0, len(pks), 40):
      chunk = pks[i:i + 40]
      dr = requests.get('https://flatfox.ch/api/v1/public-listing/',
                        params=[('limit', '0')] + [('pk', k) for k in chunk],
                        headers=headers, timeout=config.REQUEST_TIMEOUT)
      dr.raise_for_status()
      data = dr.json()
      items = data if isinstance(data, list) else data.get('results', [])
      for it in items:
        if it.get('object_category') != 'APARTMENT':
          continue
        if not _flatfox_is_geneva(it):
          continue
        out.append(_flatfox_to_listing(it))
      time.sleep(0.4)  # stay polite between batches
    if out:
      return out
  except (requests.RequestException, ValueError):
    pass

  # Fallback: render the search page (rarely needed).
  base = 'https://flatfox.ch'
  search = ('https://flatfox.ch/en/search/?offer_type=RENT'
            '&object_category=APARTMENT&query=Gen%C3%A8ve')
  detail_re = re.compile(r'/(en|fr|de)/flat/')
  html = render(search)
  return _extract_cards(html, base, detail_re, 'flatfox')


# ------------------------------------------------------------------ immobilier.ch
def fetch_immobilier() -> list[Listing]:
  """immobilier.ch is server-rendered (no Playwright needed, verified live
  2026-07). Detail URLs look like
  /fr/louer/appartement/geneve/<commune>/<agency-slug>/<title>-<id>; the
  /geneve/ path segment already scopes results to the canton, so — unlike
  Anibis's canton-wide search — we don't also require "Genève"/a postcode in
  the card text (communes like Carouge or Onex often show neither)."""
  base = 'https://www.immobilier.ch'
  detail_re = re.compile(r'/fr/louer/appartement/geneve/[^/"?]+/[^/"?]+/[^/"?]+-\d{6,}')
  cards = []
  for page in range(1, config.MAX_PAGES_PER_SOURCE + 1):
    url = f'{base}/fr/louer/appartement/geneve/page-{page}'
    r = requests.get(url, headers={'User-Agent': UA}, timeout=config.REQUEST_TIMEOUT)
    if r.status_code != 200:
      break
    found = _extract_cards(r.text, base, detail_re, 'immobilier', require_geneva_text=False)
    if not found:
      break
    cards.extend(found)
  return cards


def _num(v):
  try:
    return float(str(v).replace("'", '').replace(',', '.')) if v not in (None, '') else None
  except (TypeError, ValueError):
    return None


# ------------------------------------------------------------------ registry
ALL_SOURCES = {
  'anibis': fetch_anibis,
  'homegate': fetch_homegate,
  'immoscout': fetch_immoscout,
  'flatfox': fetch_flatfox,
  'immobilier': fetch_immobilier,
}
