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

This paragraph originally concluded "treat request budget as the scarce
resource". That was wrong and is superseded: the scarce resource is
**availability**, and pacing buys none of it. See the availability section below.

<!-- FACTS:BEGIN -->

## State of knowledge

*Generated from `facts.jsonl` by `render.py`. 58 facts, 59 records with history. Do not hand-edit this section.*

| status | count |
|---|---|
| measured | 20 |
| derived | 15 |
| candidate | 1 |
| assumed | 19 |
| refuted | 3 |

### measured (20)

Observed on the wire by this study.

| subject | fact | value | n | source |
|---|---|---|---|---|
| `command:!fish` | part_des_commandes_observees | 0.84 fraction | 25 | chat.jsonl |
| `infra:availability` | serie_utilisable_max | 2 requetes | 19 | uptime.py |
| `infra:availability` | taux_reponses_utilisables | 0.158 fraction | 19 | uptime.py |
| `infra:kick` | debit_du_chat | 19.2 msg/min | 368 | chat.jsonl |
| `infra:kick` | chat_lisible_depuis_un_serveur | True |  | pusher_probe.py |
| `infra:kick` | chatroom_id | 29834074 |  | kick.com/api/v2 |
| `infra:kick` | follow_minimum_avant_de_poster | 6 min |  | kick.com/api/v2 |
| `infra:kick` | slow_mode_interval | 1 s |  | kick.com/api/v2 |
| `infra:leaderboard` | solde_rang_1 | 792841 credits |  | /api/leaderboard |
| `infra:leaderboard` | solde_rang_2 | 362064 credits |  | /api/leaderboard |
| `infra:leaderboard` | solde_rang_3 | 211700 credits |  | /api/leaderboard |
| `infra:leaderboard` | solde_rang_4 | 169956 credits |  | /api/leaderboard |
| `infra:leaderboard` | solde_rang_5 | 145826 credits |  | /api/leaderboard |
| `infra:shoovy.wtf` | forme_du_429 | text/plain 12 octets 'rate limited', x-railway-edge, sans Retry-After ni X-RateLimit-* |  | requests.jsonl |
| `infra:shoovy.wtf` | fronting | cloudflare devant railway |  | requests.jsonl |
| `infra:shoovy.wtf` | cold_start | 40 s | 3 | requests.jsonl |
| `infra:shoovy.wtf` | accepte_client_stdlib | True |  | requests.jsonl |
| `mechanic:fishing` | decay | 0.1 fraction/jour |  | /api/fishing |
| `mechanic:fishing` | plancher_de_valeur | 0.1 fraction |  | /api/fishing |
| `mechanic:fishing` | fenetre_fraiche | 24 h |  | /api/fishing |

### derived (15)

Computed from other facts. Each names what it rests on.

| subject | fact | value | n | source |
|---|---|---|---|---|
| `event:chest` | probabilite_de_capter_un_chest | indeterminee, gouvernee par la fiabilite d'ecriture Kick |  | infer.py |
| `infra:availability` | probabilite_qu_un_appel_aboutisse | 0.158 fraction |  | infer.py |
| `infra:availability` | probabilite_qu_un_enchainement_de_2_appels_aboutisse | 0.025 fraction |  | infer.py |
| `infra:availability` | probabilite_qu_un_enchainement_de_3_appels_aboutisse | 0.0039 fraction |  | infer.py |
| `infra:leaderboard` | debit_net_requis_pour_rattraper_en_30_jours | 26428.0 credits/jour |  | infer.py |
| `infra:leaderboard` | debit_net_requis_pour_rattraper_en_90_jours | 8809.3 credits/jour |  | infer.py |
| `mechanic:business` | tentatives_par_collecte_reussie | 6.3 appels |  | infer.py |
| `mechanic:business` | rang_d_achat_du_manager | premier achat rentable |  | infer.py |
| `mechanic:business` | division_du_cout_en_requetes_par_manager | 3 |  | model.py |
| `mechanic:business` | cadence_de_collecte_optimale | T* = C / r |  | model.py |
| `mechanic:fishing` | lancers_par_heure_reels | 3.16 casts/h |  | infer.py |
| `mechanic:fishing` | lancers_par_heure_theoriques | 20.0 casts/h |  | infer.py |
| `mechanic:fishing` | valeur_conservee_en_vendant_une_fois_par_jour | 1.0 fraction |  | model.py |
| `mechanic:fishing` | part_des_appels_consacree_a_la_vente | 0.0021 fraction |  | infer.py |
| `mechanic:fishing` | valeur_conservee_apres_une_semaine | 0.778 fraction |  | model.py |

