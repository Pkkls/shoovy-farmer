"""Recursive inference over the semantic store.

Rules read the current facts and emit derived ones. Derived facts feed the next
pass, so the whole set is applied to a fixpoint rather than once. Every emitted
fact carries `derived_from`, which is what makes the result auditable and what
lets invalidation travel back down the chain.

The single most consequential thing this discovers is that availability is not
one factor among many: it multiplies into every mechanic, and it compounds
against any flow that needs more than one call to land.

    python infer.py          # run to fixpoint, append new derived facts
    python infer.py --dry    # show what would be emitted, write nothing
"""
import sys

import budget
import facts

MAX_PASSES = 10


def _val(cur, fid):
    rec = cur.get(fid)
    return rec["value"] if rec else None


# Each rule takes the current fact map and returns a list of candidate records.
# Emitting something already present is fine: the runner drops unchanged repeats.

def rule_success_probability(cur):
    """A call succeeds about as often as the backend is up. Everything else
    hangs off this number."""
    p = _val(cur, "infra.availability.v1")
    if p is None:
        return []
    return [dict(
        id="infra.call_success_probability", subject="infra:availability",
        predicate="probabilite_qu_un_appel_aboutisse", value=round(p, 3),
        unit="fraction", status="derived", confidence=0.3,
        derived_from=["infra.availability.v1"],
        method="assimile la disponibilite mesuree a la probabilite de succes d'un "
               "appel isole; borne basse puisque la mesure source est contaminee",
        source="infer.py")]


def rule_multistep_compounding(cur):
    """A flow of k calls lands only if all k land. With p small this is brutal,
    and it is why read-then-act is the wrong shape here."""
    p = _val(cur, "infra.call_success_probability")
    if p is None:
        return []
    out = []
    for k in (2, 3):
        out.append(dict(
            id=f"infra.flow_success_{k}_steps", subject="infra:availability",
            predicate=f"probabilite_qu_un_enchainement_de_{k}_appels_aboutisse",
            value=round(p ** k, 4), unit="fraction", status="derived",
            confidence=0.3, derived_from=["infra.call_success_probability"],
            method=f"p^{k}, en supposant les echecs independants",
            source="infer.py"))
    return out


def rule_chest_capture(cur):
    """A chest never touches shoovy.wtf on our side.

    The streamer types the trigger in Kick chat and viewers answer in Kick chat.
    We detect over the Pusher socket, which is verified working, and answer over
    the Kick write path. The game credits it server-side, which is their
    availability problem and not ours.

    So the binding term is Kick write reliability, which nothing has measured. It
    is deliberately not filled with the shoovy figure: substituting a number from
    the wrong system is how a model starts lying confidently.
    """
    window = _val(cur, "chest.response_window")
    if window is None or not cur.get("chat.pusher_route_works"):
        return []
    return [dict(
        id="event.chest_capture_probability", subject="event:chest",
        predicate="probabilite_de_capter_un_chest",
        value="indeterminee, gouvernee par la fiabilite d'ecriture Kick",
        status="derived", confidence=0.5,
        derived_from=["chat.pusher_route_works", "chest.response_window"],
        supersedes="event.chest_capture_probability",
        method=f"le cycle complet (detecter le mot declencheur, le retaper dans les "
               f"{window}s) est entierement cote Kick: reception verifiee par Pusher, "
               "reponse par le chemin d'ecriture Kick. shoovy.wtf n'est pas sur le "
               "chemin, donc sa disponibilite ne s'applique pas. Remplace une version "
               "anterieure qui appliquait a tort le 2.5 % de shoovy",
        source="infer.py")]


def rule_fishing_throughput(cur):
    """Casts per hour actually achievable, cooldown against retries."""
    cd = _val(cur, "fishing.cooldown_seconds")
    p = _val(cur, "infra.call_success_probability")
    if cd is None or p is None:
        return []
    nominal = 3600.0 / cd
    out = [
        dict(id="fishing.casts_per_hour_nominal", subject="mechanic:fishing",
             predicate="lancers_par_heure_theoriques", value=round(nominal, 2),
             unit="casts/h", status="derived", confidence=0.4,
             derived_from=["fishing.cooldown_seconds"],
             method="3600 / cooldown, plafond impose par le jeu",
             source="infer.py"),
    ]
    # Retrying inside the cooldown window is what actually happens, and it
    # recovers most of what naive multiplication threw away.
    for gap in (30.0, 10.0):
        hit, attempts = budget.p_success_in_window(p, cd, gap)
        out.append(dict(
            id=f"fishing.casts_per_hour_effective_retry{int(gap)}s",
            subject="mechanic:fishing",
            predicate=f"lancers_par_heure_reels_avec_reessai_toutes_les_{int(gap)}s",
            value=round(nominal * hit, 2), unit="casts/h", status="derived",
            confidence=0.3,
            derived_from=["fishing.casts_per_hour_nominal",
                          "infra.call_success_probability",
                          "fishing.cooldown_seconds"],
            method=f"P(au moins un succes dans la fenetre) = 1-(1-p)^{attempts} "
                   f"avec {attempts} essais espaces de {int(gap)}s dans un cooldown "
                   f"de {cd:.0f}s, soit {hit:.3f}. Un lancer rate n'est pas perdu: "
                   "seul du temps est depense dans une fenetre qui allait s'ecouler",
            source="budget.py"))
    return out


