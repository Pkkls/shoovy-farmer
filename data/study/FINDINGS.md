# Market study — field notes

Working notes for the question "what would it actually take to reach rank 1 on
the leaderboard". Everything here is dated and sourced. Numbers that were not
measured in this session are marked as inherited and must be re-verified before
anyone builds on them.

Raw material lives next to this file:

| file | what it is |
|---|---|
| `client.py` | the one HTTP client every request goes through. Serialises calls behind a global gap, logs request and full response body |
| `requests.jsonl` | the audit trail: one line per request, with response body |
| `harvest.py` | one spaced pass over every endpoint the site serves without a session, saving raw bytes to `raw/` |
| `availability.py` | samples one endpoint on a fixed cadence to characterise what the site is doing |
| `raw/` | untouched response bodies, so analysis costs zero further requests |

## Status: blocked, and probably not by us

As of 2026-08-19 ~20:30 local (18:30 UTC) the site does not serve us anything.
That is the single most important fact in this document, and it is not yet a
finding about the game economy.

What was actually observed, in order:

| local time | what | result |
|---|---|---|
| ~17:05 | first contact, `/api/stocks` | HTTP 502, 41.3 s |
| ~17:08 | retry, root and API | HTTP 200. Cold start confirmed: 41.3 s → 5.7 s → 0.2 s |
| ~17:08–17:15 | ~20 reconnaissance requests, unspaced | HTTP 200, then HTTP 429 `rate limited` |
| ~17:15–18:15 | spaced retries, one every few minutes | HTTP 429 throughout |
| 18:23 UTC | page loaded in a real browser | **HTTP 502 Bad gateway (Cloudflare): origin not responding** |
| 20:26–20:28 | 4 samples, 30 s apart, logged client | HTTP 429, 4/4 |

### The ban hypothesis does not survive the evidence

The first reading was "the recon burst got the IP rate-limited". That reading is
not supported:

- A real browser, different client, different TLS fingerprint, no shared cookie
  jar with the scripts, gets **502 Bad gateway** from Cloudflare. Cloudflare
  returns 502 when the origin itself fails to answer, which is a statement about
  the site, not about the caller.
- Replaying the `device` cookie the site itself issued changed nothing.
- The 429 body is 12 bytes of `text/plain` reading `rate limited`, carrying
  `x-railway-edge` and no `Retry-After`, no `X-RateLimit-*`. It is emitted at the
  Railway edge, not by Cloudflare's bot layer and not visibly by game logic.

The more parsimonious explanation is that the shoovy.wtf deployment is unhealthy
or throttled at the platform level, and 429/502 are two faces of the same
degradation. Under that reading nothing we do from here fixes it.

This is deliberately stated as the better-supported hypothesis, not as proof.
Discriminating test, when the site recovers: check whether a fresh burst
reproduces a 429 that then clears on a predictable timer. A limiter aimed at
callers behaves like a timer; a sick backend does not.

Either way the operational conclusion is the same and it is worth keeping:
**treat request budget as the scarce resource.** See below.

## Infrastructure

- Cloudflare in front of Railway (`Server: cloudflare`, `CF-RAY`,
  `x-railway-edge: cdg1`). An earlier note claiming there was no Cloudflare is
  now wrong.
- A plain Go/stdlib client is not filtered: `User-Agent: Go-http-client/1.1`
  returned HTTP 200 while the site was healthy. No TLS-impersonating client is
  needed for shoovy.wtf itself.
- Cold start after idle is roughly 40 s. Any client with a short timeout fails on
  first contact after a quiet period. Use 60 s.

## Why request budget is the design constraint

Whatever the cause of the 429, the existing bot design cannot survive contact
with any limiter at all. The trader polls every 15 s (240 requests/hour on its
own), the collector and the dashboard poll independently on top. Three
processes, three independent request streams, no shared budget.

That design ran without trouble in July. Something changed since. Either a
limiter was introduced, or the deployment became less tolerant. Both point the
same way: one shared client with one global budget, not one poller per bot.
`client.py` is that serialisation point; its fixed gap becomes a real token
bucket once the limiter's window can be measured.

## API surface

