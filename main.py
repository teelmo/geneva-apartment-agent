#!/usr/bin/env python3
# main.py — run the whole morning search once.
#
#   python main.py           # normal run: scrape, filter, dedup, write dashboard
#   python main.py --dry     # skip scraping; use sample.json (for testing layout)
#
import json
import os
import sys
import time

import config
import model
import store
import report
import notify
import sources


def gather() -> list[model.Listing]:
  """Run every source; a failure in one never stops the others."""
  all_listings = []
  for name, fn in sources.ALL_SOURCES.items():
    t0 = time.time()
    try:
      found = fn()
      print(f'  [{name}] {len(found)} raw listings ({time.time()-t0:.1f}s)')
      all_listings.extend(found)
    except Exception as e:  # noqa: BLE001 — we want to keep going
      print(f'  [{name}] FAILED: {type(e).__name__}: {e}')
  return all_listings


def main():
  dry = '--dry' in sys.argv
  print(f'Geneva apartment watch — {time.strftime("%Y-%m-%d %H:%M")}')

  if dry and os.path.exists('sample.json'):
    raw = [model.Listing(**{k: v for k, v in d.items() if k != 'uid'})
           for d in json.load(open('sample.json'))]
  else:
    raw = gather()

  # enrich + filter + score
  kept, dropped = [], 0
  seen_uid = set()
  for l in raw:
    model.enrich(l)
    if l.uid in seen_uid:      # de-dupe within this run
      continue
    seen_uid.add(l.uid)
    ok, reason = model.passes_hard_filters(l)
    if not ok:
      dropped += 1
      continue
    model.score(l)
    kept.append(l)

  kept.sort(key=lambda x: -x.score)
  print(f'Kept {len(kept)} after filtering ({dropped} dropped).')

  # figure out which are new since last run
  seen = store.load_seen()
  new, seen = store.split_new(kept, seen)
  store.save_seen(seen)
  new_uids = {l.uid for l in new}
  print(f'{len(new)} new since last run.')

  # write dashboard + machine-readable JSON
  os.makedirs('public', exist_ok=True)
  with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(report.build_html(kept, new_uids))
  with open('public/listings.json', 'w', encoding='utf-8') as f:
    json.dump([l.to_dict() for l in kept], f, ensure_ascii=False, indent=2)
  print('Wrote public/index.html and public/listings.json')

  # optional email
  dash = os.environ.get('DASHBOARD_URL', '')
  if notify.maybe_email(new, dash):
    print('Email digest sent.')


if __name__ == '__main__':
  main()