### candidate (1)

A reading that fits, with the thing that would break it named.

| subject | fact | value | n | source |
|---|---|---|---|---|
| `mechanic:fishing` | cooldown | 180 s | 2 | chat.jsonl |

- `fishing.cooldown_seconds` breaks if: le site etait indisponible pendant toute la fenetre: une commande sans effet ne demarre aucun timer, donc la regularite peut etre l'habitude du joueur et non le cooldown du jeu

### assumed (19)

Asserted by the site's own docs, or inherited from July. Never watched happen. Treat as suspect.

| subject | fact | value | n | source |
|---|---|---|---|---|
| `event:chest` | fenetre_de_reponse | 30 s |  | raw/commands.txt |
| `mechanic:business` | taux_plein_seulement_en_live | True |  | raw/commands.txt |
| `mechanic:business` | multiplicateur_capacite_manager | 3 |  | raw/commands.txt |
| `mechanic:business` | reduction_max_odds_de_raid_par_payoff | 0.75 fraction |  | raw/commands.txt |
| `mechanic:business` | till_sature | True |  | raw/commands.txt |
| `mechanic:chat_income` | periode_de_gain | 60 s |  | raw/commands.txt |
| `mechanic:daily` | montant | 200 credits |  | configs de juillet du repo |
| `mechanic:daily` | periode | 20 h |  | configs de juillet du repo |
| `mechanic:fishing` | recette_bait | 3 communs |  | raw/commands.txt |
| `mechanic:fishing` | recette_lure | 5 uncommons |  | raw/commands.txt |
| `mechanic:fishing` | especes_requises_pour_prestige | 100 especes |  | raw/commands.txt |
| `mechanic:stocks` | profondeur_amm | 250000 credits |  | configs de juillet du repo |
| `mechanic:stocks` | frais | 1 % |  | configs de juillet du repo |
| `mechanic:stocks` | nombre_de_tickers | 5 |  | configs de juillet du repo |
| `mechanic:stocks` | cooldown_entre_trades | 8 s |  | configs de juillet du repo |
| `mechanic:stocks` | seuil_entree | -0.03 fraction |  | configs de juillet du repo |
| `mechanic:stocks` | seuil_sortie | -0.005 fraction |  | configs de juillet du repo |
| `mechanic:stocks` | fenetre_moyenne_mobile | 20 points |  | configs de juillet du repo |
| `mechanic:treasure` | fouilles_gratuites | 1 par jour |  | raw/commands.txt |

### refuted (3)

Believed, then disproved. Kept because the reversals are data.

| subject | fact | value | n | source |
|---|---|---|---|---|
| `infra:availability` | debit_du_chat_proxy_de_sante_backend | False | 368 | chat.jsonl |
| `infra:kick` | chat_ferme_aux_serveurs | False |  | pusher_probe.py |
| `infra:shoovy.wtf` | ip_bannie_par_nos_sondes | False |  | FINDINGS.md |

### What rests on what

A fact moving to `refuted` invalidates everything below it.

