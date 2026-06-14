"""
Lightweight file-based cache for Twelve Data candle requests.

Higher timeframes (1day, 4h, 1h, 15min) don't need to be re-fetched on
every 5-minute scan cycle - a new Daily candle only forms once a day,
a new 4H candle every 4 hours, etc. Caching these with sensible TTLs
cuts API credit usage by roughly 60-70% versus fetching all 5
timeframes on every scan.

Only the 5min timeframe (TTL=0) is always fetched live, since that's
the entry-trigger timeframe and the scan interval itself.
"""

import json
import os
import time

CACHE_FILE = os.getenv("TD_CACHE_FILE", "td_cache.json")

# Time-to-live per interval, in seconds.
CACHE_TTL_SECONDS = {
    "1day": 6 * 3600,    # refresh every 6 hours (~4 calls/day)
    "4h": 60 * 60,        # refresh hourly (~6 calls/day)
    "1h": 20 * 60,        # refresh every 20 min (~24 calls/day)
    "15min": 15 * 60,     # refresh every 15 min (~96 calls/day)
    "5min": 0,            # always live (~280 calls/day at 5min scan)
}


def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        print("Cache save error:", e)


def get_candles_cached(fetch_fn, pair, interval, outputsize=120):
    """
    Wraps a get_candles(pair, interval, outputsize) function with a
    TTL-based file cache. Pass your existing Twelve Data fetch
    function as fetch_fn - this module makes no API calls itself.
    """
    ttl = CACHE_TTL_SECONDS.get(interval, 0)
    key = f"{pair}|{interval}|{outputsize}"
    now = time.time()

    if ttl > 0:
        cache = _load_cache()
        entry = cache.get(key)

        if entry and (now - entry.get("fetched_at", 0)) < ttl:
            return entry["data"]

    data = fetch_fn(pair, interval, outputsize)

    if ttl > 0 and data:
        cache = _load_cache()
        cache[key] = {"fetched_at": now, "data": data}
        _save_cache(cache)

    return data
