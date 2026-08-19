"""Load everything the study already knows into the semantic store.

Re-runnable: the store is append-only, so running this twice stacks duplicate
records rather than corrupting anything, but there is no reason to.

One distinction applied throughout, because it matters and the prose blurred it:
`measured` is what we observed on the wire ourselves. What the site asserts in
its own documentation but we have never watched happen is `assumed`, however
authoritative the source looks. Documentation goes stale; this project has
already been burned by inherited numbers once.
"""
import facts

W = "observe sur le fil par le client de l'etude"
DOC = "affirme par la page /commands du site, jamais observe se produire"
JULY = "herite du code de juillet, jamais reverifie"

F = []

# ---------------------------------------------------------------- infra ----
F += [
    dict(id="infra.cdn", subject="infra:shoovy.wtf", predicate="fronting",
         value="cloudflare devant railway", status="measured", confidence=1.0,
         method="en-tetes Server/CF-RAY/x-railway-edge sur toute reponse",
         source="requests.jsonl"),
    dict(id="infra.plain_client_ok", subject="infra:shoovy.wtf",
         predicate="accepte_client_stdlib", value=True, status="measured",
         confidence=1.0,
         method="GET /api/stocks avec User-Agent Go-http-client/1.1 -> HTTP 200",
         source="requests.jsonl"),
    dict(id="infra.cold_start_seconds", subject="infra:shoovy.wtf",
         predicate="cold_start", value=40, unit="s", status="measured",
         confidence=0.8, n=3, dispersion="41.3 / 5.7 / 0.2 s sur 3 appels successifs",
         method="premier appel apres inactivite, puis deux suivants", source="requests.jsonl"),
    dict(id="infra.429_shape", subject="infra:shoovy.wtf", predicate="forme_du_429",
         value="text/plain 12 octets 'rate limited', x-railway-edge, sans Retry-After ni X-RateLimit-*",
         status="measured", confidence=1.0,
         method="inspection des en-tetes de reponse", source="requests.jsonl"),
    # Contaminated first reading, kept because the correction stacks on it.
    dict(id="infra.availability.v1", subject="infra:availability",
         predicate="taux_reponses_utilisables", value=0.158, unit="fraction",
         status="measured", confidence=0.3, n=19,
         dispersion="n=19, intervalle large; serie utilisable maximale = 2",
         method="derive de requests.jsonl sur 20:24-21:02; BORNE BASSE, deux drivers "
                "tournaient pendant une partie de la fenetre donc une part de la charge "
                "etait la notre",
         source="uptime.py"),
    dict(id="infra.availability.max_run", subject="infra:availability",
         predicate="serie_utilisable_max", value=2, unit="requetes",
         status="measured", confidence=0.5, n=19,
         dispersion="meme fenetre contaminee que infra.availability.v1",
         method="plus longue suite de 200 consecutifs dans requests.jsonl",
         source="uptime.py"),
]

# ------------------------------------------------------------- kick/chat ----
F += [
    dict(id="kick.chatroom_id", subject="infra:kick", predicate="chatroom_id",
         value=29834074, status="measured", confidence=1.0,
         method="GET kick.com/api/v2/channels/<slug>, champ chatroom.id",
         source="kick.com/api/v2"),
    dict(id="kick.slow_mode_interval", subject="infra:kick",
         predicate="slow_mode_interval", value=1, unit="s", status="measured",
         confidence=1.0, method="champ chatroom.message_interval", source="kick.com/api/v2"),
    dict(id="kick.followers_min_minutes", subject="infra:kick",
         predicate="follow_minimum_avant_de_poster", value=6, unit="min",
         status="measured", confidence=1.0,
         method="champs chatroom.followers_mode + following_min_duration",
         source="kick.com/api/v2"),
    dict(id="chat.pusher_route_works", subject="infra:kick",
         predicate="chat_lisible_depuis_un_serveur", value=True, status="measured",
         confidence=1.0,
         method="client python nu: connection_established, souscription "
                "chatrooms.<id>.v2 acceptee, ChatMessageEvent reels recus",
         source="pusher_probe.py"),
    dict(id="chat.fish_command_share", subject="command:!fish",
         predicate="part_des_commandes_observees", value=0.84, unit="fraction",
         status="measured", confidence=0.6, n=25,
         dispersion="21 !fish sur 25 commandes, fenetre de 17 min",
         method="comptage des messages commencant par ! dans chat.jsonl",
         source="chat.jsonl"),
    dict(id="chat.message_rate", subject="infra:kick", predicate="debit_du_chat",
         value=19.2, unit="msg/min", status="measured", confidence=0.7, n=368,
         dispersion="12 a 50 msg/min selon la minute",
         method="368 messages sur 580 s", source="chat.jsonl"),
]

