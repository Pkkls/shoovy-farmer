# Scan the whole API and solve for the optimal path to rank 1

Two jobs: (1) map the ENTIRE shoovy.wtf API surface, including endpoints not yet documented,
and (2) from every mechanic's economics, solve for the credit-maximizing path to rank 1. This is
an optimization, not just a survey. Full read access is assumed; the streamer is a parameter.

## The one guardrail that survives "everything is accessible"
Reading and modeling everything is fine. **Executing real-world-effect or mutating actions is
not**, because shoovy runs on a real person's live stream and the economy is shared:
- NEVER call `/api/tts` or `/api/shocker/fire` — they act on the actual broadcast.
- NEVER POST/DELETE an economy action (`/buy /collect /trade /bet /claim /redeem /raffles/buy
  /sell /launder /prestige /cook`) except through the explicit farming gate with real sessions.
- The optimal path is DERIVED from the economics you read, not discovered by firing actions.
Everything else — every GET, every method-surface probe — is open.

## Discipline (the backend flaps; respect it)
- Availability is a duty cycle (~0.76 up in the last window, down-windows ~5-6 min, cold starts
  to 30 s). Read the Claw sentinel's `avail.jsonl` first; scan only during an up-window; if it
  drops mid-scan, the shared client backs off — let it, do not hammer.
- All requests through the one client: `apimap` (`client/cmd/apimap`) or `shoovyreq` /
  `shoovyclient`. Paced ≥3 s, exponential backoff on 429/502, never retries a single call, logs
  every request. Because requests are the scarce resource, **credits-per-request matters as much
  as credits-per-hour** — carry both through the whole analysis.
- English, every number sourced, token-economical (derive with code over saved bodies).

## Phase 1 — exhaustive discovery (find everything, not just the known list)
1. The known map (probe all, GET): economy `/api/me /stats /leaderboard /leaderboards /user
   /feed /daily`; fishing `/api/fishing`; market `/api/stocks /stocks/history /predictions`;
   casino `/api/games/info /casino/lobby /rakeback`; business `/api/business`; crime `/api/crime`;
   rewards `/api/shop /raffles`; meta `/api/updates /suggestions`.
2. Undocumented endpoints: fetch the live JS bundles (their URLs are in the page HTML / already
   in `data/study/raw/static_nav.js.txt`, `index.txt`) and extract every `"/api/..."` string and
   every `fetch(`/`axios.` call target. Diff against the known map; probe the new GET ones.
3. Method surface for each: a harmless `PUT` returns `405` listing real methods — enumerate
   POST/DELETE existence WITHOUT invoking them.
Save every raw body to `data/study/raw/api_<name>.json`; record access (200/401/404/429),
top-level keys, the `channel` field, and session dependence.

## Phase 2 — economic model of every mechanic
For each earning/spending surface, extract or derive the yield function and record it as facts:
- **fishing**: credits per catch, cooldown, decay, sell cadence → credits/hour, credits/request.
- **daily**: fixed amount, 24 h cooldown → credits/day, 1 request.
- **business**: passive rate r, collect cost/cap C, optimal cadence T*=C/r → credits/hour,
  credits/request (collect is periodic, cheap in requests).
- **stocks**: 1 % fee, AMM depth 250k → near break-even; model realistic edge, if any.
- **predictions**: payout structure, resolution → EV; is it +EV or house-skewed?
- **casino**: EV per game from `/api/games/info` odds (already: every game negative, best plinko
  11/high −0.84 %, rakeback 0.5 % leaves −0.34 % net). Confirm/extend; treat as a sink.
- **tips**: fee (0 % observed), the funnel to the main account.
Each fact: subject `mechanic:<x>`, predicate (`credits_per_hour`, `credits_per_request`, `ev`,
`cooldown`, `cap`), value, status measured/derived, source.

## Phase 3 — solve the optimal path
Objective: reach the leaderboard rank-1 balance (currently ~886,890, read it fresh) in the
fewest days, subject to: the availability duty cycle, per-account cooldowns, N worker accounts
funneling to one main via tips, and the request budget (up-windows are finite).
Produce:
1. A ranked table of mechanics by **credits/hour** AND by **credits/request** (the second ranking
   is the one that matters when the backend is flapping — spend scarce up-window requests on the
   highest credits/request actions first).
2. The **optimal action sequence per account per up-window**: e.g. "on wake, if up: claim daily
   (1 req, high value), cast fish (cooldown-bound), collect business if T* elapsed; skip casino
   entirely (negative EV); tip surplus to main every 36 h." Justify each inclusion/exclusion by
   its credits/request and EV.
3. The **rate estimate**: credits/day per account at the measured duty cycle, ×N accounts, and
   the resulting days-to-rank-1. Compare to the naive full-availability estimate to show what the
   flapping costs.
4. **What would move the needle most**: more accounts, higher duty cycle (out of our control),
   or a higher-yield mechanic we under-weight. Name the single highest-leverage change.

## Output
- `reports/optimal-path-<today>.md`: the full surface table, the economic model, the ranked
  mechanics, the optimal per-window sequence, and the days-to-rank-1 estimate. Sourced, in the
  layered voice of `reports/ANALYSE_complete_recursive.md`.
- Append all mechanic-economics facts to `data/study/facts.jsonl`.
- Print: endpoints found (known + new), the top-3 mechanics by credits/request, and the single
  highest-leverage change.

Farming itself stays gated on real sessions (a human login this prompt will not do); the optimal
path is the plan the farmer executes once sessions exist.
