# "Rank 1" is five games — pick the cheapest route

Recursive API testing (each read called 2x for reproducibility) revealed `/api/leaderboards`
(plural) exposes FIVE separate boards. "Rank 1" is not one target. Thresholds captured live:

| board | metric | #1 value | rank-5 value | route |
|---|---|---|---|---|
| richest | balance | 992,397 | 101,026 | the business engine (raw balance) |
| traders | stock profit | 788,244 | 89,669 | **the stock-oracle edge** (front-run the metric tickers) |
| portfolios | portfolio value | **330,316** | 101,144 | hold stock, capital from business |
| gamblers | casino profit | 222,771 | 75,272 | **TRAP** — casino is negative-EV, topping this is luck not strategy |
| criminals | stolen (via !rob) | dlepp #1 | — | crime volume (rob other players); needs the crime sub-game |

## Route analysis
- **gamblers looks cheapest (222k) but is a trap.** It ranks casino *profit*; every casino game is
  negative-EV (best plinko 11/high −0.84 %), so sustained profit is variance, not a repeatable
  plan. Do not chase it.
- **traders (788k profit) is exactly what the stock-oracle edge produces.** The tickers are
  game-metric indices whose drivers are observable seconds before the ~32 s price tick
  (see `edge-stock-oracle`). Front-running them generates trading profit → this board, and builds
  holdings → the portfolios board.
- **portfolios (330k value) is the lowest reliable bar.** It only asks you to *hold* 330k of stock.
  Fund it with the business engine, park it in the least-volatile ticker, and you top it without
  the 992k of richest.
- **richest (992k) is the business engine** — the Meth-Lab / manager compounding from
  `optimal-path`. The hardest number but the most deterministic.

## Recommendation
Two real edges exist, each winning a different board:
1. **Business engine → richest** (deterministic, capital-bound, ~992k).
2. **Stock oracle → traders + portfolios** (skill/edge-bound; portfolios at 330k is the fastest
   plausible "rank 1" of any board).
Chase portfolios or traders first via the oracle; keep the business engine compounding toward
richest in parallel. Ignore gamblers.

## Test-harness findings (each read called twice)
- **All reads are reproducible**: every base endpoint returned identical bodies across both calls
  (`consistent: true`), so the API is deterministic for reads — safe to cache and model.
- **The Cloudflare gate rate-limits even the browser**: after ~25 rapid in-page calls the session
  started returning 429. So the harness and the farmer must **pace even in-browser** — the browser
  clears the bot challenge but not an unlimited request rate.
- **New/confirmed endpoints**: `/api/leaderboards` (5 boards), `/api/crime` (full defense
  catalog), `/api/stats` (401 gated), `/api/daily` and `/api/suggestions` (405, POST-only),
  `/api/user` needs a valid id (404 otherwise).

## Standing blocker
Every write (buy/collect/trade/bet/rob/claim) needs a session (operator login). The routes and the
edges are mapped; execution waits on `accounts.json`.
