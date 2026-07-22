# report.py — builds a self-contained HTML dashboard (index.html) for GitHub Pages.
import html
import time

import config

_SOURCE_COLORS = {
  'anibis': '#e8562a', 'homegate': '#00a15a', 'immoscout': '#d4145a', 'flatfox': '#2f6df6',
}
_FEATURE_LABELS = {
  'elevator': 'Lift', 'ground_floor': 'Ground floor', 'outdoor': 'Balcony/terrace',
  'laundry': 'In-unit laundry', 'parking': 'Parking',
}
_AREA_LABELS = {0: '1205 — your area', 1: 'Central Geneva', 2: 'Canton Geneva', 9: 'Location unclear'}


def _card(l, is_new: bool) -> str:
  price = f"CHF {l.price:,.0f}".replace(',', "'") if l.price else '—'
  pieces = f'{l.pieces:g} pièces' if l.pieces else 'pièces ?'
  size = f'{l.size_m2:g} m²' if l.size_m2 else 'm² ?'
  pc = html.escape(l.postcode or '—')
  feats = ''.join(
    f'<span class="badge feat">{_FEATURE_LABELS[f]}</span>' for f in l.features if f in _FEATURE_LABELS
  )
  flags = ''
  if is_new:
    flags += '<span class="badge new">NEW</span>'
  if l.is_takeover:
    flags += '<span class="badge takeover">Lease takeover</span>'
  if l.stretch_budget:
    flags += '<span class="badge stretch">Over budget</span>'
  avail = f'<div class="avail">Available: {html.escape(l.available)}</div>' if l.available else ''
  color = _SOURCE_COLORS.get(l.source, '#888')
  title = html.escape((l.title or l.url)[:140])

  return f'''
  <a class="card{' is-new' if is_new else ''}" href="{html.escape(l.url)}" target="_blank" rel="noopener">
    <div class="row1">
      <span class="price">{price}</span>
      <span class="pc">{pc}</span>
    </div>
    <div class="specs">{pieces} · {size}</div>
    <div class="flags">{flags}</div>
    <div class="title">{title}</div>
    <div class="feats">{feats}</div>
    {avail}
    <div class="src" style="color:{color}">{l.source}</div>
  </a>'''


def build_html(listings, new_uids: set) -> str:
  ts = time.strftime('%A %d %B %Y, %H:%M')
  new_count = sum(1 for l in listings if l.uid in new_uids)

  # group by area rank
  groups = {0: [], 1: [], 2: [], 9: []}
  for l in listings:
    groups.get(l.area_rank, groups[9]).append(l)

  sections = []
  for rank in (0, 1, 2, 9):
    items = groups[rank]
    if not items:
      continue
    cards = '\n'.join(_card(l, l.uid in new_uids) for l in items)
    sections.append(
      f'<h2 class="area">{_AREA_LABELS[rank]} <span class="count">{len(items)}</span></h2>'
      f'<div class="grid">{cards}</div>'
    )
  body = '\n'.join(sections) or '<p class="empty">No matching listings today. The watch will keep looking each morning.</p>'

  return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(config.DASHBOARD_TITLE)}</title>
<style>
  :root {{ --bg:#f6f5f2; --card:#fff; --ink:#1a1a1a; --muted:#6b6b6b; --line:#e6e3dd; --accent:#c0392b; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:16px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         background:var(--bg); color:var(--ink); }}
  header {{ padding:28px 22px 18px; border-bottom:1px solid var(--line); background:var(--card); }}
  h1 {{ margin:0 0 4px; font-size:22px; letter-spacing:-.2px; }}
  .sub {{ color:var(--muted); font-size:14px; }}
  .summary {{ margin-top:12px; display:flex; gap:18px; flex-wrap:wrap; font-size:14px; }}
  .summary b {{ font-size:20px; }}
  main {{ padding:22px; max-width:1100px; margin:0 auto; }}
  h2.area {{ font-size:15px; text-transform:uppercase; letter-spacing:.6px; color:var(--muted);
             margin:30px 0 12px; display:flex; align-items:center; gap:10px; }}
  h2.area .count {{ background:var(--line); color:var(--ink); border-radius:20px; padding:2px 10px; font-size:12px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:14px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:15px;
           text-decoration:none; color:inherit; display:flex; flex-direction:column; gap:7px;
           transition:transform .08s ease, box-shadow .08s ease; }}
  .card:hover {{ transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.08); }}
  .card.is-new {{ border-color:var(--accent); box-shadow:0 0 0 2px rgba(192,57,43,.10); }}
  .row1 {{ display:flex; justify-content:space-between; align-items:baseline; }}
  .price {{ font-size:20px; font-weight:700; }}
  .pc {{ font-size:13px; color:var(--muted); }}
  .specs {{ font-size:14px; color:#333; }}
  .title {{ font-size:13px; color:var(--muted); line-height:1.35;
            display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
  .flags, .feats {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .badge {{ font-size:11px; padding:2px 8px; border-radius:20px; font-weight:600; }}
  .badge.new {{ background:var(--accent); color:#fff; }}
  .badge.takeover {{ background:#2f6df6; color:#fff; }}
  .badge.stretch {{ background:#e0a800; color:#3a2f00; }}
  .badge.feat {{ background:var(--line); color:#444; font-weight:500; }}
  .avail {{ font-size:12px; color:var(--muted); }}
  .src {{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; margin-top:2px; }}
  .empty {{ color:var(--muted); }}
  footer {{ padding:22px; text-align:center; color:var(--muted); font-size:12px; }}
</style></head><body>
<header>
  <h1>{html.escape(config.DASHBOARD_TITLE)}</h1>
  <div class="sub">Updated {ts}</div>
  <div class="summary">
    <span><b>{len(listings)}</b> matches</span>
    <span><b>{new_count}</b> new since last run</span>
    <span>Budget ≤ CHF {config.BUDGET_CHF:,}</span>
    <span>≥ {config.MIN_PIECES:g} pièces (≈3 bedrooms)</span>
  </div>
</header>
<main>{body}</main>
<footer>Automated morning watch · sources: Anibis, Homegate, ImmoScout24, Flatfox · new listings ringed in red</footer>
</body></html>'''
