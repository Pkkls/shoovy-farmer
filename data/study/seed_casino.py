"""Charge dans le magasin semantique les constantes structurelles du casino.

Extraites de la page casino du jeu (raw/games.txt, statique), via regex parsing.
Ces valeurs sont lues directement du code client delivre par le serveur :
constantes de grille, options de menu, ratios de regles affichees.

Ne sont JAMAIS chargees les probabilites, tables de gains, ou mises min/max,
qui sont recuperees par le client via fetch('/api/games/info') et ne figurent
pas dans ce fichier.

Re-runnable comme seed_commands.py: le magasin est append-only.
"""
import facts

METHOD_BASE = "Extrait du code client de la page casino (raw/games.txt), parsing regex"

F = []

# ================================================================ plinko ====
F += [
    dict(id="casino.plinko.row_options", subject="mechanic:casino_plinko",
         predicate="row_options", value=[8, 9, 10, 11, 12, 13, 14, 15, 16],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 1356",
         source="games_tables.json"),
    dict(id="casino.plinko.default_rows", subject="mechanic:casino_plinko",
         predicate="default_rows", value=16, unit="rangees",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 1361",
         source="games_tables.json"),
    dict(id="casino.plinko.default_risk", subject="mechanic:casino_plinko",
         predicate="default_risk", value="medium",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 1361",
         source="games_tables.json"),
    dict(id="casino.plinko.risk_levels", subject="mechanic:casino_plinko",
         predicate="risk_levels", value=["low", "medium", "high"],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 751",
         source="games_tables.json"),
]

# ================================================================= mines ====
F += [
    dict(id="casino.mines.grid_tiles", subject="mechanic:casino_mines",
         predicate="grid_tiles", value=25, unit="cases",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3030",
         source="games_tables.json"),
    dict(id="casino.mines.max_mines_selectable", subject="mechanic:casino_mines",
         predicate="max_mines_selectable", value=24, unit="mines",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3039",
         source="games_tables.json"),
    dict(id="casino.mines.default_mines", subject="mechanic:casino_mines",
         predicate="default_mines", value=3, unit="mines",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3042",
         source="games_tables.json"),
]

# ================================================================== keno ====
F += [
    dict(id="casino.keno.board_size", subject="mechanic:casino_keno",
         predicate="board_size", value=40, unit="nombres",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3706",
         source="games_tables.json"),
    dict(id="casino.keno.numbers_drawn_per_round", subject="mechanic:casino_keno",
         predicate="numbers_drawn_per_round", value=10, unit="nombres",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3829",
         source="games_tables.json"),
    dict(id="casino.keno.max_picks", subject="mechanic:casino_keno",
         predicate="max_picks", value=10, unit="nombres",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3694",
         source="games_tables.json"),
    dict(id="casino.keno.difficulty_tiers", subject="mechanic:casino_keno",
         predicate="difficulty_tiers", value=["classic", "low", "medium", "high"],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3687",
         source="games_tables.json"),
]

# ================================================================ cases ====
F += [
    dict(id="casino.cases.difficulty_tiers", subject="mechanic:casino_cases",
         predicate="difficulty_tiers",
         value=["easy", "medium", "hard", "expert", "master"],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3450",
         source="games_tables.json"),
]

# ============================================================ dragon_tower ====
F += [
    dict(id="casino.dragon_tower.difficulty_tiers", subject="mechanic:casino_dragon_tower",
         predicate="difficulty_tiers",
         value=["easy", "medium", "hard", "expert", "master"],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 3203",
         source="games_tables.json"),
]

# ================================================================ crash ====
F += [
    dict(id="casino.crash.animation_defaults", subject="mechanic:casino_crash",
         predicate="animation_defaults", value={"growth": 0.07, "max": 1000},
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 4355",
         source="games_tables.json"),
]

# ================================================================ slots ====
F += [
    dict(id="casino.slots.grid", subject="mechanic:casino_slots",
         predicate="grid", value={"reels": 6, "rows": 5},
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 1603",
         source="games_tables.json"),
]

# ============================================================== blackjack ====
F += [
    dict(id="casino.blackjack.natural_blackjack_payout", subject="mechanic:casino_blackjack",
         predicate="natural_blackjack_payout", value="3:2",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 2683",
         source="games_tables.json"),
]

# ================================================================ wheel ====
F += [
    dict(id="casino.wheel.bet_categories", subject="mechanic:casino_wheel",
         predicate="bet_categories", value=[1, 3, 5, 10, 20],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 4132",
         source="games_tables.json"),
]

# ================================================================ coinflip ====
F += [
    dict(id="casino.coinflip.sides", subject="mechanic:casino_coinflip",
         predicate="sides", value=["heads", "tails"],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, pattern de regex trouve (numéro de ligne non précisé)",
         source="games_tables.json"),
]

# ============================================================ rock_paper_scissors ====
F += [
    dict(id="casino.rock_paper_scissors.choices", subject="mechanic:casino_rock_paper_scissors",
         predicate="choices", value=["rock", "paper", "scissors"],
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, pattern de regex trouve (numéro de ligne non précisé)",
         source="games_tables.json"),
    dict(id="casino.rock_paper_scissors.tie_rule", subject="mechanic:casino_rock_paper_scissors",
         predicate="tie_rule", value="stake returned on tie",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 4698",
         source="games_tables.json"),
    dict(id="casino.rock_paper_scissors.pvp_pot_formula", subject="mechanic:casino_rock_paper_scissors",
         predicate="pvp_pot_formula", value="stake * 2",
         status="measured", confidence=0.9,
         method=f"{METHOD_BASE}, ligne 4732",
         source="games_tables.json"),
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