Mapped from the pages' own markup while the site was up, so this is what the
client calls, not a guess. Pages: `/fishing /stocks /casino /games /crime
/business /shop /raffles /stats /updates /commands /admin`.

| area | endpoints |
|---|---|
| fishing | `/api/fishing` + `/gear` `/net/` `/cook` `/sell` `/prestige` |
| business | `/api/business` + `/buy` `/collect` `/improve` `/launder` `/sell` `/slot` |
| crime | `/api/crime` + `/gear` |
| casino | `/api/casino/lobby`, `/api/games/info`, blackjack, crash, mines, dragon, plinko, keno, slots, wheel, coinflip, rps, cases, `/api/rakeback` + `/claim` |
| market | `/api/stocks` + `/history` `/trade`, `/api/predictions` + `/bet` `/lock` `/resolve` |
| economy | `/api/daily`, `/api/leaderboard`, `/api/leaderboards`, `/api/stats`, `/api/user`, `/api/feed` |
| rewards | `/api/shop` + `/redeem`, `/api/raffles` + `/buy` |
| meta | `/api/updates`, `/api/suggestions`, `/api/tts`, `/api/shocker/fire` |

`GET /api/fishing` answers without a session: species list, rarities, and a decay
block (10 %/day, 24 h fresh window, 10 % floor). `GET /api/stocks`,
`/api/leaderboard` and `/api/updates` are also public.

## What changed since the July baseline

The bots in this repository cover three mechanics. The site now runs roughly
twelve. Specifically:

- Fishing gained gear, nets, cooking, selling and a prestige track. A bare cast
  is now a fraction of the mechanic. Perishable stock (10 %/day decay) means the
  question is sell *cadence*, not sell *or not*.
- Business is an idle earner. `collect` is one call for accumulated income, which
  makes it the natural candidate for best credits-per-request. Unverified.
- Crime, raffles, a rewards shop and a full casino did not exist in the covered
  set.
- Stocks look unchanged in shape (5 tickers, AMM depth 250000, 1 % fee, 8 s trade
  cooldown) and gained `/api/stocks/history`, which makes backtesting possible
  without live trades.
- The default channel in `/api/me` is now `shoovy`, and the leaderboard exposes
  `stake` and `fish_prestige`. The site reads as multi-channel now.

### Inherited numbers, all pending re-verification

From the July code and configs, not re-measured: daily 200 credits per 20 h;
fishing state exposed as `enabled` / `remaining` / `cooldown_min`; stocks 8 s
server cooldown, 1 % fee, depth 250000; trader tuned to MA20, −3 % entry,
−0.5 % exit, 360 s max hold, 150 credits per position, 6 positions, `live:
false`.

One structural detail from that code matters: the July fisher **read** state from
`GET /api/fishing` but **acted** by posting `!fish` into Kick chat. If a POST API
had existed it would have used it. The presence of `/api/fishing/cook`, `/sell`,
`/gear` and `/prestige` today suggests actions moved to the API, which would
remove the entire Kick dependency. That is the highest-value open question and it
needs one authenticated call to settle.

## Leaderboard snapshot

Taken 2026-08-19 while the site was up. A snapshot, not a trend: the target is a
rate, and deriving it needs samples across days.

| rank | balance |
|---|---|
| 1 | 792 841 |
| 2 | 362 064 |
| 3 | 211 700 |
| 4 | 169 956 |
| 5 | 145 826 |

## Open questions

1. Is the 429 a limiter aimed at callers, or platform degradation? Discriminating
   test described above.
2. Do actions work through the API with only the site session cookie, or is Kick
   chat still required?
3. Real cooldowns and daily caps per mechanic.
4. Credits per hour **and** credits per request, per mechanic.
5. Casino: measured house edge versus measured rakeback. Excluded from any plan
   unless rakeback demonstrably exceeds the edge.
6. Is the existing mean-reversion strategy still positive expectancy on current
   `/api/stocks/history` data?

## Ground rules for this study

- Unmeasured is labelled unmeasured. No filled-in estimates.
- A negative result must show its measurement, not its assumption.
- Sample size and variance stated for anything random.
- `/api/shop/redeem` and `/api/raffles/buy` convert credits into real-world
  value. They get modelled, never called.
- Probe slowly. A banned account earns zero forever, which dominates any
  short-term gain.
