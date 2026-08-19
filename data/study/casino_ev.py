"""
Calcul de l'esperance de gain (RTP / house edge) par jeu de casino, a partir
de games_tables.json produit par extract_games.py.

Regle du jeu : un pari a esperance nette calculable exige a la fois
  - une probabilite de gain p (0 <= p <= 1)
  - un multiplicateur de paiement total m (ce que le joueur RECOIT s'il gagne,
    mise comprise -- ex: coinflip "gagne 2x sa mise" => m=2)

Pour une mise de 1 credit :
    RTP  = p * m                (retour attendu par credit mise)
    EV   = RTP - 1              (gain net attendu par credit mise)
    house_edge = 1 - RTP = -EV

Avec rakeback a un taux r (fraction, ex 0.05 pour 5%) qui rembourse une part
du montant MISE independamment du resultat :
    EV_net = EV + r = (RTP - 1) + r
    RTP_net = RTP + r

Le rakeback ne peut RENDRE un jeu a esperance positive que si r >= house_edge,
c'est-a-dire r >= 1 - RTP. C'est la question posee par ce chantier.

Ce script ne calcule RIEN pour un jeu dont p ou m manquent dans
games_tables.json -- il le dit explicitement plutot que de deviner.
"""

import json
from pathlib import Path

TABLES_PATH = Path(__file__).parent / "games_tables.json"


def ev_single_bet(p, m):
    """Esperance de gain par credit mise pour un pari a issue binaire
    (perte totale de la mise si echec, m credits recus si succes,
    m credits comprenant la mise rendue)."""
    if not (0 <= p <= 1):
        raise ValueError(f"probabilite hors [0,1]: {p}")
    if m < 0:
        raise ValueError(f"multiplicateur negatif: {m}")
    rtp = p * m
    return {"p": p, "m": m, "rtp": rtp, "ev_per_credit": rtp - 1, "house_edge": 1 - rtp}


def ev_with_rakeback(ev_result, rakeback_rate):
    """Ajoute un rakeback (fraction du montant mise, rendue quel que soit
    le resultat) a un resultat d'ev_single_bet. rakeback_rate est une
    fraction (0.05 = 5%), pas un pourcentage."""
    net_ev = ev_result["ev_per_credit"] + rakeback_rate
    return {
        **ev_result,
        "rakeback_rate": rakeback_rate,
        "ev_per_credit_net": net_ev,
        "rtp_net": ev_result["rtp"] + rakeback_rate,
        "profitable_with_rakeback": net_ev > 0,
        "breakeven_rakeback_rate": ev_result["house_edge"],
    }


def demo():
    """Verifications a la main avant de faire confiance a la formule.

    Coinflip a piece equilibree, mise x2 si gagne (bet 1 -> recoit 2 si
    pile/face correct) :
        p = 0.5, m = 2  =>  RTP = 1.0, EV = 0, house edge = 0 (jeu equitable)

    Meme coinflip mais avec un multiplicateur de 1.9x (house edge classique
    d'un coinflip a 5%) :
        p = 0.5, m = 1.9  =>  RTP = 0.95, EV = -0.05, house edge = 5%

    Un pari perdant a coup sur (p=0, peu importe m) doit rendre EV = -1
    (perte totale de la mise). Un pari gagnant a coup sur avec m=1 (remise
    de la mise, aucun profit) doit rendre EV = 0.

    Rakeback : sur le coinflip a 5% de house edge, un rakeback de 5%
    (r=0.05) doit exactement ramener l'EV net a 0 (seuil de rentabilite).
    Un rakeback de 3% doit laisser le jeu a esperance negative.
    """
    fair = ev_single_bet(0.5, 2.0)
    assert abs(fair["rtp"] - 1.0) < 1e-9, fair
    assert abs(fair["ev_per_credit"] - 0.0) < 1e-9, fair
    assert abs(fair["house_edge"] - 0.0) < 1e-9, fair

    edged = ev_single_bet(0.5, 1.9)
    assert abs(edged["rtp"] - 0.95) < 1e-9, edged
    assert abs(edged["ev_per_credit"] - (-0.05)) < 1e-9, edged
    assert abs(edged["house_edge"] - 0.05) < 1e-9, edged

    sure_loss = ev_single_bet(0.0, 50.0)
    assert abs(sure_loss["ev_per_credit"] - (-1.0)) < 1e-9, sure_loss

    sure_return = ev_single_bet(1.0, 1.0)
    assert abs(sure_return["ev_per_credit"] - 0.0) < 1e-9, sure_return

    at_breakeven = ev_with_rakeback(edged, 0.05)
    assert abs(at_breakeven["ev_per_credit_net"] - 0.0) < 1e-9, at_breakeven
    assert at_breakeven["profitable_with_rakeback"] is False  # exactement 0, pas > 0

    below_breakeven = ev_with_rakeback(edged, 0.03)
    assert below_breakeven["ev_per_credit_net"] < 0, below_breakeven
    assert below_breakeven["profitable_with_rakeback"] is False

    above_breakeven = ev_with_rakeback(edged, 0.10)
    assert above_breakeven["ev_per_credit_net"] > 0, above_breakeven
    assert above_breakeven["profitable_with_rakeback"] is True

    print("demo() : toutes les assertions passent (coinflip p=0.5/m=2 -> RTP=1.0, "
          "p=0.5/m=1.9 -> house edge=5%, rakeback=5% ramene exactement a l'equilibre).")


