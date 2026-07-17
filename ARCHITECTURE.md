# Architecture and design notes

Everything this project does, how, and why. This is the "how it really works" companion to the
[README](README.md) and the beginner [TUTORIAL](TUTORIAL.md). It also captures what was learned
building the original 24/7 version (including a spam bug and its fix), so the whole thing can be
handed over and understood by anyone.

Credits are virtual game money on **shoovy.wtf**, a channel-points game tied to a Kick streamer's
chat. They have no real-world value and cannot be cashed out.

---

## 1. Big picture

Several small Go programs ("bots") run side by side, each doing one job, all supervised by one
process. Everything runs on a single PC and survives reboots via a Windows logon task.

```
supervisor  ── launches & restarts everything, honors the STOP flag, writes data/status.json
   ├── fisher      casts !fish on worker accounts (async, anti-spam)
   ├── econ        claims !daily, tips worker credits to your main account
   ├── trader      mean-reversion stock trading (PAPER by default)
   ├── collector   logs market data for study/backtest
   ├── watchdog    anti-spam guard: trips the kill-switch if a bot goes crazy
   └── dashboard   local web page (127.0.0.1:8088) + STOP/START button
```

Two account roles:
- **Workers** — the bots act on these: fish, claim daily, trade, and tip out. They need Kick
  chat credentials (bearer + cookies) and a shoovy.wtf session.
- **Main account** — only ever *receives* tips. No bot posts or trades on it. Only its shoovy
  session is needed (so the dashboard can show its balance).

All credentials live in one file, `accounts.json` (gitignored, never committed).

---

## 2. The bots

### fisher
Casts `!fish` in the streamer's Kick chat for each worker, respecting the game's real cooldown
(read from `GET /api/fishing`). It is deliberately careful (see the post-mortem in section 6):
- **Hard floor**: never two casts closer than `hard_floor_seconds` (60s), whatever the logic says.
- **Full cooldown after success**: waits the full `cooldown_min` (about 15 min), never less.
- **Long backoff on failure/ban**: waits 45 min and logs loudly, never retries fast.
- **Respects `enabled=false`**: if fishing is off, it does not post at all.
- **Asynchronous**: per-account random jitter + a startup stagger, so accounts never post at the
  same second.
- The main account is excluded via the `workers` list.

### econ
Two jobs per worker, on a slow schedule:
- **`!daily`** — claims the free daily credits when `daily_ready` is true.
- **`!tip @MainAccount <surplus>`** — sends spare credits (balance above a kept float) to the
  main account, at most once every 36 hours per worker (`tip_cooldown_hrs`). This is the funnel.
  Tips have no fee (verified: 10 sent = 10 received). State is persisted in `data/econ_state.json`.

### trader
Plays the in-game stock market. Strategy and math are in section 4. Key safety property: with
`"live": false` (the default) it computes and logs signals but **never actually trades** (PAPER
mode). It writes every (paper or real) trade to `data/trades.jsonl`, which the dashboard shows.

### collector
Polls `GET /api/stocks` every 15s and appends to `data/quotes.jsonl` (prices) and
`data/news.jsonl` (market events, each labelled with an amount and timestamp). Passive; used to
study the market and backtest strategies offline.

### watchdog
The guard. Every 15s it measures how fast each bot's log file grows. If any bot exceeds its
`max_per_min` (a runaway spam), it writes a timestamped alert to `data/watchdog.log` and creates
the STOP flag. The supervisor then stops the bots. The watchdog never stops itself.

### dashboard
A small local web page. Shows each account's balance and net worth (cash + open positions), the
main account total, live market prices, the trader's realized PnL and recent trades, the tip
schedule, and which bots are up (read from `data/status.json`). The **STOP** button just creates
`data/STOP_ALL`; **Start** deletes it.

### supervisor
Launches each bot with the right config via environment variables and redirects its output to
`data/<bot>.log`. It restarts any bot that crashes. It watches the STOP flag: while the flag
exists, all bots are killed and held; when it disappears, they come back within a few seconds.
It writes `data/status.json` for the dashboard. `install-startup.bat` registers the supervisor to
run at Windows logon, which is what makes the whole thing 24/7.

---

## 3. The kill-switch

A single file, `data/STOP_ALL`. If it exists, the supervisor kills and holds every bot; the
dashboard and watchdog can create it (STOP button, or an auto-trip). `start.bat` / the Start
button delete it. The dashboard and watchdog do **not** stop themselves, so you always keep the
view and the guard.

---

## 4. The stock market and the trading strategy

The market has five fake tickers (`$CHAT`, `$GAMBA`, `$STRMR`, `$WINS`, `$LOSS`). Each has a
"fundamental" tied to observable stream events (chat speed, gambling volume, wins/losses, subs).
Under the hood it is a **bonding-curve AMM** (`depth = 250000`, `fee_pct = 1`): your own buys push
the price up, your sells push it down, prices wiggle randomly, and everything **drifts back to
normal after a pump or dump** (explicit mean reversion).

Consequences, measured on real data:
- A round-trip (buy then sell) costs about **1% minimum** (the sell fee), more if you trade big
  (you eat your own curve twice). So any edge must clear ~1% net per trade.
