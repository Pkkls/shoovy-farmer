"""
Extracteur d'annonces de gains (etude shoovy.wtf / chat Kick).

Le bot du jeu annonce publiquement chaque gain dans le chat, valeur en credits
incluse. Chaque annonce est une observation gratuite de la table de gains :
aucune requete reseau necessaire, on lit chat.jsonl.

Script RE-EXECUTABLE et INCREMENTAL :
  - relit tout chat.jsonl a chaque lancement (source de verite, jamais modifiee)
  - lit l'existant de payouts.jsonl et ne reecrit jamais une observation deja
    extraite (dedup par hash stable sur ts+sender+content)
  - n'ajoute (append) que les nouvelles observations
  - recalcule la synthese statistique sur l'ensemble des observations connues

Identification du bot : PAS de nom d'utilisateur en dur. On reutilise la
logique d'analyze_chat.py (section 4c : message qui mentionne @pseudo ET
utilise un vocabulaire structure de gain) pour deriver quels expediteurs
sont le bot du jeu, plus une verification croisee sur le pseudo. Voir
identify_bot_senders().

Format des annonces : derive des messages REELS trouves dans chat.jsonl, pas
suppose. A ce jour, un seul gabarit a ete observe (mecanique "peche", emoji
canne a peche + "reeled in"). Toute annonce du bot qui ne correspond a AUCUN
parseur connu est listee comme "non parsee" dans la synthese, jamais inventee.

Ne fait aucune requete reseau, aucune connexion websocket. Ne modifie aucun
fichier existant. Ecrit uniquement payouts.jsonl a cote de lui.

Usage: py payouts.py [chemin_vers_chat.jsonl] [chemin_payouts.jsonl]
"""

import hashlib
import json
import os
import re
import statistics
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CHAT = os.path.join(SCRIPT_DIR, "chat.jsonl")
DEFAULT_PAYOUTS = os.path.join(SCRIPT_DIR, "payouts.jsonl")

# Reutilise la logique de detection deja ecrite et validee dans analyze_chat.py
# (ne pas modifier ce fichier, seulement l'importer).
sys.path.insert(0, SCRIPT_DIR)
import analyze_chat  # noqa: E402  (import apres sys.path.insert, volontaire)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIN_N_FOR_STDEV = 5
MIN_N_FOR_QUANTILES = 20

# ---------------------------------------------------------------------------
# 1. Chargement des messages (meme format que analyze_chat.py)
# ---------------------------------------------------------------------------


def load_messages(path):
    """Relit chat.jsonl integralement (instantane courant). Ignore les lignes
    JSON invalides en les comptant, ne plante jamais dessus."""
    events, n_total_lines, n_bad = analyze_chat.load_events(path)
    msgs = []
    for d in events:
        if d.get("kind") != "msg":
            continue
        p = d.get("payload") or {}
        msgs.append({
            "ts": d.get("ts"),
            "sender": p.get("sender"),
            "content": p.get("content") or "",
            "created_at": p.get("created_at"),
        })
    msgs.sort(key=lambda m: (m["ts"] if m["ts"] is not None else 0))
    return msgs, n_total_lines, n_bad


# ---------------------------------------------------------------------------
# 2. Identification du bot (derivee des donnees, pas un nom en dur)
# ---------------------------------------------------------------------------


def identify_bot_senders(msgs):
    """Reprend le critere structurel d'analyze_chat.py (section 4c) : un
    message qui mentionne @pseudo ET utilise un vocabulaire structure de
    resultat de jeu (N credits, N lb, 'reeled in', 'personal best') est une
    reponse-jeu. L'expediteur de ce type de message est le bot.

    Complete par un controle croise sur le pseudo (contient "bot" ET
    "shoovy") plutot que le filtre OR d'analyze_chat.py ("bot|shoovy|system|
    automod"), qui est volontairement large la-bas (juste une liste de
    candidats a regarder) mais produirait ici des faux positifs -- ex:
    "shoovyfan48" (fan humain, contient "shoovy" mais pas "bot") ou "BotRix"
    (bot Discord distinct, contient "bot" mais pas "shoovy").
    """
    structural = set()
    for m in msgs:
        content = m["content"]
        if content.strip().startswith("!"):
            continue
        mention = analyze_chat.MENTION_RE.search(content)
        if not mention:
            continue
        if not analyze_chat.GAIN_STRUCT_RE.search(content):
            continue
        if mention.group(1).lower() == (m["sender"] or "").lower():
            continue  # auto-mention, pas pertinent
        if m["sender"]:
            structural.add(m["sender"])

    name_heuristic = set()
    for m in msgs:
        s = m["sender"] or ""
        sl = s.lower()
        if "bot" in sl and "shoovy" in sl:
            name_heuristic.add(s)

    return structural | name_heuristic, structural, name_heuristic


