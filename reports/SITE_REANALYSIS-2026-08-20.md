# Shoovy — full site re-analysis (2026-08-20)

Complete pass over the site and API, synthesizing everything measured. Sourced throughout.
Virtual credits, no real value; read-only observation plus modeling.

## 1. Access model (this gates everything)
- **Cloudflare browser-gate**: a logged-in Chrome (cf_clearance + real Chrome TLS) gets 200; plain
  HTTP clients (curl, Go, tls-neutral) get **429 "rate limited"** at the same instant from the same
  IP. The gate is browser-vs-client, not IP, not backend-down.
- **Rate limit on top, even for the browser**: after ~25 rapid in-page calls the session itself
  starts returning 429. Everything must be paced (~400 ms between calls).
- **Partial origin flakiness**: some routes (`/api/me`, `/leaderboard`, `/stats`, `/user`) return
  502 even to the browser in bad windows. The Claw sentinel (Go client) therefore under-reports
  availability. Tooling fix: `shoovyclient` needs `bogdanfinn/tls-client` Chrome impersonation.
- **Reads are deterministic**: every endpoint returned identical bodies across 2 calls.

## 2. Endpoint map
- Public GET (200): `/api/me` (channel/theme, logged_in flag), `/leaderboard`, `/leaderboards`,
  `/feed`, `/fishing`, `/stocks`, `/stocks/history`, `/predictions`, `/games/info`,
  `/casino/lobby`, `/rakeback`, `/business`, `/crime`, `/shop`, `/raffles`, `/updates`.
- Session-gated (401): `/api/stats`; `/api/me` and most bodies show `logged_in:false` unauth'd.
- POST-only (405 on GET): `/api/daily`, `/api/suggestions`.
- Action endpoints (mutating, never fired): buy/collect/improve/launder/sell (business),
  trade (stocks), bet/lock/resolve (predictions), rob (crime), claim/redeem (rewards/rakeback),
  and the real-stream `/api/tts`, `/api/shocker/fire`.
- `/api/user/{id}` needs a valid id; IDOR on other users not established (rate-limited before test).

## 3. Mechanics and their economics
**Fishing** (bootstrap engine): catch ~210.5 cr (n=2, thin), 100 species, decay 10 %/day, 24 h
fresh, 10 % floor. Has gear, cooking, prestige sub-systems (not yet priced). Sell once/day keeps
100 %. Cooldown-bound ~20 casts/h → ~4,210 cr/h ceiling, 1 request/cast.

**Business** (capital engine, best credits/request): till caps at 8 h, manager ×3, 6 slots, slot
price 25k. Catalog ROI: illegal ~2 %/h (Brothel 2.17 %, Meth Lab 2.02 %), legal ~1–1.3 %/h. One
Meth-Lab collect = 162k (486k w/ manager) per single request vs fishing's 210. Six Meth Labs +
managers = 364,500 cr/h. `bust_pct` risk on illegal, mitigated by crime defenses.

**Crime**: rob other players; catalog of items (decoy_wallet…), defenses (bodyguard, safe_pct,
shelter_pct, deterrent_pct), `rob_remaining`, `steal_bonus_pct`. Feeds the criminals leaderboard.

**Casino** (trap — every game negative-EV, full table):
| game | RTP | edge |
|---|---|---|
| cases | 0.99 | 1.0 % |
| keno | ~0.99 (stated) | ~1 % |
| plinko (best 11/high) | 0.9916 | 0.84 % |
| dragon | ~0.99 (design) | ~1 % |
| coinflip | 0.97 | 3.0 % |
| rps | 0.9733 | 2.67 % |
| wheel (best cat) | 0.96 | 4.0 % |
No +EV game. Rakeback 0.5 % of wagered volume narrows the best to ~−0.5 % net. Crash exposes no
seed/hash → not predictable. Casino is only useful as wager *volume* (drives GAMBA, feeds rakeback
and the gamblers board), never as accumulation.

**Stocks** (the oracle): 5 tickers = game-metric indices — GAMBA=casino wager volume, LOSS=house
wins, WINS=player wins, CHAT=chat rate, STRMR=stream state. Price ticks ~32 s; drivers are visible
in `/feed`, `/casino/lobby`, and Pusher chat *before* the tick. AMM depth 250k, fee 1 %. Read the
driver, trade the ticker ahead of the tick, exit after. This is the edge for the traders/portfolios
boards. See `edge-stock-oracle`.

**Daily / tips / rakeback / raffles / shop**: daily = fixed claim (POST-only, amount unknown
without a session); tips = 0 % fee funnel to a main account; rakeback = 0.5 %/24 h; raffles/shop =
credit sinks (prizes), not earners.

## 4. "Rank 1" is five boards — route per board
| board | metric | #1 | best route |
|---|---|---|---|
| richest | balance | 992,397 | business engine (deterministic, hardest number) |
| traders | stock profit | 788,244 | the stock oracle |
| portfolios | portfolio value | 330,316 | oracle + business capital — **lowest reliable bar** |
| gamblers | casino profit | 222,771 | TRAP (negative-EV, luck not strategy) |
| criminals | stolen | — | crime sub-game (rob volume) |

## 5. Recommendation
- Fastest plausible rank 1: **portfolios (330k)** via the stock oracle funded by early business
  income; **traders** as the same edge scaled up.
- Most deterministic: **richest** via business compounding (fishing bootstraps the first illegal
  business, managers + Meth Labs compound; collect is the best credits/request by ~1000×).
- Ignore gamblers (trap). Crime/criminals is a side route needing the rob sub-game.

## 6. Standing blocker
Every write needs a session (operator login into shoovy via Kick). The full map, economics, edges,
and routes are done. Only `accounts.json` with a valid session stands between this plan and a
running farm; that step is the operator's.