# ------------------------------------------------------------- fishing -----
F += [
    dict(id="fishing.decay_per_day", subject="mechanic:fishing",
         predicate="decay", value=0.10, unit="fraction/jour", status="measured",
         confidence=1.0, method="bloc decay de GET /api/fishing, repond sans session",
         source="/api/fishing"),
    dict(id="fishing.fresh_hours", subject="mechanic:fishing",
         predicate="fenetre_fraiche", value=24, unit="h", status="measured",
         confidence=1.0, method="bloc decay de GET /api/fishing", source="/api/fishing"),
    dict(id="fishing.floor_fraction", subject="mechanic:fishing",
         predicate="plancher_de_valeur", value=0.10, unit="fraction",
         status="measured", confidence=1.0,
         method="bloc decay de GET /api/fishing", source="/api/fishing"),
    dict(id="fishing.cooldown_seconds", subject="mechanic:fishing",
         predicate="cooldown", value=180, unit="s", status="candidate",
         confidence=0.4, n=2, dispersion="168 s et 179 s, un seul joueur",
         method="ecarts entre casts successifs d'un meme joueur, observes en chat",
         source="chat.jsonl",
         invalidated_by="le site etait indisponible pendant toute la fenetre: une "
                        "commande sans effet ne demarre aucun timer, donc la regularite "
                        "peut etre l'habitude du joueur et non le cooldown du jeu"),
    dict(id="fishing.cook_commons_for_bait", subject="mechanic:fishing",
         predicate="recette_bait", value=3, unit="communs", status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="fishing.cook_uncommons_for_lure", subject="mechanic:fishing",
         predicate="recette_lure", value=5, unit="uncommons", status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="fishing.prestige_species", subject="mechanic:fishing",
         predicate="especes_requises_pour_prestige", value=100, unit="especes",
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="treasure.digs_per_day", subject="mechanic:treasure",
         predicate="fouilles_gratuites", value=1, unit="par jour", status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
]

# ------------------------------------------------------------- business ----
F += [
    dict(id="business.manager_capacity_multiplier", subject="mechanic:business",
         predicate="multiplicateur_capacite_manager", value=3, status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="business.till_stops_when_full", subject="mechanic:business",
         predicate="till_sature", value=True, status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="business.full_rate_only_live", subject="mechanic:business",
         predicate="taux_plein_seulement_en_live", value=True, status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="business.payoff_raid_reduction_max", subject="mechanic:business",
         predicate="reduction_max_odds_de_raid_par_payoff", value=0.75,
         unit="fraction", status="assumed", confidence=0.6, method=DOC,
         source="raw/commands.txt"),
]

# --------------------------------------------------------------- events ----
F += [
    dict(id="chest.response_window", subject="event:chest",
         predicate="fenetre_de_reponse", value=30, unit="s", status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="chat.income_period", subject="mechanic:chat_income",
         predicate="periode_de_gain", value=60, unit="s", status="assumed",
         confidence=0.7,
         method="'once a minute per person' dans la doc du site, montant non precise",
         source="raw/commands.txt"),
]

# --------------------------------------------------------- leaderboard -----
for rank, bal in enumerate([792841, 362064, 211700, 169956, 145826], start=1):
    F.append(dict(id=f"leaderboard.rank{rank}", subject="infra:leaderboard",
                  predicate=f"solde_rang_{rank}", value=bal, unit="credits",
                  status="measured", confidence=1.0,
                  method="GET /api/leaderboard, instantane du 2026-08-19; "
                         "un solde n'est pas une pente, la cible est un debit",
                  source="/api/leaderboard"))

# ---------------------------------------------------- derives du modele ----
F += [
    dict(id="business.optimal_period", subject="mechanic:business",
         predicate="cadence_de_collecte_optimale", value="T* = C / r",
         status="derived", confidence=0.9,
         derived_from=["business.till_stops_when_full"],
         method="revenu = min(r*T, C)/T, plat a r pour tout T <= C/r puis decroit en "
                "C/T; collecter plus tot ne rapporte rien et coute des requetes",
         source="model.py"),
    dict(id="business.manager_request_divisor", subject="mechanic:business",
         predicate="division_du_cout_en_requetes_par_manager", value=3,
         status="derived", confidence=0.8,
         derived_from=["business.optimal_period",
                       "business.manager_capacity_multiplier"],
         method="T* est proportionnel a C, donc tripler C divise par trois la "
                "frequence de collecte necessaire",
         source="model.py"),
    dict(id="fishing.daily_sell_lossless", subject="mechanic:fishing",
         predicate="valeur_conservee_en_vendant_une_fois_par_jour", value=1.0,
         unit="fraction", status="derived", confidence=0.9,
         derived_from=["fishing.decay_per_day", "fishing.fresh_hours"],
         method="rien ne decay avant 24 h, donc vendre plus d'une fois par jour "
                "ne sauve rien",
         source="model.py"),
    dict(id="fishing.weekly_retention", subject="mechanic:fishing",
         predicate="valeur_conservee_apres_une_semaine", value=0.778,
         unit="fraction", status="derived", confidence=0.8,
         derived_from=["fishing.decay_per_day", "fishing.fresh_hours",
                       "fishing.floor_fraction"],
         method="integration de la courbe de decay sur des captures uniformes "
                "sur 168 h",
         source="model.py"),
]

# -------------------------------------------------------------- refutes ----
F += [
    dict(id="infra.ip_banned_by_probes", subject="infra:shoovy.wtf",
         predicate="ip_bannie_par_nos_sondes", value=False, status="refuted",
         confidence=0.9,
         method="refute par temoin: un vrai navigateur recevait 502 de Cloudflare "
                "sans aucune charge de notre part, et le blocage est tombe seul "
                "apres ~3h15 sans changement de comportement",
         source="FINDINGS.md"),
    dict(id="chat.ws_closed_to_servers", subject="infra:kick",
         predicate="chat_ferme_aux_serveurs", value=False, status="refuted",
         confidence=1.0,
         method="vrai de websockets.kick.com, faux du Pusher legacy qui porte "
                "toujours le chatroom et accepte un client serveur nu",
         source="pusher_probe.py"),
    dict(id="chat.volume_as_availability_sensor", subject="infra:availability",
         predicate="debit_du_chat_proxy_de_sante_backend", value=False,
         status="refuted", confidence=0.8, n=368,
         dispersion="17 minutes, 12 a 50 msg/min",
         method="le debit du chat est reste stable pendant que 100 % de nos "
                "requetes renvoyaient 429, 502 ou timeout: aucune correlation",
         source="chat.jsonl"),
]

# ------------------------------------------------- herites de juillet ------
for i, (pid, subj, pred, val, unit) in enumerate([
    ("daily.amount", "mechanic:daily", "montant", 200, "credits"),
    ("daily.period_hours", "mechanic:daily", "periode", 20, "h"),
    ("stocks.trade_cooldown", "mechanic:stocks", "cooldown_entre_trades", 8, "s"),
    ("stocks.fee_pct", "mechanic:stocks", "frais", 1, "%"),
    ("stocks.depth", "mechanic:stocks", "profondeur_amm", 250000, "credits"),
    ("stocks.ticker_count", "mechanic:stocks", "nombre_de_tickers", 5, None),
    ("trader.ma_window", "mechanic:stocks", "fenetre_moyenne_mobile", 20, "points"),
    ("trader.entry_dev", "mechanic:stocks", "seuil_entree", -0.03, "fraction"),
    ("trader.exit_dev", "mechanic:stocks", "seuil_sortie", -0.005, "fraction"),
]):
    rec = dict(id=pid, subject=subj, predicate=pred, value=val, status="assumed",
               confidence=0.3, method=JULY, source="configs de juillet du repo")
    if unit:
        rec["unit"] = unit
    F.append(rec)


def main():
    ok = err = 0
    for rec in F:
        try:
            facts.add(**rec)
            ok += 1
        except facts.Invalid as e:
            print("REJETE:", e)
            err += 1
    print(f"\n{ok} faits charges, {err} rejetes")
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