# ---------------------------------------------------------------------------
# 3. Parseurs de gabarits d'annonce (un par mecanique CONFIRMEE dans les donnees)
# ---------------------------------------------------------------------------

# Gabarit "peche", derive de messages reels, ex:
#   "reeled in a 32.1 lb Tarpon (rare) worth 141 credits x 69/100 species -- sell it on the fishing page!"
#   "reeled in a 64.4 lb Stingray (uncommon) worth 280 credits x 75/100 species x new personal best! -- sell it on the fishing page!"
FISH_PLAYER_RE = re.compile(r"@(\w+)\s+reeled in", re.IGNORECASE)
FISH_WEIGHT_RE = re.compile(r"reeled in a\s+([\d.]+)\s*lb", re.IGNORECASE)
FISH_SPECIES_RE = re.compile(r"lb\s+(\S+)\s+([A-Za-z][A-Za-z'\- ]*?)\s*\(([a-zA-Z ]+)\)")
FISH_AMOUNT_RE = re.compile(r"worth\s+([\d,]+)\s*credits", re.IGNORECASE)
FISH_PROGRESS_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*species")


def parse_fishing(content):
    if "reeled in" not in content.lower():
        return None

    m_player = FISH_PLAYER_RE.search(content)
    m_weight = FISH_WEIGHT_RE.search(content)
    m_species = FISH_SPECIES_RE.search(content)
    m_amount = FISH_AMOUNT_RE.search(content)
    if not (m_player and m_weight and m_species and m_amount):
        return None  # champ essentiel manquant -> pas un gabarit peche reconnu

    m_progress = FISH_PROGRESS_RE.search(content)

    return {
        "mechanic": "peche",
        "player": m_player.group(1),
        "amount_credits": int(m_amount.group(1).replace(",", "")),
        "species_icon": m_species.group(1),
        "species": m_species.group(2).strip(),
        "rarity": m_species.group(3).strip().lower(),
        "weight_lb": float(m_weight.group(1)),
        "species_progress": ("%s/%s" % (m_progress.group(1), m_progress.group(2))) if m_progress else None,
        "personal_best": "personal best" in content.lower(),
    }


# Liste des parseurs connus. Ajouter une entree ici des qu'un nouveau gabarit
# reel est observe (casino, business, crime, vol...). Aucun gabarit invente.
PARSERS = [
    ("peche", parse_fishing),
]


def parse_announcement(content):
    for mechanic, parser in PARSERS:
        fields = parser(content)
        if fields is not None:
            return fields
    return None


# ---------------------------------------------------------------------------
# 4. Dedup / incrementalite
# ---------------------------------------------------------------------------


def observation_id(ts, sender, content):
    raw = "%s|%s|%s" % (ts, sender, content)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_existing_payouts(path):
    """Relit payouts.jsonl s'il existe deja. Ignore les lignes illisibles en
    les comptant (meme discipline que load_events)."""
    records = []
    n_bad = 0
    if not os.path.exists(path):
        return records, n_bad
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError:
                n_bad += 1
    return records, n_bad


# ---------------------------------------------------------------------------
# 5. Statistiques (jamais un chiffre sans sa taille d'echantillon)
# ---------------------------------------------------------------------------


def describe_distribution(values):
    n = len(values)
    lines = []
    lines.append("    n = %d" % n)
    lines.append("    min = %s | max = %s" % (min(values), max(values)))
    lines.append("    mediane (n=%d) = %s" % (n, statistics.median(values)))
    lines.append("    moyenne (n=%d) = %.2f" % (n, statistics.mean(values)))
    if n >= MIN_N_FOR_STDEV:
        lines.append("    ecart-type (n=%d) = %.2f" % (n, statistics.stdev(values)))
    else:
        lines.append("    ecart-type : NON CALCULE (n=%d < seuil %d, echantillon trop faible)" % (n, MIN_N_FOR_STDEV))
    if n >= MIN_N_FOR_QUANTILES:
        q = statistics.quantiles(values, n=4, method="inclusive")
        lines.append("    quartiles (n=%d) : Q1=%.1f  Q2(mediane)=%.1f  Q3=%.1f" % (n, q[0], q[1], q[2]))
    else:
        lines.append("    quantiles : NON CALCULES (n=%d < seuil %d, echantillon trop faible)" % (n, MIN_N_FOR_QUANTILES))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------