| fact | rests on |
|---|---|
| `business.attempts_per_successful_collect` | `infra.call_success_probability`, `business.optimal_period` |
| `business.manager_priority` | `business.manager_request_divisor`, `business.attempts_per_successful_collect` |
| `business.manager_request_divisor` | `business.optimal_period`, `business.manager_capacity_multiplier` |
| `business.optimal_period` | `business.till_stops_when_full` |
| `event.chest_capture_probability` | `chat.pusher_route_works`, `chest.response_window` |
| `fishing.casts_per_hour_effective` | `fishing.casts_per_hour_nominal`, `infra.call_success_probability` |
| `fishing.casts_per_hour_nominal` | `fishing.cooldown_seconds` |
| `fishing.daily_sell_lossless` | `fishing.decay_per_day`, `fishing.fresh_hours` |
| `fishing.sell_share_of_calls` | `fishing.daily_sell_lossless`, `fishing.casts_per_hour_nominal` |
| `fishing.weekly_retention` | `fishing.decay_per_day`, `fishing.fresh_hours`, `fishing.floor_fraction` |
| `infra.call_success_probability` | `infra.availability.v1` |
| `infra.flow_success_2_steps` | `infra.call_success_probability` |
| `infra.flow_success_3_steps` | `infra.call_success_probability` |
| `target.rate_needed_30d` | `leaderboard.rank1` |
| `target.rate_needed_90d` | `leaderboard.rank1` |

*Rendered 2026-08-19 21:21.*

<!-- FACTS:END -->

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

## Game mechanics, from the site's own command reference

Captured from `/commands` (`raw/commands.txt`). This is the site describing
itself, so it is reliable on rules and silent on numbers. Every rate below still
needs measuring.

### Chatting itself pays

"You earn credits passively just by chatting — once a minute per person." A
per-minute trickle for one chat message is the floor of any plan, and it costs no
API calls at all. Rate unknown.

### Commands live in Kick chat, pages live on the API

The reference is explicit: "Type these in the Kick chat". So the Kick dependency
has **not** disappeared. But the page-based mechanics (fishing gear and selling,
business, casino games) have their own web endpoints. The realistic picture is
two surfaces, not one, and the earlier hope of dropping Kick entirely looks
wrong. Several actions appear to exist on both: `!fishsell` is documented as
"the same sale as the fishing page".

### Business is a collection-cadence game

- A till fills and then **stops earning**. Collecting regularly is the mechanic.
- Shops earn their **full rate only while the stream is live**, a fraction once it
  ends. Income is tied to the streamer's schedule, not to wall-clock time.
- A manager **triples** till capacity, which is what buys tolerance for collecting
  less often.
- Part of the catalogue is illegal: it pays **dirty money** into a separate stash
  that buys nothing until laundered, "earns more per credit invested than anything
  legal", but every collection rolls against a raid that seizes the till, fines
  you and shuts the shop for hours. Payoffs cut raid odds by up to three quarters.
- Laundering capacity comes from the **legal** shops you own, so an all-illegal
  empire piles up money it cannot spend. The legal/illegal ratio is an
  optimisation variable.
- Uncollected tills can be robbed by other players. Security hides up to three
  quarters; collecting hides all of it. Illegal tills cannot be robbed.

### Fishing is a flow, not a stock

- `!fish` is free on a cooldown. Unsold catches decay: "a full net is a bleeding
  net", which matches the 10 %/day decay in the public API.
- `!fishsell` is granular: by rarity, by species, by count, best or worst first,
  and `rare-` sweeps everything below a tier. Enough control to sell the decaying
  tail while keeping trophies.
- `!cook` converts spares into gear: 3 commons make worm bait, 5 uncommons make a
  lucky lure. It consumes the cheapest fish of the tier first.
- `!prestige` requires all 100 species on the current run and **cashes in the net**
  on the way out. Gear, credits and lifetime totals survive.
- `!treasure` is one free dig per day paying out across the whole site: fishing
  gear, criminal kit, a purse of credits, or a business contract. One call a day,
  never wasted. Likely the best credits-per-request in the game; unmeasured.

### Streamer-triggered events are the big, irregular money

Three events are minted by the streamer and cannot be predicted from polling:

| event | what it does | why it matters |
|---|---|---|
| `!chest <amount> [word]` | everyone who types the trigger word within **30 s** splits it | needs a reaction inside 30 s |
| `!frenzy [seconds]` | `!fish` cooldown drops to **zero for everyone** | a burst window worth far more than steady casting |
| `!boom [hours]` | drops N hours of takings into **every** till at once | "a full till can't take any more, so a boom rewards whoever has been collecting" |

