# Shoovy — complete recursive analysis

Built in layers. Each layer only asserts what the layer beneath it established; nothing
floats without support. Numbers cite their source in the `data/study/` corpus. Statuses are
the fact-store's own: `measured` (seen on the wire), `derived` (computed, names its supports),
`assumed` (inherited, needs re-verification), `refuted` (killed by measurement).

Store snapshot: 205 facts — 54 measured, 26 derived, 7 candidate, 109 assumed, 9 refuted.
The refuted column is the health signal: the study is falsifying its own inherited numbers
instead of propagating them.

---

## Layer 0 — Infrastructure decides everything above it

Nothing higher up means anything if the site does not answer. This is the root of the recursion.

- **Fronting**: Cloudflare in front of Railway (`Server: cloudflare`, `CF-RAY`,
  `x-railway-edge: cdg1`, `requests.jsonl`). The old "no Cloudflare" note is corrected.
- **No bot filtering on shoovy itself**: `User-Agent: Go-http-client/1.1` → 200 while the site
  is healthy (`infra:shoovy.wtf :: accepte_client_stdlib = true`). So **no tls-client is needed
  for shoovy** (unlike Kick/Kasada). A freeing fact: the difficulty is not the anti-bot layer,
  it is elsewhere.
- **Cold start ~40 s** after idle (n=3). Any short timeout fails on first contact. Hard
  consequence: client timeout = 60 s, non-negotiable.
- **The wall: availability.** At the last measured window (2026-08-19, `uptime.py`) the site
  served 429 `rate limited` (12 bytes, `x-railway-edge`, no `Retry-After`) or 502. A real
  browser gets the same 502. `infra:shoovy.wtf :: ip_bannie = refuted`. Best-supported reading:
  **the Railway deployment is unhealthy**; 429 and 502 are two faces of one degradation.

This layer produces the single number that governs everything: **p, the probability that a
call succeeds.**

---

## Layer 1 — Availability is not a number, it is a function of how many calls you chain

This is the recursive core: every mechanic above inherits p, composed by the number of
requests it chains.

- Trivial read: **p = 0.158** (n=19, `uptime.py`).
- A player command actually processed: **0.038** (n=52, `analyze_chat.py`). A read that lands
  does **not** guarantee an action lands — two different availabilities.
- Composition (`infer.py`, `budget.py`): 2 chained calls = 0.025, 3 = 0.0039. Longest usable
  streak observed: **2 requests** before a 429.
- Derived reading rule: *retryable* → `1-(1-p)^k` over the window; *deadline* → `p^steps`.
  Retrying saves the retryable path, not the deadline path.

**Architectural consequence, derived not opined**: a three-independent-poller design (trader
240 req/h + collector + dashboard) is dead at p=0.158. It needs **one shared client, one
global budget** (`client.py` is that serialization point). The scarce resource is not request
budget, it is availability — and pacing buys none of it.

---

## Layer 2 — Mechanics, raw measured value

What the site documents about itself, filtered by what we actually saw on the wire.

**Fishing** (the safe loop):
- Catch value = **210.5 credits** (n=2, `analyze_chat.py`) — thin sample, re-measure.
- 100-species catalogue; a catch announces weight/species/rarity/value/progress/personal-best
  (`payouts.py`).
- Stock decay: **10 %/day**, 24 h fresh window, 10 % floor (`/api/fishing`, answers without a
  session).
- `!fish` = **0.84** of observed commands (n=25) — the dominant chat mechanic.

**Stocks**: 5 tickers (CHAT/GAMBA/STRMR/WINS/LOSS), **1 % fee**, AMM depth 250,000 credits,
8 s cooldown, trading open (`market.jsonl`). Plus `/api/stocks/history` (backtest), plus
`/api/predictions` (bet/lock/resolve).

