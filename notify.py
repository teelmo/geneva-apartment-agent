# notify.py — optional email digest. Only runs if SMTP_* env vars are set.
# Set these as GitHub repository Secrets to enable (see README).
import os
import smtplib
from email.mime.text import MIMEText

import config


def maybe_email(new_listings, dashboard_url: str = '') -> bool:
  host = os.environ.get('SMTP_HOST')
  user = os.environ.get('SMTP_USER')
  pw = os.environ.get('SMTP_PASS')
  to = os.environ.get('SMTP_TO', user)
  if not (host and user and pw and to):
    return False  # email not configured — silently skip
  if not new_listings:
    return False  # nothing new; don't send an empty email

  lines = [f'{len(new_listings)} new apartment match(es) this morning:', '']
  for l in sorted(new_listings, key=lambda x: -x.score):
    price = f'CHF {l.price:.0f}' if l.price else 'CHF ?'
    pieces = f'{l.pieces:g}p' if l.pieces else '?p'
    size = f'{l.size_m2:g}m²' if l.size_m2 else '?m²'
    star = '★ ' if l.area_rank == 0 else ''
    lines.append(f'{star}{price} · {pieces} · {size} · {l.postcode or "?"} [{l.source}]')
    lines.append(f'  {l.url}')
  if dashboard_url:
    lines += ['', f'Full dashboard: {dashboard_url}']

  fb = getattr(config, 'FACEBOOK_GROUPS', {}) or {}
  if fb:
    lines += ['', 'Facebook groups to skim by hand:']
    for name, url in fb.items():
      lines.append(f'  · {name}: {url}')

  msg = MIMEText('\n'.join(lines), 'plain', 'utf-8')
  msg['Subject'] = f'🏠 {len(new_listings)} new Geneva apartment(s) — 1205 watch'
  msg['From'] = user
  msg['To'] = to

  port = int(os.environ.get('SMTP_PORT', '587'))
  with smtplib.SMTP(host, port) as s:
    s.starttls()
    s.login(user, pw)
    s.sendmail(user, [x.strip() for x in to.split(',')], msg.as_string())
  return True