def load_tables():
    if not TABLES_PATH.exists():
        raise FileNotFoundError(
            f"{TABLES_PATH} introuvable -- lancer extract_games.py d'abord"
        )
    return json.loads(TABLES_PATH.read_text(encoding="utf-8"))


def status_value(field):
    """Lit un champ au format {value, status, ...} produit par extract_games.py.
    Retourne (value, is_present)."""
    if not isinstance(field, dict) or "status" not in field:
        return None, False
    return field.get("value"), field["status"] == "found_in_client"


def evaluate_games(tables):
    """Pour chaque jeu, tente un calcul d'EV a partir de ce qui a ete
    extrait. Rapporte explicitement l'absence de p et/ou m plutot que
    d'inventer une valeur -- c'est la regle non negociable de ce chantier."""
    games = tables["games"]
    report = {}

    def missing_report(game, missing_bits):
        return {
            "computable": False,
            "reason": (
                f"EV non calculable pour {game} : "
                + " et ".join(missing_bits)
                + " ne sont pas des valeurs litterales dans raw/games.txt "
                "(recuperees par le client via un appel /api/... au moment de "
                "l'execution, reponse non capturee dans ce fichier)."
            ),
        }

    # --- Plinko : table de gains par (rows, risk) entierement server-side.
    report["plinko"] = missing_report(
        "plinko", ["la probabilite d'atterrissage par case (physique + RNG serveur)",
                   "la table de multiplicateurs (info.plinko_tables)"]
    )

    # --- Mines : grille connue (25 cases), mais formule de multiplicateur
    # et house edge appliquee par le serveur non ecrites dans le client.
    grid, grid_ok = status_value(games["mines"]["grid_tiles"])
    report["mines"] = missing_report(
        "mines",
        ["la formule/table de multiplicateur exacte utilisee par le serveur "
         "(g.multiplier, g.payout renvoyes par /api/mines/pick)"],
    )
    if grid_ok:
        report["mines"]["known_structure"] = (
            f"grille de {grid} cases confirmee cote client, mais cela ne suffit "
            "pas a deduire le multiplicateur : sans le house edge applique par "
            "le serveur, aucune table combinatoire ne peut etre affirmee ici."
        )

    # --- Dragon tower : eggs/tiles par palier server-side.
    report["dragon_tower"] = missing_report(
        "dragon_tower",
        ["eggs et tiles par palier de difficulte (INFO.dragon.difficulties)",
         "la table de multiplicateurs par etage"],
    )

    # --- Cases : ponderation et table de gains server-side.
    report["cases"] = missing_report(
        "cases", ["les poids de tirage par palier (conf().weights)",
                  "la table de multiplicateurs par palier"]
    )

    # --- Keno : le concept de RTP est EXPLICITE cote client (c.rtp, c.chances)
    # mais aucune valeur numerique n'est jamais ecrite dans ce fichier statique.
    report["keno"] = missing_report(
        "keno",
        ["les probabilites par nombre de hits (INFO...[tier][picks].chances)",
         "le RTP par palier (INFO...[tier][picks].rtp)"],
    )
    report["keno"]["known_structure"] = (
        "fait notable : le CLIENT lui-meme affiche un pourcentage de RTP et une "
        "probabilite par nombre de hits (paintOdds() construit un tableau chance/"
        "cote a partir de c.chances et c.rtp) -- la notion existe cote produit, "
        "mais la valeur transite uniquement par la reponse JSON de "
        "/api/games/info, jamais capturee dans le HTML statique."
    )

    # --- Blackjack : regle de paiement 3:2 connue, mais pas assez pour un
    # house edge (deck count, regles croupier, strategie de base absentes).
    payout, payout_ok = status_value(games["blackjack"]["natural_blackjack_payout"])
    report["blackjack"] = missing_report(
        "blackjack",
        ["le nombre de jeux de cartes dans le sabot",
         "les regles du croupier (tire/reste sur 17 souple)",
         "les restrictions de double/split par main (booleens server-side par tour)"],
    )
    if payout_ok:
        report["blackjack"]["known_structure"] = (
            f"le paiement d'un blackjack naturel est confirme a {payout} par le "
            "texte client, mais un house edge de blackjack depend de l'ensemble "
            "des regles de table (nombre de sabots, regle du croupier, double "
            "apres split, etc.) -- aucune de ces regles n'est ecrite dans le client."
        )

    # --- Slots : paytable entierement construite depuis la reponse serveur.
    report["slots"] = missing_report(
        "slots",
        ["la table de symboles et leurs paiements (info.symbols[].pays)",
         "les poids de tirage par symbole/rouleau (jamais exposes, meme au serveur ne "
         "semblent pas lus par ce client)"],
    )

    # --- Coinflip : structure binaire connue, mais ni p ni m ne sont litteraux.
    report["coinflip"] = missing_report(
        "coinflip",
        ["le multiplicateur de gain (info.coinflip_multiplier, initialise a 0 "
         "puis ecrase par la reponse serveur)"],
    )
    report["coinflip"]["known_structure"] = (
        "le jeu est un choix binaire pile/face symetrique -- une piece equilibree "
        "(p=0.5) serait l'hypothese la plus naturelle, mais ce n'est PAS une valeur "
        "ecrite dans le fichier : l'affirmer comme donnee extraite serait deviner. "
        "Meme avec p=0.5 suppose, le multiplicateur reste totalement absent, donc "
        "aucun RTP n'est calculable dans tous les cas."
    )

    # --- Wheel : categories de mise connues, layout/payouts server-side.
    report["wheel"] = missing_report(
        "wheel",
        ["la disposition des segments (info.wheel.layout, donc la probabilite "
         "de chaque categorie)",
         "le multiplicateur exact paye par categorie (info.wheel.payouts)"],
    )

    # --- RPS : regles connues (tie = stake back), multiplicateur absent.
    report["rock_paper_scissors"] = missing_report(
        "rock_paper_scissors",
        ["le multiplicateur de gain contre la maison (info.rps_multiplier)"],
    )
    report["rock_paper_scissors"]["known_structure"] = (
        "contre la maison : 3 choix, egalite rendue (texte client confirme). Si "
        "la maison joue au hasard uniforme sur 3 choix, p(victoire)=1/3 et "
        "p(egalite)=1/3 seraient une consequence directe de la regle, mais rien "
        "dans le client ne confirme que la maison choisit uniformement -- et le "
        "multiplicateur de gain manque de toute facon. En PvP, un rake existe "
        "(texte \"less a X% rake\") mais sa valeur (info.rake_pct) n'est jamais "
        "litterale."
    )

    # --- Crash : parametres d'animation seulement, pas de distribution.
    report["crash"] = missing_report(
        "crash",
        ["la distribution du point de crash / house edge (les parametres "
         "growth/max captures ne sont qu'une courbe d'affichage, ecrasee par "
         "le serveur des la premiere reponse)"],
    )

    return report