This has an architectural consequence that polling cannot satisfy: a 24/7 tool
needs to **listen to chat**, not just call the API on a timer. It also gives a
standing rule for business play — keep tills empty, because a boom pays only into
room that exists.

### Player-versus-player

`!rob` takes from other real viewers and can force-sell the victim's shares; a
fine you cannot cover dumps your own. It is a sanctioned mechanic with gear on the
crime page for both attack and defence. It is also the one lever in this study
that takes credits from other people rather than generating them, so whether to
use it is a decision for the repository owner, not a modelling detail.

## Two optima that fall out of the structure alone

`model.py` derives these. They need no measured constant, only the shape of the
mechanic, so they hold whatever the rates turn out to be. Self-checks included;
run `python model.py`.

### Business: collect exactly when the till fills, never sooner

A till fills at rate `r` and stops at capacity `C`. Income when collecting every
`T` is `min(r·T, C)/T`. That is flat at `r` for every `T ≤ C/r`, then falls away
as `C/T`.

So there is a whole family of optimal cadences, and the cheapest member is
`T* = C/r` exactly. Collecting more often earns **nothing extra** and burns
requests; collecting later loses income proportionally. Credits per request is
simply `C`, and a manager tripling capacity divides the request cost by three
while leaving credits per hour untouched.

Two things bend this, both from the command reference:

- Shops earn full rate only while the stream is live. `r` is not constant, so
  `C/r` stretches when the stream is off. The cadence tracks the streamer's
  schedule, not the clock.
- A `!boom` pays into whatever room a till has, and a full till gets nothing.
  That is a call option on empty space, exercised at an unpredictable moment, and
  it biases the cadence *below* `C/r`: collecting early costs only requests and
  keeps the option alive.

Together these say the collection loop must be event-driven. A fixed timer is
wrong in both directions.

### Fishing: the net bleeds far slower than the wording suggests

The command page warns that "a full net is a bleeding net". The public decay
parameters say otherwise once you do the arithmetic: catches hold **full** value
for a 24 h fresh window, and only then decay at 10 %/day toward a 10 % floor.

| sell cadence | value kept |
|---|---|
| every 12 h | 100.0 % |
| daily | 100.0 % |
| weekly | 77.8 % |

Selling more than once a day is therefore pure waste — there is nothing to save.
Even a week of neglect costs about a fifth. The operational conclusion is the
opposite of the urgency the wording implies: **the request budget belongs to
casting, not to selling.** Selling is roughly one call per account per day.

Caveat: this assumes catches accumulate uniformly and that decay applies per
catch from its own capture time. Both are readings of the public `decay` block,
not measurements, and a stack that decays as a unit would change the numbers.

## Receiving chat server-side is solved, and mostly already built

The three streamer-triggered events (`!chest`, `!frenzy`, `!boom`) cannot be
caught by polling, so this decides whether they are reachable at all. It is, by
two independent routes, and neither needs new infrastructure.

**Blocked route, for the record.** Kick's own realtime gateway
(`websockets.kick.com`, viewer token then websocket upgrade) is browser-only.
Cloudflare rejects both the token endpoint and the handshake, and a Chrome TLS
fingerprint does not change that. Anything built directly on it from a server
will fail; do not spend time there.

**Route A, legacy Pusher — verified working, 2026-08-19.** `pusher_probe.py`
connects from a plain Python process, no browser, no TLS impersonation, and gets
`pusher:connection_established`, an accepted subscription on
`chatrooms.<id>.v2`, and a live stream of `App\Events\ChatMessageEvent`. Real
chat messages, in real time, from a server socket.

This corrects an inherited belief worth stating plainly: "Kick's chat websocket
is closed to servers" is true of `websockets.kick.com` and **false** of the
legacy Pusher transport, which is still carrying the chatroom channel today.

It is also the cheaper route by a distance: no developer app, no public HTTPS
URL, no tunnel, no webhook signature handling. And it is the lower-latency one,
which matters because a chest splits among whoever answers within 30 seconds and
every hop spends that budget.