def main():
    chat_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CHAT
    payouts_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PAYOUTS

    if not os.path.exists(chat_path):
        print("Fichier introuvable : %s" % chat_path)
        sys.exit(1)

    msgs, n_total_lines, n_bad_chat = load_messages(chat_path)
    print("chat.jsonl : %d lignes lues, %d illisibles ignorees, %d messages (kind=msg)."
          % (n_total_lines, n_bad_chat, len(msgs)))

    bot_senders, structural, name_heur = identify_bot_senders(msgs)
    print("")
    print("Identification du bot du jeu (derivee des donnees, aucun nom en dur) :")
    print("  candidats via critere structurel (mention @pseudo + vocabulaire de gain) : %s"
          % (sorted(structural) if structural else "aucun"))
    print("  candidats via heuristique de pseudo ('bot' ET 'shoovy') : %s"
          % (sorted(name_heur) if name_heur else "aucun"))
    print("  => expediteurs retenus comme bot du jeu : %s" % (sorted(bot_senders) if bot_senders else "AUCUN"))

    bot_msgs = [m for m in msgs if m["sender"] in bot_senders]
    print("")
    print("Messages du bot du jeu trouves dans chat.jsonl : %d" % len(bot_msgs))

    existing_records, n_bad_payouts = load_existing_payouts(payouts_path)
    if n_bad_payouts:
        print("payouts.jsonl : %d ligne(s) illisible(s) ignoree(s) (fichier existant)." % n_bad_payouts)
    existing_ids = {r.get("id") for r in existing_records if r.get("id")}
    print("Observations deja presentes dans payouts.jsonl : %d" % len(existing_records))

    new_records = []
    unparsed = []
    seen_this_run = set()
    for m in bot_msgs:
        oid = observation_id(m["ts"], m["sender"], m["content"])
        if oid in existing_ids or oid in seen_this_run:
            continue  # deja extrait lors d'un run precedent, ou doublon exact dans ce run
        seen_this_run.add(oid)

        fields = parse_announcement(m["content"])
        if fields is None:
            unparsed.append(m)
            continue

        record = {
            "id": oid,
            "ts": m["ts"],
            "created_at": m["created_at"],
            "sender": m["sender"],
            "raw_content": m["content"],
        }
        record.update(fields)
        new_records.append(record)

    if new_records:
        with open(payouts_path, "a", encoding="utf-8") as f:
            for r in new_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("")
    print("Nouvelles observations extraites et ajoutees a payouts.jsonl : %d" % len(new_records))
    print("Nouveaux messages du bot NON parses (aucun gabarit connu ne correspond) : %d" % len(unparsed))

    all_records = existing_records + new_records
    print("")
    print("Total observations dans payouts.jsonl (cumulatif) : %d" % len(all_records))

    # ------------------------------------------------------------------
    # Synthese par mecanique
    # ------------------------------------------------------------------
    print("")
    print("=" * 78)
    print("SYNTHESE PAR MECANIQUE")
    print("=" * 78)

    by_mechanic = {}
    for r in all_records:
        by_mechanic.setdefault(r.get("mechanic", "inconnue"), []).append(r)

    all_known_mechanics = ["peche", "casino", "business", "crime", "vol"]
    observed = set(by_mechanic)
    for mech in all_known_mechanics:
        if mech not in observed:
            print("")
            print("%s : 0 observation (aucune annonce de cette mecanique vue dans chat.jsonl jusqu'ici)" % mech)

    for mech, records in sorted(by_mechanic.items(), key=lambda kv: -len(kv[1])):
        amounts = [r["amount_credits"] for r in records if "amount_credits" in r]
        print("")
        print("%s : %d observation(s)" % (mech, len(records)))
        if amounts:
            print("  Distribution des montants (credits) :")
            print(describe_distribution(amounts))
        else:
            print("  Aucun montant en credits extrait pour cette mecanique.")

    # ------------------------------------------------------------------
    # Transparence : messages du bot qu'on n'a pas su parser
    # ------------------------------------------------------------------
    print("")
    print("=" * 78)
    print("MESSAGES DU BOT NON PARSES (nouveaux cette execution)")
    print("=" * 78)
    if not unparsed:
        print("Aucun -- tous les nouveaux messages du bot ont ete parses par un gabarit connu.")
    else:
        for m in unparsed:
            print("  [ts=%s] %s: %s" % (m["ts"], m["sender"], m["content"]))
        print("")
        print("=> %d gabarit(s) non reconnu(s). A inspecter pour ecrire un nouveau parseur." % len(unparsed))


if __name__ == "__main__":
    main()