def evaluate_rakeback(tables):
    rb = tables["rakeback"]
    rate, rate_ok = status_value(rb["rate_pct"])
    if not rate_ok:
        return {
            "computable": False,
            "reason": (
                "Le taux de rakeback (d.rate_pct) n'est jamais une valeur litterale "
                "dans raw/games.txt : il est renvoye par /api/rakeback a l'execution. "
                "Le formulaire de calcul (ev_with_rakeback) est pret et teste dans "
                "demo(), mais aucun taux reel n'est disponible depuis cette capture."
            ),
        }
    return {"computable": True, "rate_pct": rate}


def main():
    demo()
    print()

    tables = load_tables()
    games_report = evaluate_games(tables)
    rakeback_report = evaluate_rakeback(tables)

    computable = [g for g, r in games_report.items() if r["computable"]]
    not_computable = [g for g, r in games_report.items() if not r["computable"]]

    print(f"Jeux avec EV calculable depuis games_tables.json : {len(computable)} / {len(games_report)}")
    if computable:
        for g in computable:
            print(f"  - {g}: {games_report[g]}")
    print()
    print(f"Jeux SANS EV calculable ({len(not_computable)}) et pourquoi :")
    for g in not_computable:
        print(f"  - {g}")
        print(f"      {games_report[g]['reason']}")
        if "known_structure" in games_report[g]:
            print(f"      [ce qui EST connu] {games_report[g]['known_structure']}")
    print()
    print("Rakeback :")
    if rakeback_report["computable"]:
        print(f"  taux = {rakeback_report['rate_pct']}%")
    else:
        print(f"  {rakeback_report['reason']}")
    print()
    print(
        "VERDICT : aucun jeu de ce casino n'a, dans cette capture, a la fois une "
        "probabilite ET un multiplicateur litteraux cote client -- les deux "
        "transitent systematiquement par des reponses JSON de /api/games/info ou "
        "d'endpoints par jeu, jamais capturees dans raw/games.txt. Aucun house "
        "edge, aucun RTP, aucune esperance nette avec rakeback ne peuvent donc "
        "etre affirmes a partir de cette page seule. Une conclusion 'le rakeback "
        "compense/ne compense pas l'avantage de la maison' necessiterait de "
        "capturer au moins une reponse reelle de /api/games/info et /api/rakeback."
    )

    return {
        "games": games_report,
        "rakeback": rakeback_report,
    }


if __name__ == "__main__":
    main()
