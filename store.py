# store.py — remembers which listings we've already reported, so each morning
# only shows genuinely new matches. Stored as a small JSON file committed back
# to the repo by the GitHub Action (or kept locally if you run on your Mac).
import json
import os
import time

STORE_PATH = os.environ.get('SEEN_STORE', 'seen.json')


def load_seen() -> dict:
  if not os.path.exists(STORE_PATH):
    return {}
  try:
    with open(STORE_PATH, 'r', encoding='utf-8') as f:
      return json.load(f)
  except (json.JSONDecodeError, OSError):
    return {}


def save_seen(seen: dict) -> None:
  with open(STORE_PATH, 'w', encoding='utf-8') as f:
    json.dump(seen, f, ensure_ascii=False, indent=0)


def split_new(listings, seen: dict):
  """Return (new_listings, updated_seen). Marks everything as seen with a first-seen date."""
  today = time.strftime('%Y-%m-%d')
  new = []
  for l in listings:
    if l.uid not in seen:
      seen[l.uid] = {'first_seen': today, 'url': l.url, 'price': l.price}
      new.append(l)
  # prune very old entries to keep the file small (> 120 days)
  cutoff = time.time() - 120 * 86400
  for uid in list(seen.keys()):
    fs = seen[uid].get('first_seen', today)
    try:
      t = time.mktime(time.strptime(fs, '%Y-%m-%d'))
      if t < cutoff:
        del seen[uid]
    except ValueError:
      pass
  return new, seen