**Route B, official webhooks via kickbus.** `Pkkls/kickbus` already exists and
does exactly this job: it receives webhooks from the official Kick API, verifies
their signature, and fans events out to local consumers over Server-Sent Events.
One daemon holds the credentials, every bot reads it with a single HTTP request.
It also repairs its own subscriptions every thirty minutes. The cost is
operational rather than technical: it needs a Kick developer app and an HTTPS URL
Kick can reach, so a tunnel or reverse proxy in front of it.

Route A is now the default: it is verified, free, and lower latency. Route B
stays documented as the fallback if Kick ever closes the legacy transport, which
it has already done once to the gateway.

Note that catching an event is only half of it: `!chest` requires **posting** a
reply into Kick chat within the window, which lands back on the Kick write path
and its protections. Reception being solved does not make the round trip solved.

## Chat is a gated surface, and the gate costs more than the login

`kick.com/api/v2/channels/<slug>` answers a plain HTTP client with HTTP 200 — no
Cloudflare challenge, no impersonation needed — and it carries the chatroom
settings. Read 2026-08-19:

| setting | value | what it costs us |
|---|---|---|
| `chat_mode` | public | — |
| `slow_mode` | true, `message_interval` 1 | one message per second. Not binding: chat income is once a minute anyway |
| `followers_mode` | true, `following_min_duration` **6** | **an account must have followed for 6 minutes before it can post at all** |
| `subscribers_mode` | false | — |

The follower gate is the real cost of enrolling any account. Every credit-earning
path that runs through chat — the per-minute chat income, `!daily`, `!fish`,
`!collect`, answering a chest — is closed until that account follows and waits.

That matters more than it looks, because following is the one Kick action known
to be hard to automate: it sits behind Kasada and has only ever worked from a
browser session driven by hand. So the cost of adding an account is not the
login, it is a manual follow plus a six-minute wait, and burst-following is
itself known to trip a rate penalty.

The same endpoint gives the live state, which the business model needs since
shops only earn full rate while the stream is up. At the time of reading: live,
684 viewers, session started 17:34 UTC. `chatroom.id` is 29834074, matching what
the July configs already had, so the chatroom never moved even though the channel
label did.

## The chat is a free measurement firehose

This reframes how the expensive half of the study gets done.

Several hundred people play this game in public. Their **commands** are certainly
visible: a first 51 s window at ~20 messages/minute already caught `!fish` and
`!rob` from four different players. If the game also announces **outcomes** in
chat, then catch values by rarity, chest sizes, frenzy and boom frequency, and
cooldowns implied by how fast a player repeats a command all become **observable
without sending a request or exposing an account**.

> **Unverified, and stated too confidently when first written.** In that first
> window no message from the game itself appeared — only players talking. So the
> outcome half of this is a hypothesis, not a finding. The likely confound is
> that the game bot runs on the same Railway deployment that is currently
> flapping, so its silence may say nothing about whether it normally replies.
> Re-check once the site is healthy, and if the game turns out never to answer in
> chat, the firehose shrinks to commands only, which is worth much less: command
> timings still give cooldowns, but nothing gives payouts.

That matters for three reasons:

1. Request budget stops being the binding constraint on those measurements. It
   only binds on things nobody else's play reveals, like our own balances.
2. Sample size stops being a problem. Our own accounts could generate a handful
   of observations an hour; the channel generates everyone's.
3. It works while shoovy.wtf is down, because it only touches Kick. During this
   session that has been most of the time.

`chat_listen.py` holds the socket, reconnects on drop, and appends everything to
`chat.jsonl` — chat messages structured, and any other event kept verbatim rather
than guessed at now. It listens only and never posts.

The obvious limit: chat shows outcomes, not the hidden state that produced them.
It gives distributions, not mechanics. Drop rates can be estimated from it; the
decay curve, capacity numbers and cooldown constants still need either the client
tables or an authenticated call.

## Availability is the binding constraint, not the rate limit

`uptime.py` derives this from `requests.jsonl`, which the harvest driver is
already filling, so it costs no extra requests.

First reading, 19 requests over 38 minutes (20:24-21:02, 2026-08-19):