**Casino**: the client carries **structural** params but **not the odds**
(`le_client_porte_t_il_les_probabilites = false`, n=11). Captured params: plinko (8–16 rows,
low/med/high), mines (25 tiles, ≤24 mines), keno (40-board, draw 10, pick ≤10), cases &
dragon-tower (easy→master), blackjack (3:2 natural), wheel (1/3/5/10/20), coinflip, rps (tie
returns stake, PvP pot = stake×2). **Rakeback** = credits returned on casino volume, a lever
the farmer ignores entirely.

**Uncovered, real surface**: business (buy/collect/improve/launder/sell/slot), crime,
predictions, raffles, shop/redeem. ~60 endpoints, ~12 mechanics, the farmer covers 3½.

**Kick (delivery path, healthy)**: chatroom `29834074`, 1 s slow-mode, 6-min follow gate
before posting, chat readable from a server via Pusher (`pusher_probe.py`), 19.2 msg/min. The
full command loop holds on Kick's side; what it does not fix is the game backend's health and
the web pages with no chat equivalent.

---

## Layer 3 — Derived economics (each number names its supports)

- Fishing value retained: sell once/day = 1.0; don't sell for a week = 0.778 (`model.py`,
  rests on 10 %/day decay + 10 % floor).
- Casts/h: theoretical 20; real **3.16** without retry, **12.87** with 30 s retry, **19.1**
  with 10 s retry (`budget.py`, rests on p=0.158). The earlier "3.16" and a "180 s cooldown"
  are both **refuted** — cast rate is unsettled until re-measured live.
- Business: optimal collection cadence **T\* = C / r** (`model.py`), 6.3 attempts per
  successful collect (rests on p). Passive idle income with laundering.
- Casino: **expectation not computable offline** (server-side odds). Most valuable capture =
  `/api/games/info` then `/api/rakeback` (`extract_games.py`).
- Chest: 0 occurrences in 1270 (`analyze_chat.py`); chest-capture probability is indeterminate,
  governed by Kick write reliability, not by the game.

---

## Layer 4 — The target, and why the analysis loops back to Layer 0

- Leaderboard: rank 1 = **792,841** credits, rank 2 = 362,064, rank 3 = 211,700
  (`/api/leaderboard`).
- Net rate to catch rank 1: **26,428 credits/day** in 30 days, **8,809/day** in 90 days
  (`infer.py`).
- Confrontation: fishing at full availability (~19 casts/h × 210.5 ≈ 4,000 credits/h) clears
  the 90-day pace easily. At p=0.158 it does not.

**The loop closes**: strategy (Layer 4) depends on economics (Layer 3), which depend on
mechanics (Layer 2), which all inherit p (Layer 1), fixed by backend health (Layer 0).
Optimizing anything above Layer 0 while the site is sick yields zero. **The only variable that
moves today's outcome is availability**, and it is not under our client-side control.

---

## Layer 5 — Operational recursion (how the analysis regenerates itself)

The analysis above is not a one-shot; it is a fixed point the daily cycle recomputes. Each day:

1. **Probe Layer 0**: one spaced GET, 60 s timeout. Does the site answer? That is the gate.
2. **If yes**: capture through the shared client, in value order — `/api/games/info`,
   `/api/rakeback`, `/api/business` — and re-sample catch value (kill the n=2). Feed
   `facts.jsonl`, let the derivations (Layers 3-4) recompute.
3. **If no**: advance one uncovered mechanic offline (order: business, then predictions, then
   crime) from the `raw/` captures.
4. **Diff** `facts.jsonl` vs yesterday → the day's report states only the **delta**, not a
   re-dump. That is what "organic" means.
5. **Discipline**: never retry into a 429; one probe, read, stop. Availability is measured by
   patience, not pressure. Any burst reproduces the Layer 0 wall.

Fixed point: when two consecutive days change no `measured` fact, the analysis has converged
for the current site state, and the cycle drops to a long sleep until availability changes.

---

## What stays `assumed` (the debt, 109 facts)

Most of it can only be paid against a live site: real casino odds, per-game EV, robust catch
value, real business yield, prediction behavior, rakeback rate. While Layer 0 is down this debt
is frozen, and it is correct to say so rather than disguise it as derivations.
