# Edge: the stock tickers are oracles you can front-run

A recursive read of the site and API, looking for something usable that a UI-only player cannot
see or understand. The find is in the stock market. These are virtual credits (no real value) and
this is an information-asymmetry edge from read-only observability, not a security exploit.

## Layer 1 — what a normal user sees
Five tickers with prices that go up and down: CHAT, GAMBA, LOSS, STRMR, WINS. The UI shows the
price and a chart. A player buys, hopes it goes up, sells. No stated reason for the moves.

## Layer 2 — what the API reveals that the UI hides
The tickers are not random. They are **indices mechanically tied to game activity**, and the API
says so outright in `/api/stocks` `news` and in the ticker `name` field:

| symbol | name | driven by (from the news headlines) |
|---|---|---|
| GAMBA | Degeneracy Inc. | casino wager volume — "🎰 $GAMBA rallies — 24,362 credits hit the tables" |
| LOSS | L Holdings | the house winning — "💀 $LOSS pumps — the house collects 4,663" |
| WINS | W Corp | players winning — "🏆 $WINS moons — chat takes the house for 2,260" |
| CHAT | Chat Hype Index | chat activity rate |
| STRMR | The Streamer | stream state (live / viewers) |

A UI user never sees this mapping. The name "Degeneracy Inc." and the headline text only exist in
the API payload; the chart doesn't explain *why* it moved.

## Layer 3 — the exploitable asymmetry
The price updates on a **~30–32 s tick** (`/api/stocks/history?symbol=GAMBA` shows dt≈32 s). The
*drivers* of that tick are observable **before** it prints:
- `/api/feed` streams individual events ("won 4,671 credits on Plinko", "bought 10,000 of $CHAT").
- `/api/casino/lobby` gives live per-game play counts.
- the Kick chat is readable from a server via Pusher (established in the Kick work), so the CHAT
  driver (chat rate) is measurable live.
- `/api/me` `live` and the stream state feed STRMR.

So the input to the price function is visible seconds before the function is recomputed. You are
not predicting the market — you are reading the tick's inputs early. Buy the ticker whose driver
just spiked, inside the ~30 s window, and sell after the tick reprices it.

## Layer 4 — why a lambda user can't do this
- The ticker↔metric mapping is API-only; the UI never shows it.
- The driver streams (feed at machine speed, chat via Pusher, casino_lobby counts) are not
  surfaced as "this will move GAMBA"; a human can't watch and correlate them in a 30 s window.
- The AMM is deterministic: depth 250,000, fee 1 %. Price impact of a trade ≈ trade/depth, so a
  bot can size a position to clear the 1 % round-trip fee only when the predicted move is large
  enough. A human can't compute that live. (Exact AMM curve — constant-product vs linear — is
  still to confirm; the depth and fee are measured.)

## The bot, in one paragraph
Poll `/api/feed` + `casino_lobby` + the Pusher chat every few seconds. Maintain a running estimate
of each ticker's driver since the last price tick. When a driver's accumulated delta implies a
price move exceeding the 1 % fee, take the position on that ticker before the next tick, then exit
after the tick prints. This is pure read-then-trade on public-but-unsurfaced data; it needs a
session to place trades (the standing farming-gate blocker), but the signal is free and live now.

## Checked negatives (not edges)
- **Crash is not predictable from exposed data.** `crash_history` shows past multipliers/results
  per user but no `seed`/`hash`/`nonce`/`server_seed` anywhere in `games_info` — no provably-fair
  seed leak to precompute the next crash point.
- **Casino games have no +EV surface** (established earlier: every game negative, best plinko
  11/high −0.84 %, rakeback leaves −0.34 %). The edge is the stock oracle, not the casino.

## Next to firm this up (needs a live up-window + a session)
1. Measure the exact lag: timestamp a driver event in the feed vs the price tick that reflects it.
2. Reverse the AMM curve from `depth` + observed price moves per known volume.
3. Confirm each ticker's driver quantitatively (correlate casino_lobby delta → GAMBA move).
