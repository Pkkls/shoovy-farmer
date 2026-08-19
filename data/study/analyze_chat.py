"""
Analyse de chat.jsonl (etude shoovy.wtf / chat Kick).

Script re-executable : relit tout le fichier a chaque lancement, donc peut
etre relance plus tard sur un chat.jsonl plus gros sans modification.
Ne fait aucune requete reseau, ne modifie aucun fichier source. Ecrit
uniquement chat_analysis.txt a cote de lui.

Usage: py analyze_chat.py [chemin_vers_chat.jsonl] [chemin_sortie.txt]
"""

import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "chat.jsonl")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "chat_analysis.txt")

CMD_RE = re.compile(r"^!(\w+)")
SPECIAL_EVENT_WORDS = ["chest", "frenzy", "boom", "pump", "dump"]
BURST_WINDOW_S = 15          # fenetre glissante pour detecter une annonce collective
BURST_MIN_DISTINCT_SENDERS = 3
CLUSTER_TOL_FLOOR_S = 5       # tolerance minimale pour le clustering d'intervalles
CLUSTER_TOL_RATIO = 0.20      # tolerance relative pour le clustering d'intervalles
CLUSTER_RATIO_THRESHOLD = 0.60  # part des intervalles dans le cluster dominant pour dire "resserre"
MIN_INTERVALS_FOR_VERDICT = 5   # sous ce seuil : "indicatif seulement", jamais de verdict tranche
BOT_CORRELATION_WINDOW_S = 600  # fenetre large pour chercher la commande precedente du joueur mentionne
                                 # (large expres : on veut MESURER la latence reelle, pas la presupposer)
MENTION_RE = re.compile(r"@(\w+)")
GAIN_STRUCT_RE = re.compile(r"\d+\s*(credits|lb\b)|reeled in|personal best", re.IGNORECASE)
LOOSE_GAIN_RE = re.compile(r"credits|worth|reeled|jackpot|\bwon\b| lb |personal best", re.IGNORECASE)


