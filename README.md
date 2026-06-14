# AUDUSD ICT/SMC Alert Bot

Adapted from the GBPUSD HTF Narrative bot. Same top-down checklist:
Daily Bias → 4H PD Array → 1H PD Array → 15m PD Array → 5m Entry
(FVG/IFVG, TDO, NDOG/NWOG, VWAP/EMA/SMA confluence). Paper alerts only
via Telegram - no order execution.

## What's new vs the GBPUSD bot

1. **`td_cache.py`** - file-based cache for Twelve Data candle requests.
   Higher timeframes (1day/4h/1h/15min) are cached with TTLs so the
   bot stays well under the 800 credits/day free-tier limit even
   while running a 5-minute scan loop. Only the 5min timeframe is
   always fetched live.

2. **`risk_tracker.py`** - shared exposure tracker. Since this bot and
   the GBPUSD bot both trade FundingPips account #20084818 (EUR 8,000,
   3% / EUR 240 daily loss limit), each bot registers its active
   signal's allocated risk (default 0.5% = EUR 40/trade) to a shared
   JSON file. Before sending a new alert, a bot checks combined
   exposure and appends a `RISK BUDGET` warning to the Telegram
   message if both bots' active signals together would exceed the
   daily loss limit. It does not block or auto-close anything - it's
   a visibility layer so you can decide whether to act on both
   signals.

## Setup

```bash
git clone https://github.com/Hirthick21/AUD_forex_repo.git
cd AUD_forex_repo
pip install -r requirements.txt
cp .env.example .env
# edit .env with your real Telegram token/chat ID and Twelve Data key
python audusd_bot.py
```

## Connecting this to the GBPUSD bot's risk tracker

For the shared risk tracker to actually coordinate both bots, the
GBPUSD repo needs the same `risk_tracker.py` file and a couple of
small additions. On the GBPUSD bot:

1. Copy `risk_tracker.py` into the GBPUSD repo.
2. In its `.env`, set:
   ```
   BOT_NAME=GBPUSD_BOT
   SHARED_RISK_STATE_PATH=/home/youruser/shared_risk_state.json
   ACCOUNT_SIZE=8000
   DAILY_LOSS_LIMIT_PCT=3.0
   RISK_PER_TRADE_PCT=0.5
   SIGNAL_EXPIRY_SECONDS=14400
   ```
   **`SHARED_RISK_STATE_PATH` must be the exact same path as in this
   AUDUSD bot's `.env`**, and both bots must run on the same
   machine/server.
3. In the GBPUSD bot's `main.py`, add the import:
   ```python
   from risk_tracker import exposure_warning, register_signal, risk_per_trade_eur
   ```
4. In the main loop, right before `send_signal(signal)`, add:
   ```python
   trade_risk = risk_per_trade_eur()
   warn = exposure_warning(BOT_NAME, signal["pair"], signal["side"], trade_risk)
   if warn:
       signal["warnings"].append(f"RISK BUDGET: {warn}")
   ```
   and right after `send_signal(signal)`, add:
   ```python
   register_signal(BOT_NAME, signal["pair"], signal["side"], trade_risk)
   ```

Once both bots share the same state file, a GBPUSD signal and an
AUDUSD signal firing close together will each show the combined risk
in their Telegram warnings.

## Notes on AUDUSD vs GBPUSD config

- `MIN_SL_DISTANCE["AUD/USD"] = 0.0010` and `PIP_100_RANGE["AUD/USD"]
  = 0.0100` - starting values matching EUR/USD's volatility class.
  AUD/USD generally has slightly lower ATR than GBP/USD; tune these
  after observing a week or two of live signals.
- `MIN_CONFIDENCE`, `MIN_RR`, `RR_TARGET`, session windows, and
  cooldown are unchanged from the GBPUSD bot as a starting point.

## Risk reminders (FundingPips #20084818)

- Daily Loss Limit: EUR 240 (3% of EUR 8,000), shared across all
  instruments and both bots.
- Max Loss Limit: EUR 480 (6%, locks at EUR 8,000 floor once equity
  reaches EUR 8,400).
- This bot is alert-only - position sizing and execution are manual.
