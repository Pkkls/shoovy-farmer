"""
Extraction des constantes de jeu du casino shoovy.wtf a partir de la capture
statique raw/games.txt (page /casino, HTML + JS inline).

Principe : ce script ne calcule rien et n'invente rien. Il localise dans le
texte du fichier les valeurs numeriques et objets de configuration que le
client JavaScript connait *litteralement* (grilles, options de menu, ratios
de paiement ecrits en dur, etc.), et separe explicitement cela de ce que le
client va chercher au moment de l'execution via fetch("/api/..."), dont ce
fichier statique ne contient jamais la reponse.

Si un pattern attendu n'est pas trouve dans le fichier, le champ correspondant
est mis a null avec une note "not_found" -- jamais une valeur devinee.

Sortie : games_tables.json
"""

import json
import re
import sys
from pathlib import Path

RAW_PATH = Path(__file__).parent / "raw" / "games.txt"
OUT_PATH = Path(__file__).parent / "games_tables.json"


def load_raw():
    text = RAW_PATH.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return text, lines


def find_first(pattern, text, flags=0):
    """Retourne (match_object, line_no) ou (None, None). line_no est 1-based."""
    m = re.search(pattern, text, flags)
    if not m:
        return None, None
    line_no = text.count("\n", 0, m.start()) + 1
    return m, line_no


def missing(reason):
    return {"value": None, "status": "not_found", "reason": reason}


def found(value, line_no, note=None):
    d = {"value": value, "status": "found_in_client", "line": line_no}
    if note:
        d["note"] = note
    return d


# ---------------------------------------------------------------------------
# Decoupage du fichier en sections de jeu, sur les separateurs commentaires
# "/* ================= NOM ================= */" qui bornent chaque IIFE
# de jeu dans la partie <script> du fichier. Permet de scanner, par jeu,
# quels champs "info.X" / "INFO.X" / "d.X" / "g.X" / "c.X" sont lus depuis
# une reponse serveur -- c'est-a-dire quels champs existent cote serveur
# mais dont ce fichier ne contient jamais la valeur.
# ---------------------------------------------------------------------------
SECTION_RE = re.compile(r"/\*\s*=+\s*([^=\n]+?)\s*=+", re.MULTILINE)


