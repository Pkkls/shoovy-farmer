"""Charge dans le magasin semantique tout ce que raw/commands.txt affirme.

C'est la doc /commands du site (une page HTML capturee hors ligne), jamais une
observation de comportement en direct. Tout ce qui vient d'ici est donc
`assumed`, jamais `measured`, quelle que soit la clarte du texte.

Re-runnable comme seed_facts.py: le magasin est append-only.
"""
import facts

DOC = "affirme par la page /commands (raw/commands.txt) du site, jamais observe se produire"

F = []

# ------------------------------------------------------------- credits ----
F += [
    dict(id="credits.signature", subject="command:!credits", predicate="signature",
         value="!credits <user> (optionnel)", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="credits.aliases", subject="command:!credits", predicate="aliases",
         value="!coins, !points, !balance", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="leaderboard.signature", subject="command:!leaderboard", predicate="signature",
         value="!leaderboard", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="leaderboard.aliases", subject="command:!leaderboard", predicate="aliases",
         value="!top", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="leaderboard.top_n_shown", subject="command:!leaderboard",
         predicate="taille_du_top_affiche", value=5, status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="daily.signature", subject="command:!daily", predicate="signature",
         value="!daily", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="tip.signature", subject="command:!tip", predicate="signature",
         value="!tip <user> <amount>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="tip.recipient_must_have_chatted", subject="command:!tip",
         predicate="destinataire_doit_avoir_deja_chatte", value=True,
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="site.signature", subject="command:!site", predicate="signature",
         value="!site", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="help.signature", subject="command:!help", predicate="signature",
         value="!help", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="help.aliases", subject="command:!help", predicate="aliases",
         value="!commands", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
]

# -------------------------------------------------------------- casino ----
F += [
    dict(id="gamble.signature", subject="command:!gamble", predicate="signature",
         value="!gamble <amount|all>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="casino.gamble_win_multiplier", subject="mechanic:casino",
         predicate="multiplicateur_de_gain", value=2, status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="plinko.signature", subject="command:!plinko", predicate="signature",
         value="!plinko <amount|all>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="plinko.requires_board_enabled", subject="command:!plinko",
         predicate="necessite_le_plateau_active", value=True, status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="enableplinko.signature", subject="command:!enableplinko",
         predicate="signature", value="!enableplinko", status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="enableplinko.aliases", subject="command:!enableplinko",
         predicate="aliases", value="!plinkoon", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="enableplinko.permission", subject="command:!enableplinko",
         predicate="qui_peut_lancer", value="streamer, admins, mods",
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="disableplinko.signature", subject="command:!disableplinko",
         predicate="signature", value="!disableplinko", status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="disableplinko.aliases", subject="command:!disableplinko",
         predicate="aliases", value="!plinkooff", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="disableplinko.permission", subject="command:!disableplinko",
         predicate="qui_peut_lancer", value="streamer, admins, mods",
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="rob.signature", subject="command:!rob", predicate="signature",
         value="!rob <user>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="crime.rob_force_sells_victim_stock", subject="mechanic:crime",
         predicate="gros_butin_force_la_vente_des_actions_de_la_victime",
         value=True, status="assumed", confidence=0.7, method=DOC,
         source="raw/commands.txt"),
    dict(id="crime.rob_fine_force_sells_own_stock", subject="mechanic:crime",
         predicate="amende_non_couverte_force_la_vente_de_ses_propres_actions",
         value=True, status="assumed", confidence=0.7, method=DOC,
         source="raw/commands.txt"),
    dict(id="business.illegal_till_immune_to_rob", subject="mechanic:business",
         predicate="till_illegal_impossible_a_voler", value=True, status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="business.security_hide_fraction", subject="mechanic:business",
         predicate="fraction_du_till_cachee_par_la_securite", value=0.75,
         unit="fraction", status="assumed", confidence=0.6, method=DOC,
         source="raw/commands.txt"),
    dict(id="business.collect_hides_till_from_rob", subject="mechanic:business",
         predicate="collecter_cache_tout_le_till_du_vol", value=True,
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="duel.signature", subject="command:!duel", predicate="signature",
         value="!duel <user> <amount>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="duel.accept_window", subject="mechanic:casino",
         predicate="fenetre_pour_repondre", value=60, unit="s", status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="duel.refund_on_timeout", subject="mechanic:casino",
         predicate="challenger_rembourse_si_pas_de_reponse", value=True,
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="accept.signature", subject="command:!accept", predicate="signature",
         value="!accept", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="decline.signature", subject="command:!decline", predicate="signature",
         value="!decline", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
]

# -------------------------------------------------------------- stocks ----
F += [
    dict(id="stocks.signature", subject="command:!stocks", predicate="signature",
         value="!stocks", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="stocks.change_window_hours", subject="mechanic:stocks",
         predicate="fenetre_de_variation_affichee", value=1, unit="h",
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="buy.signature", subject="command:!buy", predicate="signature",
         value="!buy <ticker> <credits>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="stocks.buy_increases_price", subject="mechanic:stocks",
         predicate="achat_fait_monter_le_prix", value=True, status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="sell.signature", subject="command:!sell", predicate="signature",
         value="!sell <ticker> <shares|all>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="stocks.sell_decreases_price", subject="mechanic:stocks",
         predicate="vente_fait_baisser_le_prix", value=True, status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="portfolio.signature", subject="command:!portfolio", predicate="signature",
         value="!portfolio <user> (optionnel)", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
]

# ---------------------------------------------------------- predictions ----
F += [
    dict(id="predict.signature", subject="command:!predict", predicate="signature",
         value="!predict <option#> <amount>", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="predict.one_bet_per_prediction", subject="command:!predict",
         predicate="paris_max_par_prediction", value=1, status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
]

# -------------------------------------------------------------- raffles ----
F += [
    dict(id="raffle.signature", subject="command:!raffle", predicate="signature",
         value="!raffle [tickets]", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="raffle.aliases", subject="command:!raffle", predicate="aliases",
         value="!tickets", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="raffles.odds_proportional_to_tickets", subject="mechanic:raffles",
         predicate="cotes_proportionnelles_au_nombre_de_tickets", value=True,
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="raffles.credits_spent_regardless_of_outcome", subject="mechanic:raffles",
         predicate="credits_depenses_meme_en_cas_de_perte", value=True,
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="raffles.cancel_refunds_everyone", subject="mechanic:raffles",
         predicate="raffle_annulee_rembourse_tout_le_monde", value=True,
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
]

# -------------------------------------------------------------- fishing ----
F += [
    dict(id="fish.signature", subject="command:!fish", predicate="signature",
         value="!fish", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="fishsell.signature", subject="command:!fishsell", predicate="signature",
         value="!fishsell <all|rarity|species> [count] [best|worst]",
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="fishsell.minus_suffix_sweeps_lower_tiers", subject="command:!fishsell",
         predicate="suffixe_moins_balaie_les_paliers_inferieurs", value=True,
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="treasure.signature", subject="command:!treasure", predicate="signature",
         value="!treasure", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="treasure.never_wasted", subject="mechanic:treasure",
         predicate="fouille_jamais_pour_rien", value=True, status="assumed",
         confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="cook.signature", subject="command:!cook", predicate="signature",
         value="!cook <item>", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="cook.eats_cheapest_stock_first", subject="command:!cook",
         predicate="consomme_les_poissons_les_moins_chers_dabord", value=True,
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="prestige.signature", subject="command:!prestige", predicate="signature",
         value="!prestige", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
]

# ------------------------------------------------------------- business ----
F += [
    dict(id="business.signature", subject="command:!business", predicate="signature",
         value="!business", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="business.aliases", subject="command:!business", predicate="aliases",
         value="!biz", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="collect.signature", subject="command:!collect", predicate="signature",
         value="!collect", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="collect.aliases", subject="command:!collect", predicate="aliases",
         value="!cashout", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="business.collect_timing_irrelevant_to_earned_amount",
         subject="mechanic:business",
         predicate="moment_de_la_collecte_ninflue_pas_sur_le_montant_gagne",
         value=True, status="assumed", confidence=0.7, method=DOC,
         source="raw/commands.txt"),
    dict(id="business.illegal_yield_higher_than_legal", subject="mechanic:business",
         predicate="rendement_illegal_superieur_au_legal_par_credit_investi",
         value=True, status="assumed", confidence=0.7, method=DOC,
         source="raw/commands.txt"),
    dict(id="wash.signature", subject="command:!wash", predicate="signature",
         value="!wash", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="wash.aliases", subject="command:!wash", predicate="aliases",
         value="!launder", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="business.wash_unused_capacity_accumulates", subject="mechanic:business",
         predicate="capacite_de_lavage_inutilisee_saccumule", value=True,
         status="assumed", confidence=0.7, method=DOC, source="raw/commands.txt"),
    dict(id="empire.signature", subject="command:!empire", predicate="signature",
         value="!empire [user]", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
]

# ------------------------------------------------------------------ tts ----
F += [
    dict(id="tts.signature", subject="command:!tts", predicate="signature",
         value="!tts <message>", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="tts.no_links_allowed", subject="mechanic:tts",
         predicate="liens_interdits", value=True, status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
]

# ------------------------------------------------------------------ fun ----
F += [
    dict(id="cock.signature", subject="command:!cock", predicate="signature",
         value="!cock [user]", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="cock.range", subject="command:!cock", predicate="plage_affichee",
         value="0-12 inches", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="boobs.signature", subject="command:!boobs", predicate="signature",
         value="!boobs [user]", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="boobs.range", subject="command:!boobs", predicate="plage_affichee",
         value="34 AA-G cup", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
]

# ---------------------------------------------------------------- admin ----
F += [
    dict(id="ttson.signature", subject="command:!ttson", predicate="signature",
         value="!ttson", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="ttson.permission", subject="command:!ttson", predicate="qui_peut_lancer",
         value="streamer, admins", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="ttsoff.signature", subject="command:!ttsoff", predicate="signature",
         value="!ttsoff", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="ttsoff.permission", subject="command:!ttsoff", predicate="qui_peut_lancer",
         value="streamer, admins", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="pump.signature", subject="command:!pump", predicate="signature",
         value="!pump <ticker>", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="pump.permission", subject="command:!pump", predicate="qui_peut_lancer",
         value="streamer, admins", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="dump.signature", subject="command:!dump", predicate="signature",
         value="!dump <ticker>", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="dump.permission", subject="command:!dump", predicate="qui_peut_lancer",
         value="streamer, admins", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="chest.signature", subject="command:!chest", predicate="signature",
         value="!chest <amount> [trigger word]", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="chest.permission", subject="command:!chest", predicate="qui_peut_lancer",
         value="streamer seulement", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="chest.default_trigger_word", subject="event:chest",
         predicate="mot_declencheur_par_defaut", value="W", status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="frenzy.signature", subject="command:!frenzy", predicate="signature",
         value="!frenzy [seconds|stop]", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="frenzy.aliases", subject="command:!frenzy", predicate="aliases",
         value="!fishfrenzy, !fishingfrenzy", status="assumed", confidence=0.8,
         method=DOC, source="raw/commands.txt"),
    dict(id="frenzy.permission", subject="command:!frenzy", predicate="qui_peut_lancer",
         value="streamer, admins", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="frenzy.default_duration_seconds", subject="event:frenzy",
         predicate="duree_par_defaut", value=30, unit="s", status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="frenzy.fish_cooldown_override", subject="event:frenzy",
         predicate="cooldown_de_fish_ramene_a_zero", value=True, status="assumed",
         confidence=0.8, method=DOC, source="raw/commands.txt"),
    dict(id="boom.signature", subject="command:!boom", predicate="signature",
         value="!boom [hours]", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="boom.aliases", subject="command:!boom", predicate="aliases",
         value="!businessboom", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="boom.permission", subject="command:!boom", predicate="qui_peut_lancer",
         value="streamer, admins", status="assumed", confidence=0.8, method=DOC,
         source="raw/commands.txt"),
    dict(id="boom.till_full_blocks_boom", subject="event:boom",
         predicate="till_plein_ne_recoit_rien_du_boom", value=True,
         status="assumed", confidence=0.8, method=DOC, source="raw/commands.txt"),
]


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
