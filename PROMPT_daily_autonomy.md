# Daily autonomy — full cycle

Run one complete cycle toward rank 1 on shoovy.wtf, unattended, zero interaction, then stop.
Self-contained; also runs on demand. Paths are relative to this repo root.

## Absolute rules
- Never ask anything; on ambiguity take the safest default and note it in the report.
- Never login or enter credentials. A step needing fresh account cookies is recorded as
  "needs operator" and skipped.
- Never retry into a 429/502. All requests go through `client/` (`shoovyclient` / `shoovyreq`),
  which paces, backs off, and logs. One request, read, stop. Requests spaced ≥3 s.
- English output; every number cites its source. Derive with code over saved bodies, never dump
  raw JSON into context.

## Environment
- The availability sentinel runs on a RISC-V board and appends `avail.jsonl`. Read it over ssh
  (host + key from your local config) rather than probing the site yourself — that is the Layer-0
  gate at zero request cost. If the sentinel process is dead, restart its `S99` init script.
- shoovy API (plain Go/stdlib client is fine): public — `/api/stocks`, `/api/fishing`,
  `/api/games/info` (casino odds), `/api/leaderboard`, `/api/stats`. Session-gated — `/api/me`,
  `/api/rakeback`, `/api/business`, trades, chat commands.

## Cycle
1. AVAILABILITY: read the sentinel's `avail.jsonl`; determine up/down and recent uptime. No site
   request for this step.
2. IF UP: via `shoovyreq`, capture once each into `data/study/live/<today>/`: `games_info`,
   `leaderboard`, `fishing` (and, only with a valid session, `/api/me`, `/api/rakeback`,
   `/api/business`). Skip anything that 429s; the client is now in backoff.
3. ANALYSE (always, offline): compute casino EV per game from the latest `games_info` odds; flag
   positive-EV games or where rakeback covers the edge. Re-sample fishing catch value. Diff the
   fact store vs yesterday.
4. REPORT: write `reports/<today>.md` as an organic delta (verdict, site status, what changed,
   today's advance, next step). Update `reports/RANK1_status.md` (target = leaderboard rank-1
   balance; blocker state). Match the sourced, layered voice of `reports/ANALYSE_complete_recursive.md`.
5. FARMING GATE: if `accounts.json` has valid worker sessions, run the farmer per `README.md`
   (fisher/econ, anti-spam guards) and report credits accumulated. If absent/expired (current
   state), record farming as blocked pending operator cookies and continue.
6. CONVERGENCE: two consecutive days with no changed measured fact and unchanged site state →
   say it converged, keep the run short.

## Done
Print: report path, a two-line delta, current availability, current rank-1 target, farming
blocked yes/no. Do not loop; the scheduler re-runs tomorrow, and it is triggerable on demand.
