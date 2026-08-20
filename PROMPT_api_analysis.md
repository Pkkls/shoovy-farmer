# Shoovy API surface analysis

Map and characterize the whole shoovy.wtf API surface: which endpoints exist, whether they are
public or session-gated, their response shape, the economy numbers they carry, and their method
surface. Feed the typed fact store. Runs safely unattended.

## Absolute rules (read twice)
- **Read only. Never invoke an action.** Many paths mutate or trigger real-world effects. NEVER
  POST/DELETE to: `/buy /collect /improve /launder /sell /slot` (business), `/trade` (stocks),
  `/bet /lock /resolve` (predictions), `/claim /redeem` (rewards, rakeback), `/raffles/buy`,
  and especially `/api/tts` and `/api/shocker/fire` (these do things in the real stream). If in
  doubt, GET only.
- All requests go through the disciplined client, never raw curl in a loop: `shoovyreq`
  (`shoovyreq.exe` on PC, `shoovyreq-riscv64` on the board) or the `shoovyclient` package. It
  paces (≥3 s), backs off on 429/502, **never retries a single call**, and logs every request.
- Check availability first from the Claw sentinel's `avail.jsonl` (over ssh), not by probing the
  site. If it is in a down window, stop and try later — do not hammer a sick backend.
- Streamer is a parameter, never hardcoded. Default channel if none given; scope with the
  mechanism `PROMPT_streamer_analysis.md` discovers.
- English output; every number cites its source. Token-economical: derive with code over the
  saved bodies, never dump raw JSON into context.

## The known surface (probe the GET/info endpoints; do not act on the rest)
Save each raw body to `data/study/raw/api_<name>.json`.

- economy: `GET /api/me`, `/api/stats`, `/api/leaderboard`, `/api/leaderboards`, `/api/user`,
  `/api/feed`, `/api/daily` (GET only — do not claim)
- fishing: `GET /api/fishing` (public: species, decay). `/gear /net /cook /sell /prestige` are actions — skip.
- market: `GET /api/stocks`, `/api/stocks/history?symbol=X&minutes=N`. `/trade` is an action — skip.
- predictions: `GET /api/predictions`. `/bet /lock /resolve` are actions — skip.
- casino: `GET /api/games/info` (odds), `/api/casino/lobby`, `/api/rakeback` (rate, GET only — do not claim).
  Per-game info if a GET form exists; the play calls are actions — skip.
- business: `GET /api/business` (structure). action sub-paths — skip.
- crime: `GET /api/crime`. `/gear` — skip if it acts.
- rewards: `GET /api/shop`, `/api/raffles`. `/redeem /buy` — skip.
- meta: `GET /api/updates`, `/api/suggestions`. **Never** touch `/api/tts`, `/api/shocker/fire`.

For any endpoint not in this list that the frontend references (grep `data/study/raw/static_nav.js.txt`
and `index.txt` for `/api/`), add it as GET-only unless the name implies an action.

## Per endpoint, record
1. **Access**: 200 (public), 401 (session-gated), 404 (gone/renamed), 429/502 (backend down).
2. **Shape**: top-level keys, and any nested `channel` field (multi-channel scoping).
3. **Economy content**: does it carry numbers that feed the model — balances, rates, fees,
   payouts/odds (rtp/multiplier), cooldowns, decay, leaderboard targets? Extract them.
4. **Method surface** (safe probe only): a `PUT` returns `405` listing supported methods, which
   reveals whether POST/DELETE exist **without invoking them**. Use PUT (harmless) to enumerate;
   never send the POST/DELETE it lists. Record e.g. "POST, DELETE supported".
5. **Session dependence**: note which need `shoovy_session` (401 without it).

## Output
- Append facts to `data/study/facts.jsonl` (typed: subject `api:<name>`, predicate, value,
  status measured/derived, source). One line per finding.
- Write `reports/api-surface-<today>.md`: a table of endpoints × access × shape × economy value,
  the public-vs-gated split, and which endpoints are the highest-value captures for the rank-1
  model. Flag any endpoint whose behavior contradicts prior notes (candidate for kick-api-notes
  style correction). Match the sourced voice of `reports/ANALYSE_complete_recursive.md`.
- Print: endpoints probed, public/gated counts, and the single most valuable new finding.

Do not loop; this is one analysis pass, re-runnable on demand.
