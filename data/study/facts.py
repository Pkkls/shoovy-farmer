"""The study's semantic store: typed observations, append-only, queryable.

Prose cannot say where a number came from, what would break it, or whether it
was measured or guessed. Every figure in this study lives here instead, and the
Markdown is a view over it.

Append-only on purpose. A value that replaces another does not overwrite it: the
old record stays, and the correction stacks on top. This study has already
reversed three conclusions, and the reversals are data.

    python facts.py what mechanic:fishing     # everything about a subject
    python facts.py status assumed            # everything still unverified
    python facts.py deps infra.availability   # what rests on this fact
    python facts.py check                     # integrity problems
    python facts.py list                      # current value of every fact
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "facts.jsonl")

STATUSES = ("measured", "derived", "candidate", "assumed", "refuted")

REQUIRED = ("id", "subject", "predicate", "value", "status", "method", "source")


class Invalid(Exception):
    pass


def validate(rec):
    for k in REQUIRED:
        if k not in rec or rec[k] in (None, ""):
            raise Invalid(f"{rec.get('id','?')}: champ obligatoire manquant: {k}")
    if rec["status"] not in STATUSES:
        raise Invalid(f"{rec['id']}: status inconnu {rec['status']!r}, "
                      f"attendu un de {STATUSES}")
    if ":" not in rec["subject"]:
        raise Invalid(f"{rec['id']}: subject doit etre prefixe "
                      f"(mechanic:, endpoint:, command:, event:, infra:, constant:), "
                      f"recu {rec['subject']!r}")
    if rec["status"] == "derived" and not rec.get("derived_from"):
        raise Invalid(f"{rec['id']}: un fait derive doit nommer derived_from")
    if rec["status"] == "candidate" and not rec.get("invalidated_by"):
        raise Invalid(f"{rec['id']}: un candidat doit nommer invalidated_by")
    # A random mechanic reports its sample and its spread, or it is not a
    # measurement. One average over three draws is an anecdote.
    if rec.get("random"):
        if not rec.get("n"):
            raise Invalid(f"{rec['id']}: mecanique aleatoire sans n")
        if rec.get("dispersion") in (None, ""):
            raise Invalid(f"{rec['id']}: mecanique aleatoire sans dispersion")
    return rec


def add(**rec):
    rec.setdefault("observed_at", int(time.time()))
    rec.setdefault("supersedes", None)
    validate(rec)
    with open(STORE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load():
    if not os.path.exists(STORE):
        return []
    return [json.loads(l) for l in open(STORE, encoding="utf-8") if l.strip()]


def current():
    """Latest record per fact id. Earlier records stay in the file as history.

    Records with no id are skipped rather than fatal: a concurrent writer once
    appended a batch in a different shape, and losing the whole store to one
    malformed line is worse than ignoring it. `orphans()` lists them so they can
    be migrated instead of quietly lost.
    """
    out = {}
    for rec in load():
        if "id" in rec:
            out[rec["id"]] = rec
    return out


def orphans():
    """Records that predate or violate the schema, kept for migration."""
    return [r for r in load() if "id" not in r]


def _fmt(rec):
    val = rec["value"]
    unit = f" {rec['unit']}" if rec.get("unit") else ""
    n = f" n={rec['n']}" if rec.get("n") else ""
    disp = f" ±{rec['dispersion']}" if rec.get("dispersion") else ""
    conf = f" conf={rec['confidence']}" if rec.get("confidence") is not None else ""
    return (f"  [{rec['status']:9}] {rec['id']:34} {rec['predicate']:22} "
            f"{val}{unit}{n}{disp}{conf}\n"
            f"      methode: {rec['method']}\n"
            f"      source : {rec['source']}")


def cmd_what(arg):
    hits = [r for r in current().values()
            if arg in r["subject"] or arg in r["id"]]
    if not hits:
        print(f"rien sur {arg!r}")
        return 1
    for subject in sorted({r["subject"] for r in hits}):
        print(f"\n{subject}")
        for r in sorted([h for h in hits if h["subject"] == subject],
                        key=lambda r: r["id"]):
            print(_fmt(r))
            if r.get("invalidated_by"):
                print(f"      casse si : {r['invalidated_by']}")
    return 0


def cmd_status(arg):
    hits = [r for r in current().values() if r["status"] == arg]
    print(f"{len(hits)} fait(s) en statut {arg!r}\n")
    for r in sorted(hits, key=lambda r: r["id"]):
        print(_fmt(r))
        if r.get("invalidated_by"):
            print(f"      casse si : {r['invalidated_by']}")
    return 0


def cmd_deps(arg):
    cur = current()
    dependents = [r for r in cur.values() if arg in (r.get("derived_from") or [])]
    replaced = [r for r in cur.values() if r.get("supersedes") == arg]
    print(f"faits qui derivent de {arg}: {len(dependents)}")
    for r in dependents:
        print(_fmt(r))
    if replaced:
        print(f"\nfaits qui remplacent {arg}: {len(replaced)}")
        for r in replaced:
            print(_fmt(r))
    if arg in cur and cur[arg]["status"] == "refuted" and dependents:
        print("\n!! ce fait est refute et des derives en dependent encore")
    return 0


def cmd_check():
    cur = current()
    problems = []
    for r in cur.values():
        for parent in (r.get("derived_from") or []):
            if parent not in cur:
                problems.append(f"{r['id']}: derive d'un id inconnu {parent!r}")
            elif cur[parent]["status"] == "refuted" and r["status"] != "refuted":
                # A refuted fact resting on a refuted parent is consistent: the
                # cascade already reached it. Only live facts are a problem.
                problems.append(f"{r['id']}: derive de {parent} qui est REFUTE")
        if r.get("supersedes") and r["supersedes"] not in cur:
            problems.append(f"{r['id']}: supersedes un id inconnu {r['supersedes']!r}")
    counts = {}
    for r in cur.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{len(cur)} faits courants ({len(load())} enregistrements avec historique)")
    print("  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if problems:
        print(f"\n{len(problems)} probleme(s):")
        for p in problems:
            print("  !", p)
        return 1
    print("\naucun probleme d'integrite")
    return 0


def cmd_list():
    for r in sorted(current().values(), key=lambda r: (r["subject"], r["id"])):
        print(_fmt(r))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, arg = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    if cmd == "what" and arg:
        return cmd_what(arg)
    if cmd == "status" and arg:
        return cmd_status(arg)
    if cmd == "deps" and arg:
        return cmd_deps(arg)
    if cmd == "check":
        return cmd_check()
    if cmd == "list":
        return cmd_list()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