def rule_business_effective_cadence(cur):
    """The clean optimum assumed a collection lands when you want it."""
    p = _val(cur, "infra.call_success_probability")
    mult = _val(cur, "business.manager_capacity_multiplier")
    if p is None:
        return []
    out = [dict(
        id="business.attempts_per_successful_collect", subject="mechanic:business",
        predicate="tentatives_par_collecte_reussie", value=round(1.0 / p, 1),
        unit="appels", status="derived", confidence=0.3,
        derived_from=["infra.call_success_probability", "business.optimal_period"],
        method="esperance d'une geometrique de parametre p; la cadence nominale C/r "
               "doit etre visee bien plus tot que necessaire pour qu'une collecte "
               "tombe avant saturation",
        source="infer.py")]
    if mult:
        out.append(dict(
            id="business.manager_priority", subject="mechanic:business",
            predicate="rang_d_achat_du_manager", value="premier achat rentable",
            status="derived", confidence=0.5,
            derived_from=["business.manager_request_divisor",
                          "business.attempts_per_successful_collect"],
            method=f"le manager multiplie la capacite par {mult}, donc la tolerance a "
                   "une fenetre de collecte ratee; sous une disponibilite basse cette "
                   "tolerance vaut plus que le revenu marginal d'une autre boutique",
            source="infer.py"))
    return out


def rule_rank1_requirement(cur):
    """What net rate closes the gap to rank 1, per target horizon."""
    r1 = _val(cur, "leaderboard.rank1")
    if r1 is None:
        return []
    out = []
    for days in (30, 90):
        out.append(dict(
            id=f"target.rate_needed_{days}d", subject="infra:leaderboard",
            predicate=f"debit_net_requis_pour_rattraper_en_{days}_jours",
            value=round(r1 / days, 1), unit="credits/jour", status="derived",
            confidence=0.2, derived_from=["leaderboard.rank1"],
            method=f"solde du rang 1 divise par {days} jours, EN PARTANT DE ZERO et "
                   "EN SUPPOSANT LE RANG 1 IMMOBILE. Les deux hypotheses sont fausses: "
                   "la cible est une pente, pas un solde, et elle n'a pas encore ete "
                   "echantillonnee. A remplacer des que la pente existe",
            source="infer.py"))
    return out


def rule_fishing_sell_budget(cur):
    """Selling is cheap, so the request budget belongs to casting."""
    daily = _val(cur, "fishing.daily_sell_lossless")
    casts = _val(cur, "fishing.casts_per_hour_nominal")
    if daily is None or casts is None:
        return []
    sells_per_day = 1.0
    casts_per_day = casts * 24
    return [dict(
        id="fishing.sell_share_of_calls", subject="mechanic:fishing",
        predicate="part_des_appels_consacree_a_la_vente",
        value=round(sells_per_day / (casts_per_day + sells_per_day), 4),
        unit="fraction", status="derived", confidence=0.4,
        derived_from=["fishing.daily_sell_lossless",
                      "fishing.casts_per_hour_nominal"],
        method="une vente par jour contre les lancers d'une journee: la vente est "
               "un arrondi dans le budget, contrairement a ce que suggere "
               "l'avertissement du jeu sur le filet qui saigne",
        source="infer.py")]


RULES = [
    rule_success_probability,
    rule_multistep_compounding,
    rule_chest_capture,
    rule_fishing_throughput,
    rule_business_effective_cadence,
    rule_rank1_requirement,
    rule_fishing_sell_budget,
]


def suspect_chain(cur):
    """Transitive fallout: everything resting, at any depth, on a refuted fact."""
    bad = {fid for fid, r in cur.items() if r["status"] == "refuted"}
    tainted, changed = set(), True
    while changed:
        changed = False
        for fid, r in cur.items():
            if fid in tainted:
                continue
            parents = set(r.get("derived_from") or [])
            if parents & (bad | tainted):
                tainted.add(fid)
                changed = True
    return tainted


def main():
    dry = "--dry" in sys.argv
    emitted_total = 0

    for p in range(1, MAX_PASSES + 1):
        cur = facts.current()
        new = []
        for rule in RULES:
            for rec in rule(cur):
                old = cur.get(rec["id"])
                if old and old.get("value") == rec["value"]:
                    continue  # nothing changed, do not stack a duplicate
                if old:
                    rec["supersedes"] = rec["id"]
                new.append(rec)
        if not new:
            print(f"point fixe atteint apres {p - 1} passe(s)")
            break
        print(f"\n--- passe {p}: {len(new)} nouveau(x) fait(s)")
        for rec in new:
            unit = f" {rec.get('unit','')}".rstrip()
            print(f"  {rec['id']:38} {rec['value']}{unit}")
            if not dry:
                facts.add(**rec)
        emitted_total += len(new)
        if dry:
            print("(--dry: rien ecrit, donc pas de recursion possible)")
            break
    else:
        print(f"arret apres {MAX_PASSES} passes sans point fixe")

    cur = facts.current()
    tainted = suspect_chain(cur)
    print(f"\n{emitted_total} fait(s) derive(s) au total")
    if tainted:
        print(f"\n{len(tainted)} fait(s) reposant sur un refute, en profondeur:")
        for fid in sorted(tainted):
            print(f"  ! {fid}")
    else:
        print("aucun fait ne repose sur un refute")
    return 0


if __name__ == "__main__":
    sys.exit(main())