- **Mean reversion is real and measurable** (AR(1) coefficients ~0.90–0.95, half-lives of a few
  minutes). But a *typical* 1.5% wobble only recovers ~0.75%, which loses to the 1% cost. Only
  **deep dips (beyond ~3%)** revert enough to be worth it, and those are rare.
- News-lag and reacting-to-events edges exist but are individually sub-1%.

So the trader only buys **deep dislocations** (`entry_dev`, default 3% below the moving average),
sells when price returns near the average (`exit_dev`) or after `max_hold_s`, caps its exposure
(`max_positions`), respects the 8s trade cooldown, and does at most one trade per cycle. It uses a
**continuous reconcile**: every cycle the server's portfolio is treated as the source of truth
(adopt what it holds, drop what it sold), which self-heals timeouts and desyncs.

Honest verdict: on real deep dips it is slightly positive, but overall it hovers near break-even
because of the fee. Trading is a bonus, not a reliable earner. The reliable, positive loop is
fishing + daily + tips.

---

## 5. API reference (shoovy.wtf and Kick)

shoovy.wtf runs on Railway (no Cloudflare), so plain HTTP works to read the market and trade. Kick
sits behind Kasada, so posting chat commands needs a browser-like TLS fingerprint — the chat bots
(`fisher`, `econ`) use `github.com/bogdanfinn/tls-client` for that; the market bots use the Go
standard library.

- `GET /api/stocks` (public) → `{quotes:[{symbol,price,change_pct,day_low,day_high,volume}],
  balance, portfolio:[{symbol,shares,avg_cost,price,value,pl_pct}], news, fee_pct, depth, logged_in}`
- `POST /api/stocks/trade` (needs the shoovy session cookie):
  - BUY  `{"symbol","side":"buy","amount":<credits>}`
  - SELL `{"symbol","side":"sell","shares":"all"}` (or a number)
  - Response `{ok,error,message,balance,portfolio}`. Server enforces an 8s cooldown.
- `GET /api/stocks/history?symbol=X&minutes=N` → `{history:[[unix_ts, price], ...]}` (~15–30s/tick)
- `GET /api/me` → `{username, balance, daily_ready, daily_amount, ...}`
- `GET /api/fishing` → `{enabled, remaining, cooldown_min, logged_in, ...}`

Chat commands (posted via `POST https://kick.com/api/v2/messages/send/<chatroom_id>`, the shoovy
chatroom id is `29834074`): `!fish`, `!daily`, `!tip <user> <amount>`, `!duel <user> <amount>`
(coin-flip, no rake, so pointless between your own accounts), `!gamble`, `!predict`, etc.

Credentials in `accounts.json`, per account:
- `bearer` = the value of the kick.com `session_token` cookie (the code URL-decodes it).
- `cookies` = the kick.com cookie set (Cookie-Editor JSON export) — needed to post chat.
- `shoovy_session` = the shoovy.wtf `session` cookie value — needed to read balances and trade.

Sessions expire after roughly a month; refresh them when a bot reports "session invalid".

---

## 6. Post-mortem: the fisher spam bug (and why the guards exist)

In the first 24/7 version, `fisher` did `send()` then `sleep(5s)` whenever `/api/fishing` returned
`remaining=0`. But `remaining=0` is the normal "ready to fish" state. When a cast failed (the
feature was briefly off, or an account got limited), no server cooldown started, so `remaining`
stayed 0, and the bot cast again every 5 seconds — a burst that got the accounts chat-banned.

The fix is the current `fisher` design in section 2: an absolute hard floor, a full cooldown after
success, a long backoff on failure, an `enabled` check, and per-account jitter/stagger. On top of
that, the **watchdog** was added as an independent guard: if any bot's log grows too fast, it trips
the kill-switch and logs the alert. The lesson: a bot that talks to other people needs a hard rate
limit that no logic bug can bypass, plus an outside watchdog.

---

## 7. Config reference

Each bot reads a small JSON config at the install root (the supervisor points each bot at its file
via an environment variable). The channel and chatroom are preset for shoovy; you normally only
set account names.

| File | You set |
|------|---------|
| `accounts.json` | your accounts' credentials (the only secret file) |
| `fisher.config.json` | `workers` (account names) |
| `econ.config.json` | `workers`, `target_user` (main account's Kick username), `keep_float` |
| `trader.config.json` | `account` (which worker to trade), `live` (false = paper), `size_credits` |
| `dashboard.config.json` | `target` (main account name), `port` |
| `watchdog.config.json` | which logs to watch and the per-minute thresholds |

Defaults for cooldowns, jitter, anti-spam floors, and the trading strategy are already tuned and
safe; you do not need to change them.

---

## 8. History

This PC edition is a port of a 24/7 system that originally ran on RISC-V single-board computers
(Lichee boards) using busybox `init.d` for persistence. The board version and its French docs live
in a separate private repo (`kick-xp-farmer`). This edition drops the boards entirely: it is
Windows-native, English, and kept simple enough for a beginner to set up and run.
