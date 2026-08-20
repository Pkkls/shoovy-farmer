"""Banc d'essai pour la strategie de reversion a la moyenne sur le marche shoovy.

Le marche a 5 tickers (CHAT, GAMBA, LOSS, STRMR, WINS), un teneur de marche
automatise de profondeur 250000 credits et des frais de 1 % par transaction.
Ces trois valeurs sont MESUREES (market.jsonl) et servent de defaut. Le
cooldown serveur de 8 s entre deux transactions est HERITE de juillet et
n'a jamais ete revarifie contre le backend actuel: il est applique dans la
simulation mais reste marque comme non verifie dans le rapport.

Les parametres de strategie herites (fenetre 20, entree -3 %, sortie -0.5 %,
detention max 360 s, 150 credits/position, 6 positions max) ne sont qu'un
jeu de defauts parmi d'autres: `Params` est concu pour etre remplace, et
`grid_search` balaie autour d'eux.

Modele d'impact de prix (teneur de marche a profondeur finie)
---------------------------------------------------------------
La vraie formule interne du jeu n'est documentee nulle part dans ce depot
(raw/commands.txt confirme juste qualitativement "acheter fait monter le
prix", "vendre fait baisser le prix"). Faute de mieux on modelise le teneur
de marche comme un pool a produit constant (x*y=k, façon Uniswap), construit
a partir des deux seules quantites mesurees: le prix cote et la profondeur.

    reserve_credits = depth
    reserve_parts   = depth / prix_cote      (ainsi credits/parts = prix cote)
    k = reserve_credits * reserve_parts

Un achat de `credits_in` (apres frais) deplace reserve_credits -> +credits_in
et recalcule reserve_parts = k / nouveau reserve_credits; la difference de
parts est ce qu'on recoit. Une vente fait le trajet inverse. C'est une
APPROXIMATION explicitement etiquetee comme telle: elle a la bonne forme
(impact croissant et non lineaire avec la taille de l'ordre relative a la
profondeur, prix marginal qui tend vers le prix cote quand l'ordre est petit)
mais rien ne garantit que c'est la formule exacte du jeu.

Consequence pratique attendue: a 150 credits pour une profondeur de 250000,
l'ordre pese ~0.06 % de la profondeur, donc l'impact devrait etre minuscule
comparé aux frais de 1 %. Le rapport le confirme ou l'infirme avec les
vrais nombres plutot que de le supposer.

    python backtest.py       # backtest sur donnees reelles + grid search + rapport
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import deque
from dataclasses import dataclass, replace

HERE = os.path.dirname(os.path.abspath(__file__))
MARKET_JSONL = os.path.join(HERE, "market.jsonl")
HISTORY_JSON = os.path.join(HERE, "raw", "api_stocks_history.json")
REPORT_PATH = os.path.join(HERE, "backtest_report.txt")

SYMBOLS = ("CHAT", "GAMBA", "LOSS", "STRMR", "WINS")

# En dessous de ce nombre de points (par serie, tous symboles confondus) un
# backtest n'a mecaniquement aucune chance de calculer plus qu'une poignee de
# moyennes mobiles. Ce n'est pas un seuil statistique savant, juste le
# minimum pour que "resultat" veuille dire quelque chose plutot que du bruit
# sur 2-3 points.
MIN_POINTS_FOR_CONCLUSION = 50


# --------------------------------------------------------------------------
# Parametres de strategie
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Params:
    window: int = 20              # points de moyenne mobile (herite)
    entry_pct: float = -0.03      # entree quand (prix-MA)/MA <= ce seuil (herite)
    exit_pct: float = -0.005      # sortie quand (prix-MA)/MA >= ce seuil (herite)
    max_hold_s: int = 360         # ou sortie forcee apres ce temps de detention (herite)
    position_size: float = 150.0  # credits par position (herite)
    max_positions: int = 6        # positions simultanees max (herite)
    fee_pct: float = 0.01         # MESURE
    depth: float = 250000.0       # MESURE
    cooldown_s: float = 8.0       # herite, NON VERIFIE contre le backend actuel


HERITAGE = Params()


# --------------------------------------------------------------------------
# Chargement des donnees
# --------------------------------------------------------------------------

def load_market_series(path: str) -> dict[str, list[tuple[int, float]]]:
    """Lit market.jsonl (un objet JSON par ligne, voir market.py:snapshot).

    Le fichier est alimente en continu par un processus qui peut etre en
    train d'ecrire pendant qu'on le lit; une ligne coupee ou invalide est
    ignoree plutot que de faire planter tout le chargement.
    """
    series: dict[str, list[tuple[int, float]]] = {s: [] for s in SYMBOLS}
    if not os.path.exists(path):
        return series
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ts = int(obj["ts"])
                quotes = obj.get("quotes", {})
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            for sym, q in quotes.items():
                price = q.get("price") if isinstance(q, dict) else None
                if price is None:
                    continue
                series.setdefault(sym, []).append((ts, float(price)))
    return series


def _try_shapes(obj):
    """Essaie plusieurs formes plausibles pour /api/stocks/history et rend
    la premiere qui produit des series exploitables, ou None.

    Le fichier n'existe pas encore au moment d'ecrire ce script (aucun appel
    reussi n'a encore ete capture), donc son format n'a jamais ete observe.
    On ne le suppose pas: on essaie des formes raisonnables et on abandonne
    proprement si aucune ne correspond, plutot que de deviner une structure
    et planter dessus plus tard.
    """
    # Forme A: meme structure qu'une ligne de market.jsonl, en liste.
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "quotes" in obj[0]:
        out: dict[str, list[tuple[int, float]]] = {s: [] for s in SYMBOLS}
        for row in obj:
            ts = row.get("ts") or row.get("timestamp")
            quotes = row.get("quotes", {})
            if ts is None or not isinstance(quotes, dict):
                continue
            for sym, q in quotes.items():
                price = q.get("price") if isinstance(q, dict) else q
                if price is None:
                    continue
                out.setdefault(sym, []).append((int(ts), float(price)))
        if any(out.values()):
            return out

    # Forme B: dict symbole -> liste de points {ts|timestamp|t, price|p|close}.
    if isinstance(obj, dict) and any(k in obj for k in SYMBOLS):
        out = {s: [] for s in SYMBOLS}
        for sym, points in obj.items():
            if sym not in SYMBOLS or not isinstance(points, list):
                continue
            for p in points:
                if not isinstance(p, dict):
                    continue
                ts = p.get("ts", p.get("timestamp", p.get("t")))
                price = p.get("price", p.get("p", p.get("close")))
                if ts is None or price is None:
                    continue
                out[sym].append((int(ts), float(price)))
        if any(out.values()):
            return out

    # Forme C: wrapper {"data": ...} ou {"history": ...} ou {"quotes": ...}
    # autour de l'une des deux formes ci-dessus.
    if isinstance(obj, dict):
        for key in ("data", "history", "quotes", "results"):
            if key in obj:
                inner = _try_shapes(obj[key])
                if inner is not None:
                    return inner

    return None


def load_history_series(path: str) -> tuple[dict[str, list[tuple[int, float]]], str]:
    """Rend (series, message). series est {} si le fichier est absent ou
    illisible; message explique pourquoi, pour le rapport."""
    if not os.path.exists(path):
        return {}, "raw/api_stocks_history.json absent (aucun appel /api/stocks/history n'a encore reussi)"
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {}, f"raw/api_stocks_history.json illisible ({type(e).__name__}), ignore"
    shaped = _try_shapes(obj)
    if shaped is None:
        return {}, "raw/api_stocks_history.json present mais format non reconnu par les formes essayees, ignore"
    n = sum(len(v) for v in shaped.values())
    return shaped, f"raw/api_stocks_history.json charge: {n} points"


def merge_series(*sources: dict[str, list[tuple[int, float]]]) -> dict[str, list[tuple[int, float]]]:
    """Fusionne plusieurs series par symbole, deduplique par ts, trie."""
    merged: dict[str, dict[int, float]] = {s: {} for s in SYMBOLS}
    for src in sources:
        for sym, points in src.items():
            bucket = merged.setdefault(sym, {})
            for ts, price in points:
                bucket.setdefault(ts, price)
    return {sym: sorted(pts.items()) for sym, pts in merged.items()}


# --------------------------------------------------------------------------
# Modele de teneur de marche a produit constant (voir docstring du module)
# --------------------------------------------------------------------------

def amm_buy(depth: float, quoted_price: float, credits_in: float, fee_pct: float):
    """Achete `credits_in` credits au prix cote `quoted_price`. Rend
    (parts_recues, frais_preleves)."""
    fee_amt = credits_in * fee_pct
    net_in = credits_in - fee_amt
    reserve_credits = depth
    reserve_parts = depth / quoted_price
    k = reserve_credits * reserve_parts
    new_reserve_credits = reserve_credits + net_in
    new_reserve_parts = k / new_reserve_credits
    parts_out = reserve_parts - new_reserve_parts
    return parts_out, fee_amt


def amm_sell(depth: float, quoted_price: float, parts_in: float, fee_pct: float):
    """Vend `parts_in` parts au prix cote `quoted_price`. Rend
    (credits_recus_net, frais_preleves)."""
    reserve_credits = depth
    reserve_parts = depth / quoted_price
    k = reserve_credits * reserve_parts
    new_reserve_parts = reserve_parts + parts_in
    new_reserve_credits = k / new_reserve_parts
    credits_out_gross = reserve_credits - new_reserve_credits
    fee_amt = credits_out_gross * fee_pct
    return credits_out_gross - fee_amt, fee_amt


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------

@dataclass
class Trade:
    symbol: str
    entry_ts: int
    entry_price: float
    exit_ts: int | None
    exit_price: float | None
    realized: bool

    def pnl(self, position_size: float, fee_pct: float, depth: float):
        """Rend (pnl_brut, pnl_net_frais, pnl_net_impact) pour cette
        transaction. exit_price doit etre renseigne (reel si close, dernier
        prix observe si encore ouverte / valorisation a la marque)."""
        p_in, p_out = self.entry_price, self.exit_price
        credits_in = position_size

        # brut: execution au prix cote, sans frais ni impact.
        parts = credits_in / p_in
        pnl_gross = parts * p_out - credits_in

        # net de frais: prix cote, frais de 1 % preleves a l'achat et a la vente.
        net_in = credits_in * (1 - fee_pct)
        parts_f = net_in / p_in
        proceeds_f = parts_f * p_out * (1 - fee_pct)
        pnl_fees = proceeds_f - credits_in

        # net d'impact: execution via le teneur de marche a profondeur finie
        # (frais inclus dans le modele, voir amm_buy/amm_sell).
        parts_i, _ = amm_buy(depth, p_in, credits_in, fee_pct)
        proceeds_i, _ = amm_sell(depth, p_out, parts_i, fee_pct)
        pnl_impact = proceeds_i - credits_in

        return pnl_gross, pnl_fees, pnl_impact


def run_backtest(series: dict[str, list[tuple[int, float]]], params: Params) -> dict:
    """Simule la strategie de reversion a la moyenne sur une serie multi-
    symboles deja fusionnee et triee. Rend un dict de resultats.

    Interpretation retenue pour le seuil de sortie: comme le seuil d'entree,
    il est exprime en deviation par rapport a la moyenne mobile (pas par
    rapport au prix d'entree) — sortie quand le prix est revenu a moins de
    0.5 % sous la moyenne, ou apres le temps de detention max. C'est la
    lecture qui a un sens pour une strategie de reversion (on sort quand le
    prix a suffisamment reverti), l'autre lecture (deviation depuis le prix
    d'entree) reviendrait a sortir sur une nouvelle perte apres un achat sur
    repli, ce qui n'a pas de sens economique pour cette strategie.

    La moyenne mobile est calculee sur les N derniers POINTS observes, pas
    sur une fenetre de temps fixe: le marche ne repond qu'une fois sur six
    environ donc les points ne sont pas equidistants. Limite documentee, pas
    corrigee ici (corriger demanderait d'interpoler, donc d'inventer des prix).
    """
    events = []
    for sym, points in series.items():
        for ts, price in points:
            events.append((ts, sym, price))
    events.sort(key=lambda e: e[0])

    history = {s: deque(maxlen=params.window) for s in SYMBOLS}
    open_positions: list[Trade] = []
    closed_trades: list[Trade] = []
    last_trade_ts = None
    last_price = {}

    for ts, sym, price in events:
        last_price[sym] = price
        hist = history.setdefault(sym, deque(maxlen=params.window))
        hist.append(price)

        # sorties d'abord, pour liberer un slot avant de tenter une entree
        # au meme timestamp.
        still_open = []
        for pos in open_positions:
            if pos.symbol != sym:
                still_open.append(pos)
                continue
            held_s = ts - pos.entry_ts
            ma = statistics.fmean(hist) if len(hist) == params.window else None
            deviation = (price - ma) / ma if ma else None
            should_exit = held_s >= params.max_hold_s or (
                deviation is not None and deviation >= params.exit_pct
            )
            if should_exit:
                pos.exit_ts, pos.exit_price, pos.realized = ts, price, True
                closed_trades.append(pos)
                last_trade_ts = ts
            else:
                still_open.append(pos)
        open_positions = still_open

        if len(hist) < params.window:
            continue
        ma = statistics.fmean(hist)
        deviation = (price - ma) / ma
        cooldown_ok = last_trade_ts is None or (ts - last_trade_ts) >= params.cooldown_s
        if (
            deviation <= params.entry_pct
            and len(open_positions) < params.max_positions
            and cooldown_ok
        ):
            open_positions.append(
                Trade(symbol=sym, entry_ts=ts, entry_price=price,
                      exit_ts=None, exit_price=None, realized=False)
            )
            last_trade_ts = ts

    # positions encore ouvertes en fin de serie: valorisees au dernier prix
    # observe pour ce symbole (marque a la fin, non realise).
    unrealized = []
    for pos in open_positions:
        pos.exit_ts = pos.entry_ts  # inconnu, non utilise pour le pnl
        pos.exit_price = last_price.get(pos.symbol, pos.entry_price)
        pos.realized = False
        unrealized.append(pos)

    all_trades = closed_trades + unrealized
    gross = fees = impact = 0.0
    per_trade_impact = []
    for t in all_trades:
        g, f, i = t.pnl(params.position_size, params.fee_pct, params.depth)
        gross += g
        fees += f
        impact += i
        per_trade_impact.append(i)

    n_realized = len(closed_trades)
    wins = sum(1 for t in closed_trades
               if t.pnl(params.position_size, params.fee_pct, params.depth)[2] > 0)
    win_rate = wins / n_realized if n_realized else None
    worst_loss = min(per_trade_impact) if per_trade_impact else None

    return {
        "n_trades": len(all_trades),
        "n_realized": n_realized,
        "n_unrealized": len(unrealized),
        "gross_pnl": gross,
        "net_fees_pnl": fees,
        "net_impact_pnl": impact,
        "win_rate": win_rate,
        "worst_loss": worst_loss,
        "params": params,
    }


def buy_and_hold(series: dict[str, list[tuple[int, float]]], total_capital: float,
                  fee_pct: float, depth: float) -> dict:
    """Reference: repartit `total_capital` a parts egales entre les symboles
    qui ont au moins 2 points, achete au premier prix observe, valorise
    (non realise) au dernier prix observe. Une seule execution d'achat par
    symbole donc un seul aller de frais/impact, pas de vente."""
    usable = [s for s, pts in series.items() if len(pts) >= 2]
    if not usable:
        return {"pnl_gross": None, "pnl_fees": None, "pnl_impact": None, "symbols": []}
    per_symbol = total_capital / len(usable)
    gross = fees = impact = 0.0
    for sym in usable:
        pts = series[sym]
        p_in, p_out = pts[0][1], pts[-1][1]
        parts = per_symbol / p_in
        gross += parts * p_out - per_symbol

        net_in = per_symbol * (1 - fee_pct)
        parts_f = net_in / p_in
        fees += parts_f * p_out - per_symbol

        parts_i, _ = amm_buy(depth, p_in, per_symbol, fee_pct)
        impact += parts_i * p_out - per_symbol
    return {"pnl_gross": gross, "pnl_fees": fees, "pnl_impact": impact, "symbols": usable}


# --------------------------------------------------------------------------
# Grid search
# --------------------------------------------------------------------------

def grid_search(series: dict[str, list[tuple[int, float]]], base: Params) -> list[dict]:
    windows = (10, 15, 20, 30)
    entries = (-0.01, -0.02, -0.03, -0.04, -0.05)
    exits = (-0.02, -0.01, -0.005, 0.0)
    holds = (120, 240, 360, 600)

    results = []
    for w in windows:
        for e in entries:
            for x in exits:
                for h in holds:
                    p = replace(base, window=w, entry_pct=e, exit_pct=x, max_hold_s=h)
                    r = run_backtest(series, p)
                    results.append(r)
    results.sort(key=lambda r: r["net_impact_pnl"], reverse=True)
    return results


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

def _fmt(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def build_report(real_series: dict[str, list[tuple[int, float]]],
                  history_msg: str) -> str:
    lines = []
    add = lines.append

    n_points = {s: len(pts) for s, pts in real_series.items()}
    total_points = sum(n_points.values())

    add("=" * 72)
    add("BACKTEST — strategie de reversion a la moyenne, marche shoovy.wtf")
    add("=" * 72)
    add("")
    add("Parametres herites evalues (defauts de Params, jamais revarifies depuis juillet):")
    add(f"  fenetre MA={HERITAGE.window}  entree={HERITAGE.entry_pct:.1%}  "
        f"sortie={HERITAGE.exit_pct:.1%}  detention max={HERITAGE.max_hold_s}s  "
        f"position={HERITAGE.position_size:.0f} credits  max positions={HERITAGE.max_positions}")
    add(f"  mesures (fiables): frais={HERITAGE.fee_pct:.0%}  profondeur AMM={HERITAGE.depth:.0f} credits")
    add(f"  herite non verifie: cooldown serveur={HERITAGE.cooldown_s:.0f}s")
    add("")
    add("-" * 72)
    add("DONNEES DISPONIBLES")
    add("-" * 72)
    add(f"  market.jsonl: {n_points} (total {total_points} points, {len(SYMBOLS)} tickers)")
    add(f"  {history_msg}")
    add("")

    insufficient = total_points < MIN_POINTS_FOR_CONCLUSION or total_points < HERITAGE.window + 1
    if total_points < HERITAGE.window + 1:
        add(f"  ECHANTILLON INSUFFISANT: {total_points} point(s) au total, il en faut au moins "
            f"{HERITAGE.window + 1} rien que pour calculer UNE moyenne mobile sur {HERITAGE.window} "
            "points. Aucun signal d'entree/sortie n'a pu etre evalue.")
        add("  Aucun backtest, aucun grid search, aucune conclusion : ce n'est pas un resultat,")
        add("  c'est l'absence de resultat. market.py doit continuer a tourner avant de reessayer.")
        add("")
        add("=" * 72)
        add("VERDICT")
        add("=" * 72)
        add("  Impossible de dire si la strategie heritee bat le buy-and-hold : il n'y a pas")
        add("  assez de donnees reelles pour faire tourner ne serait-ce qu'une seule fenetre de")
        add("  moyenne mobile. La mecanique du backtest est verifiee (voir demo()), mais elle")
        add("  n'a rien a mordre cote donnees reelles pour l'instant.")
        return "\n".join(lines)

    if insufficient:
        add(f"  ECHANTILLON FAIBLE: {total_points} points, sous le seuil de "
            f"{MIN_POINTS_FOR_CONCLUSION} retenu pour qu'un resultat soit autre chose que du bruit.")
        add("  Les chiffres ci-dessous sont calcules mais NE DOIVENT PAS etre lus comme concluants.")
        add("")

    result = run_backtest(real_series, HERITAGE)
    capital = HERITAGE.position_size * HERITAGE.max_positions
    bh = buy_and_hold(real_series, capital, HERITAGE.fee_pct, HERITAGE.depth)

    add("-" * 72)
    add("STRATEGIE HERITEE SUR DONNEES REELLES")
    add("-" * 72)
    add(f"  transactions: {result['n_trades']}  "
        f"(realisees={result['n_realized']}, encore ouvertes en fin de periode={result['n_unrealized']})")
    add(f"  pnl brut          : {_fmt(result['gross_pnl'])} credits")
    add(f"  pnl net de frais   : {_fmt(result['net_fees_pnl'])} credits")
    add(f"  pnl net d'impact   : {_fmt(result['net_impact_pnl'])} credits")
    add(f"  taux de reussite   : {_fmt(result['win_rate'], 1) if result['win_rate'] is None else f'{result['win_rate']:.1%}'}")
    add(f"  pire perte (1 transaction, net d'impact): {_fmt(result['worst_loss'])} credits")
    add("")
    add(f"  reference buy-and-hold (meme capital engage, {capital:.0f} credits, "
        f"reparti sur {len(bh['symbols'])} tickers):")
    add(f"    pnl brut         : {_fmt(bh['pnl_gross'])} credits")
    add(f"    pnl net de frais : {_fmt(bh['pnl_fees'])} credits")
    add(f"    pnl net d'impact : {_fmt(bh['pnl_impact'])} credits")
    add("")

    if bh["pnl_impact"] is not None:
        beats = result["net_impact_pnl"] > bh["pnl_impact"]
        add("  VERDICT: la strategie heritee "
            + ("BAT" if beats else "NE BAT PAS")
            + " le buy-and-hold sur cette periode (comparaison net d'impact).")
        if not beats:
            add("  Une strategie qui ne bat pas la reference n'a aucun interet a etre relancee")
            add("  telle quelle, meme si elle est individuellement rentable.")
    add("")

    if insufficient:
        add("  Grid search NON EXECUTE en conclusion faute d'echantillon suffisant (voir plus")
        add("  haut). Il tourne quand meme ci-dessous a titre indicatif uniquement.")
        add("")

    grid = grid_search(real_series, HERITAGE)
    add("-" * 72)
    add(f"GRID SEARCH ({len(grid)} combinaisons, classees par pnl net d'impact)")
    add("-" * 72)
    add("  top 5:")
    for r in grid[:5]:
        p = r["params"]
        add(f"    fenetre={p.window:>2} entree={p.entry_pct:>+.2%} sortie={p.exit_pct:>+.2%} "
            f"hold={p.max_hold_s:>4}s -> net_impact={_fmt(r['net_impact_pnl'])} "
            f"({r['n_trades']} trades)")
    heritage_rank = next(
        (i for i, r in enumerate(grid, 1)
         if (r["params"].window, r["params"].entry_pct, r["params"].exit_pct, r["params"].max_hold_s)
         == (HERITAGE.window, HERITAGE.entry_pct, HERITAGE.exit_pct, HERITAGE.max_hold_s)),
        None,
    )
    if heritage_rank is not None:
        add(f"  jeu de parametres herite: rang {heritage_rank}/{len(grid)}")
        if heritage_rank > len(grid) // 2:
            add("  Il est dans la moitie basse du balayage: l'optimum de juillet ne tient")
            add("  pas particulierement mieux que d'autres reglages sur cet echantillon.")
    add("")

    add("-" * 72)
    add("LIMITES A GARDER EN TETE")
    add("-" * 72)
    add("  - cooldown de 8s: herite, jamais revarifie contre le backend actuel.")
    add("  - impact de prix: modele produit-constant approxime a partir de (prix cote,")
    add("    profondeur), formule reelle du jeu non documentee dans ce depot.")
    add("  - moyenne mobile calculee sur les N derniers POINTS, pas sur une fenetre de")
    add("    temps fixe (le serveur ne repond qu'une fois sur six environ).")
    add("  - seuil de sortie interprete comme une deviation par rapport a la moyenne")
    add("    mobile (comme le seuil d'entree), pas par rapport au prix d'entree.")
    if insufficient:
        add("  - ECHANTILLON INSUFFISANT: tout ce qui precede est a reevaluer une fois que")
        add("    market.jsonl aura accumule assez de points (seuil retenu ici: "
            f"{MIN_POINTS_FOR_CONCLUSION}).")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# demo() — verifie la mecanique sur des series synthetiques, sans donnees reelles
# --------------------------------------------------------------------------

def _synthetic_flat(n=40, price=100.0, step=30):
    return [(i * step, price) for i in range(n)]


def _synthetic_sawtooth(n=200, base=100.0, amp=0.06, period=20, step=30):
    return [(i * step, base * (1 + amp * math.sin(2 * math.pi * i / period)))
            for i in range(n)]


def _synthetic_uptrend(n=60, base=100.0, growth=0.004, step=30):
    return [(i * step, base * (1 + growth * i)) for i in range(n)]


def demo():
    p = HERITAGE

    # --- serie plate: aucune deviation possible, aucune transaction. ---
    flat = {"CHAT": _synthetic_flat()}
    r_flat = run_backtest(flat, p)
    assert r_flat["n_trades"] == 0, r_flat
    assert r_flat["gross_pnl"] == 0.0 and r_flat["net_impact_pnl"] == 0.0, r_flat

    # --- dents de scie autour d'une moyenne: doit produire des transactions. ---
    saw = {"CHAT": _synthetic_sawtooth()}
    r_saw = run_backtest(saw, p)
    assert r_saw["n_trades"] > 0, r_saw
    # les couts ne font que reduire le pnl, jamais l'ameliorer.
    assert r_saw["gross_pnl"] >= r_saw["net_fees_pnl"] - 1e-9 >= r_saw["net_impact_pnl"] - 1e-9, r_saw

    # --- montee droite: la reversion n'entre jamais, perd contre buy-and-hold. ---
    up = {"CHAT": _synthetic_uptrend()}
    r_up = run_backtest(up, p)
    assert r_up["n_trades"] == 0, r_up
    bh_up = buy_and_hold(up, p.position_size * p.max_positions, p.fee_pct, p.depth)
    assert bh_up["pnl_impact"] > 0, bh_up
    assert r_up["net_impact_pnl"] < bh_up["pnl_impact"], (r_up, bh_up)

    # --- AMM: acheter coute plus cher que le prix cote, vendre rapporte moins. ---
    parts, _ = amm_buy(depth=250000.0, quoted_price=100.0, credits_in=150.0, fee_pct=0.01)
    buy_avg_price = 150.0 / parts
    assert buy_avg_price > 100.0, buy_avg_price
    credits_out, _ = amm_sell(depth=250000.0, quoted_price=100.0, parts_in=parts, fee_pct=0.01)
    assert credits_out < 150.0, credits_out
    # a 150 credits pour 250000 de profondeur l'ordre est ~0.06% de la profondeur:
    # l'impact doit rester tres petit face aux frais de 1%.
    assert (buy_avg_price - 100.0) / 100.0 < p.fee_pct, buy_avg_price

    # --- chargement d'un historique absent: pas de crash, message explicite. ---
    series, msg = load_history_series(os.path.join(HERE, "raw", "__inexistant__.json"))
    assert series == {}, series
    assert "absent" in msg, msg

    print("demo: tous les controles passent")


if __name__ == "__main__":
    demo()

    real_market = load_market_series(MARKET_JSONL)
    real_history, history_msg = load_history_series(HISTORY_JSON)
    real_series = merge_series(real_history, real_market)

    report = build_report(real_series, history_msg)
    print()
    print(report)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nrapport ecrit: {REPORT_PATH}")

    sys.exit(0)