| outcome | share |
|---|---|
| 429 | 57.9 % |
| 200 | **15.8 %** |
| 5xx | 15.8 % |
| transport error / timeout | 10.5 % |

**Longest run of consecutive usable answers: 2.**

Nineteen samples is a small n and the interval around 15.8 % is wide, so treat
the figure as an order of magnitude rather than a number.

**And it is contaminated.** For roughly fifteen minutes of that window two
harvest drivers were running at once, because restarting one never stopped the
old one. That doubled our own request rate against the backend, so some share of
those 429s may be self-inflicted rather than ambient. The figure is therefore a
*lower* bound on availability, not an estimate of it. The driver now holds a pid
lock so this cannot recur, and the number needs redoing over a clean window
before anything is built on the precise value.

The qualitative shape survives the contamination: a real browser was getting 502
from Cloudflare with no load from us at all, the outage predates the duplicate
driver by hours, and four harvest passes over 30 targets have captured 2 of them.

This reframes the study's central constraint. Earlier notes called request budget
the scarce resource, on the theory that a limiter was punishing us. That was the
wrong model twice over. The scarce resource is **availability**, and no amount of
polite pacing buys more of it.

Design consequences, and these are load-bearing for the 24/7 tool:

- **Nothing may assume a sequence of calls completes.** With a run length of 2,
  any flow of the shape "read state, then act on it" will routinely break between
  its two halves. Actions have to be individually retryable, and where the game
  allows it, idempotent.
- **Opportunistic, not scheduled.** A timer that fires an action every N minutes
  will mostly fire into a 502. The loop should be "try, expect to fail, keep the
  intent queued", not "sleep, act, assume".
- **Persistent intent.** If the tool wants to collect a till or claim a daily, it
  must hold that intent across restarts and outages until it observes a success,
  rather than dropping it when one call fails.
- **The cadence maths still holds but its input changes.** The business optimum
  `T* = C/r` assumed a collection lands when you want it. At 16 % availability the
  effective cadence is much coarser than the nominal one, which pushes the
  manager upgrade (capacity ×3, so three times the tolerance for a missed window)
  from a nice-to-have to the first thing worth buying.

To re-check as more samples accumulate: whether availability has a pattern
(recovery windows, correlation with stream traffic) or is simply flat and bad.
The per-hour breakdown in `uptime.py` will show it once there are enough hours.

## What 17 minutes of listening actually produced

368 messages, 20:52-21:08 on 2026-08-19, while our own requests to the game were
failing throughout. Three results, one of them a negative.

### Fishing is what people actually do

Of 25 commands seen, **21 were `!fish`**. The rest: two `!rob`, one `!treasure`,
one `!collect`, one `!site`. Whatever the spreadsheet eventually says about
business being the efficient earner, fishing is the mechanic the channel plays,
and that is worth knowing when judging how visible an account's behaviour is.

### A candidate fishing cooldown, around three minutes

One player kept a strikingly regular cadence: casts at 20:57:30, 21:00:18 and
21:03:17, so gaps of 168 s and 179 s. That is the signature of someone hitting a
cooldown rather than typing when they feel like it.

Marked candidate, not measured, for two reasons. It is one player and two
intervals. And the site was down for the whole window, so a command that does
nothing starts no cooldown — the regularity could be their retry habit rather
than the game's timer. Other players in the same window show gaps of 17 s, 38 s
and 2 s, which is consistent with spamming into a dead backend.

Re-measure when the game is answering. The method is sound and costs nothing:
take the players with the most casts, keep the modal gap, discard the impatient.

### Chat volume is not an availability sensor

Tested because it would have been free: if players spam commands when the game
is dead and settle when it works, chat rate would proxy for backend health
without spending a request.

It does not. Message rate stayed between 12 and 50 per minute across the whole
window while every one of our requests returned 429, 502 or a timeout. No
correlation, and no visible reaction to a backend that was down the entire time.
Most of the channel is talking, not playing, and the talkers do not notice.

### Still no sign of the game itself

Zero messages from any bot or system account in 368. That is now a substantially
larger sample behind the caveat recorded earlier, though it remains confounded by
the outage: a game that cannot answer looks identical to a game that never does.

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
