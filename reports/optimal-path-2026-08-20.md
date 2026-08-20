# Optimal path to rank 1 — 2026-08-20 (first model, offline)

Built from the current fact store while the backend is in a down-window (no live scan this pass).
Fishing is the only fully-quantified earner; daily and business are upside pending one live
capture. Every number cites its source.

## The binding metric: credits per REQUEST, not per hour

Because the backend flaps (duty cycle ~0.765, down-windows of minutes), up-window requests are
the scarce resource. Rank mechanics by credits/request first, credits/hour second.

| mechanic | credits/request | credits/hour | verdict | source |
|---|---|---|---|---|
| daily | whole daily amount in **1 request** | once/24h | **best/req if the amount is non-trivial** — UNQUANTIFIED, capture `/api/me` daily_amount | facts (daily_ready/amount fields) |
| fishing | **210.5 cr / cast** (1 req) | ~4,210 (20 casts/h) | the engine, cooldown-bound | catch 210.5 n=2 `analyze_chat.py`, 20 casts/h theoretical |
| business collect | accumulated pile / ~6.3 req | passive | UNQUANTIFIED rate — capture `/api/business` | T*=C/r `model.py`, 6.3 req/collect `infer.py` |
| stocks | ~0 (1 % round-trip fee) | ~break-even | EXCLUDE as engine | fee 1 % `market.jsonl` |
| casino | **negative every game** | negative | EXCLUDE (sink) | games_info EV, best plinko 11/high −0.84 %, rakeback leaves −0.34 % |

## The fishing engine (quantified)

Cooldown-bound at ~20 casts/h × 210.5 cr = **4,210 cr/h ceiling** = 101,040 cr/day at 100 %
uptime. At the measured duty cycle 0.765: **~77,300 cr/day per account**.

Target: leaderboard rank 1 = **886,890 cr** (fresh, `/api/leaderboard`, and climbing).

## Days to rank 1, by account count

Accounts funnel to one main via `!tip` (0 % fee, verified), and fishing is per-account
cooldown-bound, so N accounts scale nearly linearly:

| accounts | days to rank 1 |
|---|---|
| 1 | 11.5 |
| 2 | 5.7 |
| 3 | 3.8 |
| 4 | 2.9 |
| 5 | 2.3 |

## Optimal per-account, per-up-window sequence

When the sentinel shows up, per worker account:
1. **`!daily`** if ready — 1 request, a whole day's chunk, the best credits/request action. Once/24h.
2. **`!fish`** on cooldown — the repeatable 210.5 cr/request engine. This is where the time goes.
3. **`!collect`** business if the optimal cadence T* has elapsed — cheap in requests, free passive.
4. **`!tip` surplus to main** every ~36 h — consolidation, 0 % fee.
5. **Never** stocks (break-even) or casino (negative EV). They only bleed scarce requests.

## Highest-leverage change

**Account count.** Fishing is per-account cooldown-bound, so it does not speed up with more
requests on one account — it speeds up with more accounts, ~linearly. Duty cycle is out of our
control (backend health). So the lever is: more worker accounts, each running the sequence above.

## What must be captured next up-window to firm this up

- `/api/me` → the actual **daily amount** (likely the top credits/request action, currently a blank).
- `/api/business` → the passive **rate r** and collect cost, to price the business loop.
- Re-sample **fishing catch value** — 210.5 is n=2; the whole model scales with it.

## The standing blocker

The plan is executable only with valid worker sessions in `accounts.json` (a human login). Until
then this is the plan the farmer will run, not a running farm.
