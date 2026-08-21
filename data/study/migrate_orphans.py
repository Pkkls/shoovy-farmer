"""Bring the id-less records into the schema.

An overnight run appended 29 observations in a different shape: subject,
predicate, value, status and source, but no id, so `current()` could not key
them and they were invisible to every query. The content is real work and some
of it contradicts conclusions the study had already drawn, which makes losing it
the worst option available.

This synthesises a stable id from subject and predicate, re-files each record
through the normal validation, and leaves the originals in place because the
store is append-only. Provenance is preserved in the method text: these did not
come from this session and have not been independently re-verified here.

    python migrate_orphans.py [--dry]
"""
import re, sys

import facts

PREFIX_FIX = {
    # The overnight run invented prefixes the schema does not define. Map them
    # onto the existing vocabulary so subjects actually join up.
    "edge:stocks": "mechanic:stocks",
    "edge:crash": "mechanic:casino_crash",
    "strategy:rank1": "infra:leaderboard",
    "tooling:shoovyclient": "infra:shoovy.wtf",
    "api:reads": "infra:shoovy.wtf",
    "infra:leaderboards": "infra:leaderboard",
}

NOTE = ("importe d'une session nocturne qui ecrivait hors schema (aucun id). "
        "Contenu conserve tel quel, provenance signalee: non re-verifie "
        "independamment dans la session courante")


def make_id(subject, predicate):
    base = subject.split(":", 1)[1] if ":" in subject else subject
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    pred = re.sub(r"[^a-z0-9]+", "_", str(predicate).lower()).strip("_")
    return f"{base}.{pred}"


def main():
    dry = "--dry" in sys.argv
    todo = facts.orphans()
    existing = set(facts.current())
    print(f"{len(todo)} enregistrement(s) sans id\n")

    seen, ok, skipped = set(), 0, 0
    for rec in todo:
        subject = PREFIX_FIX.get(rec.get("subject", ""), rec.get("subject", ""))
        if ":" not in subject:
            subject = f"infra:{subject or 'inconnu'}"
        fid = make_id(subject, rec.get("predicate", "sans_predicat"))

        # Two orphans can collide on the same synthesised id; keep both.
        n, base = 2, fid
        while fid in seen:
            fid = f"{base}_{n}"
            n += 1
        seen.add(fid)

        if fid in existing:
            print(f"  = {fid} (deja present, ignore)")
            skipped += 1
            continue

        status = rec.get("status", "assumed")
        if status not in facts.STATUSES:
            status = "assumed"
        # The orphans claim "derived" without naming what they derive from, and
        # that chain cannot be reconstructed after the fact. An unverifiable
        # derivation is an assumption, so say so rather than inventing parents.
        if status == "derived":
            status = "assumed"

        new = dict(
            id=fid, subject=subject, predicate=rec.get("predicate", "inconnu"),
            value=rec.get("value"), status=status, confidence=0.5,
            method=f"{NOTE}. Source d'origine: {rec.get('source', 'non precisee')}",
            source=rec.get("source", "session nocturne"),
        )
        if rec.get("unit"):
            new["unit"] = rec["unit"]
        # A candidate needs its falsifier; these arrive without one.
        if status == "candidate":
            new["invalidated_by"] = ("importe sans falsifieur explicite; a requalifier "
                                     "apres re-verification")
        try:
            if not dry:
                facts.add(**new)
            print(f"  + {fid}")
            ok += 1
        except facts.Invalid as e:
            print(f"  ! rejete: {e}")

    print(f"\n{ok} migre(s), {skipped} deja present(s)"
          f"{' (--dry, rien ecrit)' if dry else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