def split_sections(text):
    matches = list(SECTION_RE.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.setdefault(name, "")
        sections[name] += text[start:end]
    return sections


SERVER_FIELD_RE = re.compile(r"\b(?:info|INFO|d|g|c|r)\.([a-zA-Z_][a-zA-Z0-9_]*)")
FETCH_RE = re.compile(r"fetch\(\s*['\"]([^'\"]+)['\"]")


def server_surface(section_text):
    """Endpoints appeles + noms de champs lus sur les objets de reponse.
    C'est un inventaire de ce que le CLIENT SAIT QUI EXISTE cote serveur,
    pas des valeurs -- la valeur n'est jamais dans ce fichier statique."""
    endpoints = sorted(set(FETCH_RE.findall(section_text)))
    fields = sorted(set(SERVER_FIELD_RE.findall(section_text)))
    # bruit DOM/js courant a ecarter (pas des champs de reponse serveur)
    noise = {
        "value", "disabled", "textContent", "className", "style", "min",
        "max", "checked", "target", "addEventListener", "onclick", "length",
        "toFixed", "toLocaleString", "children", "appendChild", "classList",
        "innerHTML", "querySelector", "dataset", "closest", "remove", "id",
        "round", "toString", "slice", "map", "join", "forEach", "push",
        "then", "catch", "json", "ok", "ceil", "floor", "abs", "max2",
        # bruit Canvas2D/Pixi/WebAudio : variables courtes (c, g, r, d) reutilisees
        # pour des contextes graphiques/audio ailleurs dans la meme section, pas
        # des champs de reponse serveur
        "beginFill", "drawCircle", "drawRect", "endFill", "lineStyle",
        "connect", "createBiquadFilter", "createBuffer", "createBufferSource",
        "createGain", "createOscillator", "currentTime", "sampleRate", "gain",
        "blur", "container", "destroy", "position", "previousPosition",
        "velocity", "spinUntil", "key", "label",
    }
    fields = [f for f in fields if f not in noise]
    return endpoints, fields


def extract_plinko(text, sections):
    out = {}
    m, ln = find_first(r"const rowOptions\s*=\s*\[([^\]]+)\]", text)
    out["row_options"] = (
        found([int(x) for x in m.group(1).split(",")], ln)
        if m else missing("rowOptions array not found")
    )
    m, ln = find_first(r"rowCount:\s*(\d+)", text)
    out["default_rows"] = found(int(m.group(1)), ln) if m else missing("default rowCount not found")
    m, ln = find_first(r"risk:\s*'(\w+)'", text)
    out["default_risk"] = found(m.group(1), ln) if m else missing("default risk not found")
    m, ln = find_first(
        r'<select id="riskLevel">(.*?)</select>', text, re.DOTALL
    )
    if m:
        opts = re.findall(r'<option value="(\w+)"', m.group(1))
        out["risk_levels"] = found(opts, ln)
    else:
        out["risk_levels"] = missing("riskLevel <select> not found")
    out["payout_tables"] = missing(
        "st.tables = info.plinko_tables -- table de gains par (rows, risk) "
        "recuperee via fetch('/api/games/info'), reponse non capturee dans ce fichier"
    )
    out["bet_min"] = missing("info.bet_min -- valeur fournie par /api/games/info, non litterale ici")
    out["bet_max"] = missing("aucun champ bet_max reference cote client dans ce fichier")
    return out


def extract_mines(text, sections):
    out = {}
    m, ln = find_first(r"for \(let i = 0; i < (\d+); i\+\+\) \{\s*\n\s*const t = document\.createElement\(\"button\"\);\s*\n\s*t\.className = \"mn-tile", text)
    out["grid_tiles"] = found(int(m.group(1)), ln, "grille = 5x5 (repeat(5,1fr) en CSS)") if m else missing("mines tile loop not found")
    m, ln = find_first(r"for \(let m = 1; m <= (\d+); m\+\+\) \{", text)
    out["max_mines_selectable"] = found(int(m.group(1)), ln) if m else missing("mine count option loop not found")
    m, ln = find_first(r"if \(m === (\d+)\) o\.selected = true;", text)
    out["default_mines"] = found(int(m.group(1)), ln) if m else missing("default mine count not found")
    out["multiplier_table"] = missing(
        "multiplicateur/paiement calcule et renvoye par le serveur a chaque pick "
        "(g.multiplier, g.payout, g.safe_pct via /api/mines/*) -- pas de formule ni de "
        "table litterale dans le client"
    )
    return out


def extract_dragon_tower(text, sections):
    out = {}
    sec = sections.get("DRAGON TOWER", "")
    m, ln = find_first(r'const LABELS = \{\s*easy: "Easy", medium: "Medium", hard: "Hard",\s*\n\s*expert: "Expert", master: "Master" \};', text)
    out["difficulty_tiers"] = (
        found(["easy", "medium", "hard", "expert", "master"], ln)
        if m else missing("dragon tower LABELS object not found")
    )
    m, ln = find_first(r"const conf = \(\) => INFO\.difficulties\[sel\.value\]", sec)
    out["win_probability_formula"] = found(
        "eggs / tiles (par ligne)", ln,
        "formule utilisee par le client pour l'affichage (conf().eggs / conf().tiles * 100) -- "
        "les valeurs eggs/tiles elles-memes viennent de INFO.dragon.difficulties[name], "
        "fournies par /api/games/info, jamais litterales ici"
    ) if m else missing("eggs/tiles probability display formula not found")
    out["eggs_tiles_per_difficulty"] = missing(
        "INFO.dragon.difficulties[name] = {eggs, tiles, multipliers, ...} "
        "recupere via fetch('/api/games/info'), reponse non capturee"
    )
    out["multiplier_ladder"] = missing("d.multipliers[] par palier -- server-only")
    return out


def extract_cases(text, sections):
    out = {}
    m, ln = find_first(r'const LABELS = \{\s*easy: "Easy", medium: "Medium", hard: "Hard",\s*\n\s*expert: "Expert", master: "Master" \};\s*\n\s*const SPIN_MS', text)
    out["difficulty_tiers"] = (
        found(["easy", "medium", "hard", "expert", "master"], ln)
        if m else missing("cases LABELS object not found")
    )
    out["weights_per_tier"] = missing(
        "conf().weights = INFO.difficulties[name].weights -- ponderation du tirage "
        "recuperee via /api/games/info, jamais litterale ici"
    )
    out["colours_per_tier"] = missing("COLOURS = INFO.colours -- server-only")
    out["payout_multipliers"] = missing("aucune table de gains cases litterale dans le client")
    return out


def extract_keno(text, sections):
    out = {}
    m, ln = find_first(r"for \(let n = 1; n <= (\d+); n\+\+\) \{\s*\n\s*const c = document\.createElement", text)
    out["board_size"] = found(int(m.group(1)), ln) if m else missing("keno board loop not found")
    m, ln = find_first(r"Ten of the forty numbers are drawn every", text)
    out["numbers_drawn_per_round"] = found(10, ln, 'texte client: "Ten of the forty numbers are drawn every round"') if m else missing("draw count string not found")
    m, ln = find_first(r"let INFO = null, MAX = (\d+);", text)
    out["max_picks"] = found(int(m.group(1)), ln) if m else missing("MAX picks constant not found")
    m, ln = find_first(r"const LABELS = \{ classic: \"Classic\", low: \"Low\", medium: \"Medium\", high: \"High\" \};", text)
    out["difficulty_tiers"] = found(["classic", "low", "medium", "high"], ln) if m else missing("keno LABELS not found")
    out["multipliers_chances_rtp"] = missing(
        "INFO.difficulties[tier][pickCount] = {multipliers[], chances[], rtp} -- le client "
        "affiche explicitement une probabilite (c.chances[k]) et un RTP (c.rtp) par palier "
        "de hits, MAIS ces objets sont recuperes via fetch('/api/games/info') ; ce fichier "
        "statique ne contient jamais la reponse JSON, donc aucune valeur numerique n'est "
        "recuperable ici malgre le fait que le concept de RTP soit explicite cote client"
    )
    return out


def extract_blackjack(text, sections):
    out = {}
    m, ln = find_first(r"blackjack: \"BLACKJACK! Paid 3:2", text)
    out["natural_blackjack_payout"] = (
        found("3:2", ln, 'chaine client: "BLACKJACK! Paid 3:2"') if m else missing("blackjack payout string not found")
    )
    out["deck_count"] = missing("nombre de jeux de cartes dans le sabot non ecrit dans le client")
    out["dealer_rules"] = missing("regle du croupier (hit/stand soft 17) non ecrite dans le client")
    out["double_split_restrictions"] = missing(
        "can_double / can_split sont des booleens renvoyes par le serveur par main "
        "(game.can_double, game.can_split), pas une regle fixe lisible dans le client"
    )
    return out


def extract_slots(text, sections):
    out = {}
    m, ln = find_first(r"const REELS = (\d+), ROWS = (\d+), BAND", text)
    out["grid"] = found({"reels": int(m.group(1)), "rows": int(m.group(2))}, ln) if m else missing("REELS/ROWS constants not found")
    out["symbols_paytable"] = missing(
        "info.symbols[].pays, info.scatter_pays, info.fs_award, info.fs_mult -- la table de "
        "gains est *construite dynamiquement* dans buildPaytable(info) a partir de la reponse "
        "de /api/games/info ; aucun symbole, aucune valeur de paiement n'est ecrit en dur "
        "dans le HTML/JS capture"
    )
    out["scatter_id"] = missing("info.scatter_id -- server-only")
    return out


def extract_coinflip(text, sections):
    out = {}
    out["sides"] = found(["heads", "tails"], None, "deux issues nommees en dur (heads/tails), choix binaire")
    out["payout_multiplier"] = missing(
        "info.coinflip_multiplier recupere via /api/games/info -- variable payoutMult "
        "initialisee a 0 puis ecrasee par la reponse serveur, jamais de valeur litterale"
    )
    out["win_probability"] = missing(
        "aucune probabilite n'est ecrite dans le client. Le mecanisme (pile/face, un seul "
        "choix) suggere une piece equilibree mais ce n'est pas une valeur extraite -- "
        "affirmer p=0.5 serait une supposition, pas une lecture du fichier"
    )
    return out


def extract_wheel(text, sections):
    out = {}
    m, ln = find_first(r'const COLORS = \{ 1: "[^"]+", 3: "[^"]+", 5: "[^"]+", 10: "[^"]+", 20: "[^"]+" \};', text)
    out["bet_categories"] = (
        found([1, 3, 5, 10, 20], ln, "cles de l'objet COLORS/TEXT utilise pour l'affichage")
        if m else missing("wheel COLORS object not found")
    )
    out["segment_layout"] = missing("st.layout = info.wheel.layout -- disposition des segments, server-only")
    out["payouts_per_category"] = missing("st.payouts = info.wheel.payouts -- server-only")
    return out


def extract_rps(text, sections):
    out = {}
    out["choices"] = found(["rock", "paper", "scissors"], None, "objets GLYPH/NAME en dur")
    m, ln = find_first(r"a tie gives your stake back", text)
    out["tie_rule"] = found("stake returned on tie", ln, 'texte client: "a tie gives your stake back"') if m else missing("tie rule string not found")
    out["payout_multiplier"] = missing("info.rps_multiplier -- server-only, initialise a 0 dans le client")
    m, ln = find_first(r"pot <b>\$\{fmt\(s\.stake \* 2\)\}", text)
    out["pvp_pot_formula"] = found("stake * 2", ln, "pot PvP = mise du joueur * 2 (les deux joueurs misent la meme somme)") if m else missing("pvp pot formula not found")
    m, ln = find_first(r"info\.rake_pct", text)
    out["pvp_rake_pct"] = missing("info.rake_pct -- l'existence d'un rake PvP est confirmee par le texte client (\"less a X% rake\") mais la valeur n'est jamais litterale") if m else missing("no rake_pct reference found")
    return out


def extract_crash(text, sections):
    out = {}
    m, ln = find_first(r"growth: ([\d.]+), max: (\d+)", text)
    out["animation_defaults"] = (
        found({"growth": float(m.group(1)), "max": int(m.group(2))}, ln,
              "st.growth/st.max sont des parametres de COURBE D'ANIMATION cote client "
              "(mult = exp(growth*elapsed)), pas une distribution de probabilite. "
              "Ecrases par data.growth / d.state.growth des la premiere reponse serveur. "
              "Ne permettent PAS de deduire la probabilite de crash ni le house edge.")
        if m else missing("growth/max defaults not found")
    )
    out["crash_point_distribution"] = missing(
        "le point de crash est tire par le serveur (/api/crash/start, /api/crash/state) ; "
        "aucune distribution ni aucun house edge n'est ecrit dans le client"
    )
    return out


def extract_rakeback(text, sections):
    out = {}
    m, ln = find_first(r"const d = await \(await fetch\(\"/api/rakeback\"\)\)\.json\(\);", text)
    out["endpoint"] = found("/api/rakeback", ln) if m else missing("rakeback endpoint not found")
    out["rate_pct"] = missing(
        "d.rate_pct -- utilise dans plusieurs chaines d'aide (\"{d.rate_pct}% of everything "
        "you wager...\") mais TOUJOURS comme variable de reponse serveur, jamais une valeur "
        "litterale (ex: 5, 10) ecrite dans le HTML/JS"
    )
    out["cooldown_hours"] = missing("d.cooldown_hours -- server-only, jamais litteral")
    out["min_claim"] = missing("d.min_claim -- server-only, jamais litteral")
    out["tiers"] = missing("aucun palier de rakeback (ex: par niveau de badge) n'est ecrit dans le client")
    return out


def build():
    text, lines = load_raw()
    sections = split_sections(text)

    games = {
        "plinko": extract_plinko(text, sections),
        "mines": extract_mines(text, sections),
        "dragon_tower": extract_dragon_tower(text, sections),
        "cases": extract_cases(text, sections),
        "keno": extract_keno(text, sections),
        "blackjack": extract_blackjack(text, sections),
        "slots": extract_slots(text, sections),
        "coinflip": extract_coinflip(text, sections),
        "wheel": extract_wheel(text, sections),
        "rock_paper_scissors": extract_rps(text, sections),
        "crash": extract_crash(text, sections),
    }

    # inventaire "ce que le client sait exister cote serveur" par section JS
    server_surface_by_game = {}
    section_name_map = {
        "plinko": "PLINKO",
        "slots": 'SLOTS — "Le Shoovy"',
        "blackjack": "BLACKJACK",
        "mines": "MINES",
        "dragon_tower": "DRAGON TOWER",
        "cases": "CASES",
        "keno": "KENO",
        "coinflip": "COIN FLIP",
        "wheel": "WHEEL",
        "crash": "CRASH",
        "rock_paper_scissors": "ROCK PAPER SCISSORS",
    }
    for game, sec_name in section_name_map.items():
        sec_text = sections.get(sec_name)
        if sec_text is None:
            server_surface_by_game[game] = {"endpoints": [], "fields": [], "note": "section not found by header split"}
            continue
        endpoints, fields = server_surface(sec_text)
        server_surface_by_game[game] = {"endpoints": endpoints, "fields": fields}

    rakeback = extract_rakeback(text, sections)
    rb_endpoints, rb_fields = server_surface(text[text.find('STAKE RAKEBACK'):text.find('PLINKO ')] if 'STAKE RAKEBACK' in text else "")

    output = {
        "_meta": {
            "source_file": "raw/games.txt",
            "source_bytes": len(text.encode("utf-8")),
            "source_lines": len(lines),
            "method": (
                "Parsing regex du HTML/JS statique. Chaque valeur porte soit "
                "status=found_in_client (valeur litterale localisee, avec numero de ligne), "
                "soit status=not_found (le pattern attendu n'apparait pas dans le fichier -- "
                "champ marque manquant explicitement, aucune valeur devinee)."
            ),
            "central_finding": (
                "La quasi-totalite des donnees economiques (tables de multiplicateurs, "
                "probabilites/chances, RTP, taux de rakeback, mises min/max, poids de tirage) "
                "sont recuperees par le client au chargement via fetch('/api/games/info') ou "
                "des endpoints par jeu (/api/mines/*, /api/dragon/*, /api/rakeback, ...). Ce "
                "fichier est une capture STATIQUE du HTML/JS envoye par le serveur ; il ne "
                "contient JAMAIS la reponse JSON de ces appels. Le client est un pur moteur "
                "de rendu pour des donnees calculees et gardees cote serveur -- ce que ce "
                "fichier peut documenter, ce sont les CONSTANTES STRUCTURELLES (tailles de "
                "grille, options de menu, ratios de regle ecrits dans une chaine d'affichage "
                "comme le 3:2 du blackjack), jamais les probabilites ou les tables de gains."
            ),
        },
        "games": games,
        "server_only_surface": server_surface_by_game,
        "rakeback": rakeback,
    }
    return output


def main():
    if not RAW_PATH.exists():
        print(f"ERREUR: {RAW_PATH} introuvable", file=sys.stderr)
        sys.exit(1)
    output = build()
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # Resume court sur stdout : combien de champs trouves vs manquants
    found_n = 0
    missing_n = 0

    def walk(node):
        nonlocal found_n, missing_n
        if isinstance(node, dict):
            if "status" in node and node["status"] in ("found_in_client", "not_found"):
                if node["status"] == "found_in_client":
                    found_n += 1
                else:
                    missing_n += 1
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(output["games"])
    walk(output["rakeback"])
    print(f"Extraction terminee -> {OUT_PATH}")
    print(f"Champs localises dans le client : {found_n}")
    print(f"Champs marques manquants (server-only) : {missing_n}")


if __name__ == "__main__":
    main()