def fmt_ts(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_events(path):
    """Lit toutes les lignes disponibles MAINTENANT (instantane). Ignore les lignes
    illisibles en le signalant, ne fait jamais planter l'analyse pour une ligne pourrie."""
    events = []
    n_bad = 0
    n_total_lines = 0
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            n_total_lines += 1
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                n_bad += 1
                continue
            events.append(d)
    return events, n_total_lines, n_bad


def normalize_command(content):
    m = CMD_RE.match(content.strip())
    if not m:
        return None
    return "!" + m.group(1).lower()


def cluster_intervals(intervals):
    """Cherche le plus gros cluster d'intervalles proches (tolerance relative).
    Retourne (centre_median, taille_cluster, ratio_sur_total)."""
    if not intervals:
        return None, 0, 0.0
    best_cluster = []
    for center in intervals:
        tol = max(CLUSTER_TOL_FLOOR_S, CLUSTER_TOL_RATIO * center)
        cluster = [x for x in intervals if abs(x - center) <= tol]
        if len(cluster) > len(best_cluster):
            best_cluster = cluster
    return statistics.median(best_cluster), len(best_cluster), len(best_cluster) / len(intervals)


def analyze(path):
    events, n_total_lines, n_bad = load_events(path)

    msgs = []       # (ts, sender, content, type)
    others = []
    connects = []
    for d in events:
        kind = d.get("kind")
        ts = d.get("ts")
        if kind == "msg":
            p = d.get("payload") or {}
            msgs.append((ts, p.get("sender"), p.get("content") or "", p.get("type")))
        elif kind in ("connected", "disconnect"):
            connects.append((ts, kind, d.get("payload")))
        else:
            others.append((ts, kind, d.get("payload")))

    msgs.sort(key=lambda x: (x[0] if x[0] is not None else 0))
    lines = []

    def out(s=""):
        lines.append(s)

    out("=" * 78)
    out("ANALYSE chat.jsonl -- shoovy.wtf / chat Kick")
    out("Genere le : " + fmt_ts(datetime.now(timezone.utc).timestamp()))
    out("Fichier source : " + path)
    out("=" * 78)
    out("")
    out("NOTE METHODO : le fichier source grossit en continu (ecouteur actif).")
    out("Cette analyse est un instantane pris a l'instant du lancement du script.")
    out("Lignes brutes lues dans ce fichier : %d" % n_total_lines)
    if n_bad:
        out("Lignes illisibles (JSON invalide), ignorees : %d" % n_bad)
    else:
        out("Lignes illisibles (JSON invalide) : 0")
    out("Evenements kind=msg : %d | kind=connected/disconnect : %d | kind=other : %d"
        % (len(msgs), len(connects), len(others)))

    # ------------------------------------------------------------------
    # 1. VOLUMETRIE
    # ------------------------------------------------------------------
    out("")
    out("-" * 78)
    out("1. VOLUMETRIE")
    out("-" * 78)
    if not msgs:
        out("Aucun message kind=msg dans le fichier. Rien a calculer.")
    else:
        ts_list = [m[0] for m in msgs if m[0] is not None]
        n_msgs = len(msgs)
        t_min, t_max = min(ts_list), max(ts_list)
        duration_s = t_max - t_min
        duration_min = duration_s / 60.0
        out("Nombre de messages (kind=msg) : %d" % n_msgs)
        out("Fenetre temporelle couverte : %s -> %s" % (fmt_ts(t_min), fmt_ts(t_max)))
        out("Duree couverte : %.1f minutes (%d s)" % (duration_min, duration_s))
        if duration_min > 0:
            out("Debit moyen : %.2f messages/minute" % (n_msgs / duration_min))
        else:
            out("Duree nulle ou trop courte : debit moyen non calculable.")

        out("")
        out("Evolution par tranche de 5 minutes (alignee sur la premiere tranche) :")
        bucket_counts = Counter()
        for ts in ts_list:
            bucket = (ts - t_min) // 300
            bucket_counts[bucket] += 1
        n_buckets = max(bucket_counts) + 1 if bucket_counts else 0
        for b in range(n_buckets):
            bstart = t_min + b * 300
            cnt = bucket_counts.get(b, 0)
            rate = cnt / 5.0
            out("  [%s - %s[  %4d msg  (%.1f msg/min)"
                % (fmt_ts(bstart)[11:19], fmt_ts(bstart + 300)[11:19], cnt, rate))
        if n_buckets and bucket_counts.get(n_buckets - 1, 0) < 5:
            out("  (derniere tranche potentiellement partielle : capture arretee en cours de tranche)")

    if connects:
        out("")
        out("Evenements de connexion/deconnexion (contexte, peuvent expliquer des trous) :")
        for ts, kind, payload in connects[:20]:
            out("  %s  %s  %s" % (fmt_ts(ts), kind, payload))
        if len(connects) > 20:
            out("  ... (%d de plus, non affiches)" % (len(connects) - 20))

    # ------------------------------------------------------------------
    # 2. COMMANDES
    # ------------------------------------------------------------------
    out("")
    out("-" * 78)
    out("2. COMMANDES (contenu commencant par '!')")
    out("-" * 78)
    cmd_counter = Counter()
    cmd_examples = {}
    for ts, sender, content, mtype in msgs:
        content_stripped = content.strip()
        if content_stripped.startswith("!"):
            cmd = normalize_command(content_stripped)
            if cmd:
                cmd_counter[cmd] += 1
                cmd_examples.setdefault(cmd, content_stripped)

    n_cmd_msgs = sum(cmd_counter.values())
    out("Messages-commandes (commencant par '!') : %d sur %d messages totaux" % (n_cmd_msgs, len(msgs)))
    if not cmd_counter:
        out("Aucune commande detectee.")
    else:
        out("")
        out("Comptage par commande (casse normalisee) :")
        for cmd, cnt in cmd_counter.most_common():
            out("  %-20s %4d   (ex: %s)" % (cmd, cnt, cmd_examples[cmd][:60]))
        out("")
        out("Commandes distinctes vues (%d) : %s" % (len(cmd_counter), ", ".join(sorted(cmd_counter))))

    # ------------------------------------------------------------------
    # 3. CADENCES PAR JOUEUR (le plus important)
    # ------------------------------------------------------------------
    out("")
    out("-" * 78)
    out("3. CADENCES PAR (JOUEUR, COMMANDE) -- detection de cooldown")
    out("-" * 78)

    pair_occurrences = defaultdict(list)
    for ts, sender, content, mtype in msgs:
        content_stripped = content.strip()
        if content_stripped.startswith("!"):
            cmd = normalize_command(content_stripped)
            if cmd and sender:
                pair_occurrences[(sender, cmd)].append(ts)

    qualifying = {k: sorted(v) for k, v in pair_occurrences.items() if len(v) >= 3}
    out("Couples (joueur, commande) avec >= 3 occurrences : %d" % len(qualifying))
    out("(tout couple avec moins de 3 occurrences est ignore ici, echantillon trop faible pour un intervalle)")
    out("")

    tight_results = []   # (cmd, sender, cluster_center, n_occ, n_int, ratio)
    erratic_results = []
    weak_results = []

    if not qualifying:
        out("Aucun couple ne franchit le seuil de 3 occurrences. Rien a analyser ici.")
    else:
        for (sender, cmd), ts_list in sorted(qualifying.items(), key=lambda kv: -len(kv[1])):
            n_occ = len(ts_list)
            intervals = [ts_list[i + 1] - ts_list[i] for i in range(n_occ - 1)]
            n_int = len(intervals)
            median_int = statistics.median(intervals)
            mean_int = statistics.mean(intervals)
            stdev_int = statistics.pstdev(intervals) if n_int > 1 else 0.0
            cv = (stdev_int / mean_int) if mean_int else None
            cluster_center, cluster_size, cluster_ratio = cluster_intervals(intervals)

            out("%s x %s : n=%d occurrences, %d intervalles" % (sender, cmd, n_occ, n_int))
            out("  intervalles (s) : %s" % intervals)
            out("  mediane=%.1fs  moyenne=%.1fs  ecart-type=%.1fs  CV=%s"
                % (median_int, mean_int, stdev_int,
                   ("%.2f" % cv) if cv is not None else "n/a"))
            out("  cluster dominant : ~%.1fs (%d/%d intervalles, ratio=%.2f)"
                % (cluster_center, cluster_size, n_int, cluster_ratio))

            if n_int < MIN_INTERVALS_FOR_VERDICT:
                verdict = "INDICATIF SEULEMENT (echantillon %d intervalle(s) < seuil %d) -- pas concluant" % (
                    n_int, MIN_INTERVALS_FOR_VERDICT)
                weak_results.append((cmd, sender, cluster_center, n_occ, n_int, cluster_ratio))
            elif cluster_ratio >= CLUSTER_RATIO_THRESHOLD:
                verdict = "CADENCE RESSERREE autour de ~%.1fs -- candidat cooldown" % cluster_center
                tight_results.append((cmd, sender, cluster_center, n_occ, n_int, cluster_ratio))
            else:
                verdict = "ERRATIQUE -- pas de valeur dominante claire (joueur impatient probable ou reponses irregulieres)"
                erratic_results.append((cmd, sender, cluster_center, n_occ, n_int, cluster_ratio))
            out("  VERDICT : %s" % verdict)
            out("")

        out("Synthese cadences :")
        out("  Resserrees (candidats cooldown, n_intervalles>=%d) : %d couple(s)" % (
            MIN_INTERVALS_FOR_VERDICT, len(tight_results)))
        out("  Erratiques (n_intervalles>=%d mais pas de cluster dominant) : %d couple(s)" % (
            MIN_INTERVALS_FOR_VERDICT, len(erratic_results)))
        out("  Echantillon trop faible pour trancher (< %d intervalles) : %d couple(s)" % (
            MIN_INTERVALS_FOR_VERDICT, len(weak_results)))
        out("")

        # Validation croisee : un cooldown n'est exploitable que si plusieurs
        # joueurs distincts convergent vers la meme valeur pour la meme commande.
        by_cmd = defaultdict(list)
        for cmd, sender, center, n_occ, n_int, ratio in tight_results:
            by_cmd[cmd].append((sender, center))

        out("Validation croisee (un seul joueur ne suffit jamais a conclure un cooldown) :")
        if not tight_results:
            out("  Aucun couple n'atteint le statut 'resserre' avec un echantillon suffisant.")
            out("  => Aucune valeur de cooldown exploitable ne peut etre affirmee sur cet instantane.")
        else:
            any_exploitable = False
            for cmd, entries in by_cmd.items():
                distinct_senders = {s for s, c in entries}
                if len(distinct_senders) == 1:
                    s, c = entries[0]
                    out("  %s : signal resserre chez UN SEUL joueur (%s, ~%.1fs)." % (cmd, s, c))
                    out("    => INSUFFISANT pour conclure a un cooldown global. A confirmer avec d'autres joueurs.")
                else:
                    centers = [c for s, c in entries]
                    spread = max(centers) - min(centers)
                    ref = statistics.median(centers)
                    tol = max(CLUSTER_TOL_FLOOR_S, CLUSTER_TOL_RATIO * ref)
                    if spread <= tol:
                        any_exploitable = True
                        out("  %s : convergence entre %d joueurs (%s) autour de ~%.1fs (ecart max %.1fs)."
                            % (cmd, len(distinct_senders), ", ".join(sorted(distinct_senders)), ref, spread))
                        out("    => EXPLOITABLE : cooldown estime ~%.1fs pour '%s'." % (ref, cmd))
                    else:
                        out("  %s : %d joueurs resserres mais sur des valeurs qui divergent (%s) -- pas une valeur unique."
                            % (cmd, len(distinct_senders), centers))
                        out("    => Cooldowns individuels plausibles mais pas de valeur globale exploitable sur cet instantane.")
            if not any_exploitable and len(by_cmd) > 0 and all(len({s for s, c in e}) == 1 for e in by_cmd.values()):
                out("")
                out("  Conclusion : tous les signaux resserres viennent d'un seul joueur par commande.")
                out("  Par discipline, aucun ne doit etre presente comme un cooldown confirme.")

        if weak_results:
            out("")
            out("Couples a echantillon trop faible (rappel, non concluants, donnes a titre indicatif) :")
            for cmd, sender, center, n_occ, n_int, ratio in weak_results:
                out("  %s x %s : n_occ=%d, n_intervalles=%d, cluster indicatif ~%.1fs" % (
                    sender, cmd, n_occ, n_int, center))

    # ------------------------------------------------------------------
    # 4. DETECTION D'UN COMPTE AUTOMATE / SYSTEME
    # ------------------------------------------------------------------
    out("")
    out("-" * 78)
    out("4. DETECTION D'UN COMPTE AUTOMATE / SYSTEME (le jeu repond-il en chat ?)")
    out("-" * 78)

    sender_counter = Counter(m[1] for m in msgs if m[1])
    n_senders = len(sender_counter)
    out("Expediteurs distincts observes : %d, pour %d messages." % (n_senders, len(msgs)))

    # 4a. Regularite / frequence brute par expediteur (signal generique de non-humain)
    out("")
    out("Top expediteurs par frequence (signal brut, ne prouve rien seul) :")
    for sender, cnt in sender_counter.most_common(10):
        out("  %-25s %4d messages" % (sender, cnt))

    # 4b. Recherche de noms evoquant un bot/systeme
    out("")
    bot_like_names = [s for s in sender_counter if re.search(r"bot|shoovy|system|automod", s, re.IGNORECASE)]
    out("Expediteurs dont le pseudo evoque un bot/systeme/le jeu lui-meme (recherche sur 'bot|shoovy|system|automod', %d expediteurs distincts examines) :"
        % n_senders)
    if bot_like_names:
        for s in sorted(bot_like_names):
            out("  candidat : %s (%d messages)" % (s, sender_counter[s]))
    else:
        out("  Aucun pseudo ne matche ce filtre.")

    # 4c. Le test qui compte vraiment : un message structurellement "resultat de jeu"
    # (mention @pseudo + vocabulaire structure de gain : "reeled in", "N credits", "N lb",
    # "personal best") qu'on relie ensuite a la commande la plus proche du joueur mentionne,
    # SANS presupposer de fenetre de latence courte -- on mesure le delai reel, on ne le filtre pas.
    out("")
    out("Recherche de reponses-jeu structurees : message qui mentionne @pseudo ET utilise un")
    out("vocabulaire structure de resultat de jeu (N credits, N lb, 'reeled in', 'personal best').")
    out("Ce criterion est volontairement strict (mention obligatoire) pour eviter le bruit du")
    out("bavardage normal qui contient occasionnellement 'worth'/'won'/'jackpot' sans rapport avec le jeu.")

    cmd_events = [(ts, sender, content) for ts, sender, content, mtype in msgs
                  if content.strip().startswith("!")]

    game_responses = []  # (ts, sender, content, mentioned_player, best_cmd_or_None)
    for ts, sender, content, mtype in msgs:
        if content.strip().startswith("!"):
            continue
        mention_match = MENTION_RE.search(content)
        if not mention_match:
            continue
        if not GAIN_STRUCT_RE.search(content):
            continue
        mentioned = mention_match.group(1)
        if mentioned.lower() == (sender or "").lower():
            continue  # auto-mention, pas pertinent
        best_cmd = None
        for cts, csender, ccontent in cmd_events:
            if csender.lower() != mentioned.lower():
                continue
            if cts > ts:
                continue
            delay = ts - cts
            if delay > BOT_CORRELATION_WINDOW_S:
                continue
            if best_cmd is None or delay < best_cmd[3]:
                best_cmd = (cts, csender, ccontent, delay)
        game_responses.append((ts, sender, content, mentioned, best_cmd))

    n_examined_for_bot = len(msgs)
    responder_senders = Counter(r[1] for r in game_responses)

    if not game_responses:
        out("  RESULTAT : aucun message structure de ce type sur les %d messages examines." % n_examined_for_bot)
        out("  => Sur cet instantane, rien n'indique que le jeu repond en chat (ni preuve du contraire :")
        out("     un backend en panne produirait exactement ce signal ; voir note ci-dessous.)")
    else:
        out("  RESULTAT : %d message(s) structure(s) 'resultat de jeu', %d expediteur(s) distinct(s), sur %d messages examines :"
            % (len(game_responses), len(responder_senders), n_examined_for_bot))
        out("  Repartition par expediteur : %s" % dict(responder_senders))
        for ts, sender, content, mentioned, best_cmd in game_responses[:20]:
            if best_cmd:
                cts, csender, ccontent, delay = best_cmd
                out("  [%s] %s: %s" % (fmt_ts(ts)[11:19], sender, content[:160]))
                out("      -> commande la plus proche de @%s : [%s] %s (delai observe : %ds)"
                    % (mentioned, fmt_ts(cts)[11:19], ccontent[:60], delay))
            else:
                out("  [%s] %s: %s" % (fmt_ts(ts)[11:19], sender, content[:160]))
                out("      -> AUCUNE commande de @%s trouvee dans les %ds precedents (pas de correlation possible)"
                    % (mentioned, BOT_CORRELATION_WINDOW_S))
        if len(game_responses) > 20:
            out("  ... (%d de plus, non affiches)" % (len(game_responses) - 20))

        delays = [r[4][3] for r in game_responses if r[4] is not None]
        out("")
        if delays:
            out("Delais observes entre commande et reponse structuree (s) : %s" % delays)
            out("  mediane=%.0fs, min=%ds, max=%ds (n=%d)" % (
                statistics.median(delays), min(delays), max(delays), len(delays)))
        n_uncorrelated = len(game_responses) - len(delays)
        if n_uncorrelated:
            out("%d message(s) structure(s) sans commande correlee retrouvee dans les %ds precedents." % (
                n_uncorrelated, BOT_CORRELATION_WINDOW_S))

        out("")
        out("=> Le jeu REPOND en chat au moins par intermittence sur cet instantane : au moins")
        out("   un expediteur (%s) poste des messages structures qui mentionnent un joueur et un gain."
            % ", ".join(sorted(responder_senders)))
        n_game_cmds = sum(cnt for c, cnt in cmd_counter.items())
        out("")
        out("Nuance obligatoire (panne backend, norme ou exception ?) :")
        out("  commandes-jeu totales (toutes commandes '!...') : %d" % n_game_cmds)
        out("  reponses-jeu structurees detectees : %d" % len(game_responses))
        if n_game_cmds:
            rate = 100.0 * len(game_responses) / n_game_cmds
            out("  taux de reponse observe : %.1f%% des commandes-jeu ont une reponse structuree detectee"
                % rate)
            if rate < 20:
                out("  => taux tres bas : compatible avec un backend majoritairement indisponible/degrade")
                out("     sur cet instantane, PAS avec un jeu qui ne repond jamais (au moins une reponse existe).")

    # 4d. Transparence : combien de messages auraient ete retenus par un filtre
    # laxiste (mot-cle de gain SANS exigence de mention) -- pour montrer que ce
    # filtre produit du bruit et justifier pourquoi il n'est pas utilise ci-dessus.
    loose_no_mention = 0
    loose_examples = []
    for ts, sender, content, mtype in msgs:
        if content.strip().startswith("!"):
            continue
        if MENTION_RE.search(content):
            continue
        if LOOSE_GAIN_RE.search(content):
            loose_no_mention += 1
            if len(loose_examples) < 3:
                loose_examples.append((ts, sender, content))
    out("")
    out("Controle de bruit : messages contenant un mot-cle de gain generique (worth/won/jackpot/...)")
    out("MAIS sans mention @pseudo, donc EXCLUS du comptage ci-dessus (bavardage, pas une reponse-jeu) : %d"
        % loose_no_mention)
    for ts, sender, content in loose_examples:
        out("  exemple exclu [%s] %s: %s" % (fmt_ts(ts)[11:19], sender, content[:100]))

    # ------------------------------------------------------------------
    # 5. EVENEMENTS SPECIAUX
    # ------------------------------------------------------------------
    out("")
    out("-" * 78)
    out("5. EVENEMENTS SPECIAUX (!chest, !frenzy, !boom, !pump, !dump, annonces collectives)")
    out("-" * 78)

    out("Occurrences des commandes speciales connues :")
    any_special_cmd = False
    for w in SPECIAL_EVENT_WORDS:
        key = "!" + w
        cnt = cmd_counter.get(key, 0)
        if cnt:
            any_special_cmd = True
            ts_list = sorted(pair_occurrences_all_ts(msgs, key))
            out("  %s : %d occurrence(s) -- horodatages : %s" % (
                key, cnt, [fmt_ts(t) for t in ts_list][:20]))
        else:
            out("  %s : 0 occurrence" % key)
    if not any_special_cmd:
        out("  => Aucune de ces commandes n'a ete tapee sur cet instantane (%d messages examines)." % len(msgs))

    out("")
    out("Mention en prose de ces mots-cles (hors commande), toutes occurrences :")
    prose_hits = []
    for ts, sender, content, mtype in msgs:
        cl = content.lower()
        for w in SPECIAL_EVENT_WORDS:
            if w in cl and not cl.strip().startswith("!" + w):
                prose_hits.append((ts, sender, content, w))
    if prose_hits:
        for ts, sender, content, w in prose_hits[:20]:
            out("  [%s] %s (mot: %s) %s: %s" % (fmt_ts(ts)[11:19], w, w, sender, content[:100]))
    else:
        out("  Aucune mention en prose trouvee.")

    out("")
    out("Detection d'annonce collective : meme contenu tape par >= %d expediteurs distincts"
        % BURST_MIN_DISTINCT_SENDERS)
    out("en <= %ds (signature typique d'un chest/evenement declenchant une raffale de chat)." % BURST_WINDOW_S)

    content_occ = defaultdict(list)
    for ts, sender, content, mtype in msgs:
        norm = content.strip().lower()
        if not norm or norm.startswith("!"):
            continue
        content_occ[norm].append((ts, sender))

    bursts = []
    for content, occ in content_occ.items():
        if len(occ) < BURST_MIN_DISTINCT_SENDERS:
            continue
        occ_sorted = sorted(occ)
        window = deque()
        best_window = None
        for ts, sender in occ_sorted:
            window.append((ts, sender))
            while window and window[0][0] < ts - BURST_WINDOW_S:
                window.popleft()
            distinct = {s for _, s in window}
            if len(distinct) >= BURST_MIN_DISTINCT_SENDERS:
                if best_window is None or len(distinct) > best_window[2]:
                    best_window = (window[0][0], ts, len(distinct), list(window))
        if best_window:
            bursts.append((content, best_window))

    if bursts:
        bursts.sort(key=lambda b: -b[1][2])
        for content, (t0, t1, n_distinct, win) in bursts[:15]:
            out("  \"%s\" : %d expediteurs distincts entre %s et %s"
                % (content[:60], n_distinct, fmt_ts(t0)[11:19], fmt_ts(t1)[11:19]))
    else:
        out("  Aucune raffale collective detectee (contenu identique tape par >= %d personnes en <= %ds)."
            % (BURST_MIN_DISTINCT_SENDERS, BURST_WINDOW_S))
        out("  Verifie sur %d messages, %d contenus distincts non-commande examines." % (
            len(msgs), len(content_occ)))

    # ------------------------------------------------------------------
    # 6. EVENEMENTS NON-CHAT (kind="other")
    # ------------------------------------------------------------------
    out("")
    out("-" * 78)
    out('6. EVENEMENTS NON-CHAT (kind="other")')
    out("-" * 78)
    if not others:
        out("Aucun evenement kind=\"other\" dans cet instantane (%d lignes totales lues)." % n_total_lines)
    else:
        other_types = Counter(payload.get("event") if isinstance(payload, dict) else None
                               for ts, kind, payload in others)
        out("Nombre d'evenements kind=\"other\" : %d" % len(others))
        out("Repartition par type d'evenement (champ payload.event) :")
        for ev, cnt in other_types.most_common():
            out("  %-45s %4d" % (ev, cnt))
        out("")
        out("Detail (jusqu'a 30) :")
        for ts, kind, payload in others[:30]:
            out("  [%s] %s" % (fmt_ts(ts), payload))
        if len(others) > 30:
            out("  ... (%d de plus, non affiches)" % (len(others) - 30))

    out("")
    out("=" * 78)
    out("FIN DU RAPPORT")
    out("=" * 78)

    return "\n".join(lines), len(msgs), n_total_lines


def pair_occurrences_all_ts(msgs, cmd_key):
    res = []
    for ts, sender, content, mtype in msgs:
        if normalize_command(content.strip()) == cmd_key:
            res.append(ts)
    return res


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    out_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT

    if not os.path.exists(in_path):
        print("Fichier introuvable : %s" % in_path)
        sys.exit(1)

    report, n_msgs, n_total_lines = analyze(in_path)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    print("OK. %d lignes lues (%d messages), rapport ecrit dans %s" % (n_total_lines, n_msgs, out_path))


if __name__ == "__main__":
    main()
