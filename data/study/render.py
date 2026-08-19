"""Render the store into FINDINGS.md.

Numbers are never hand-written in the Markdown. This rewrites the region between
the FACTS markers from facts.jsonl and leaves everything outside it alone, so
the prose keeps the reasoning and the design consequences while the figures stay
generated.

    python render.py
"""
import os, sys, time

import facts

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "FINDINGS.md")
BEGIN = "<!-- FACTS:BEGIN -->"
END = "<!-- FACTS:END -->"

ORDER = ["measured", "derived", "candidate", "assumed", "refuted"]
BLURB = {
    "measured": "Observed on the wire by this study.",
    "derived": "Computed from other facts. Each names what it rests on.",
    "candidate": "A reading that fits, with the thing that would break it named.",
    "assumed": "Asserted by the site's own docs, or inherited from July. Never "
               "watched happen. Treat as suspect.",
    "refuted": "Believed, then disproved. Kept because the reversals are data.",
}


def cell(v):
    return str(v).replace("|", "\\|")


def render():
    cur = facts.current()
    lines = [BEGIN,
             "",
             "## State of knowledge",
             "",
             f"*Generated from `facts.jsonl` by `render.py`. "
             f"{len(cur)} facts, {len(facts.load())} records with history. "
             f"Do not hand-edit this section.*",
             ""]

    counts = {s: sum(1 for r in cur.values() if r["status"] == s) for s in ORDER}
    lines += ["| status | count |", "|---|---|"]
    lines += [f"| {s} | {counts[s]} |" for s in ORDER if counts[s]]
    lines.append("")

    for status in ORDER:
        rows = sorted([r for r in cur.values() if r["status"] == status],
                      key=lambda r: (r["subject"], r["id"]))
        if not rows:
            continue
        lines += [f"### {status} ({len(rows)})", "", BLURB[status], "",
                  "| subject | fact | value | n | source |",
                  "|---|---|---|---|---|"]
        for r in rows:
            val = cell(r["value"])
            if r.get("unit"):
                val += f" {cell(r['unit'])}"
            n = str(r["n"]) if r.get("n") else ""
            lines.append(f"| `{cell(r['subject'])}` | {cell(r['predicate'])} "
                         f"| {val} | {n} | {cell(r['source'])} |")
        lines.append("")

        # The things that would overturn a candidate are the point of having it.
        if status == "candidate":
            for r in rows:
                lines.append(f"- `{r['id']}` breaks if: {r['invalidated_by']}")
            lines.append("")

    # Dependency chains, so a reader can see what a correction would cost.
    derived = [r for r in cur.values() if r.get("derived_from")]
    if derived:
        lines += ["### What rests on what", "",
                  "A fact moving to `refuted` invalidates everything below it.", "",
                  "| fact | rests on |", "|---|---|"]
        for r in sorted(derived, key=lambda r: r["id"]):
            parents = ", ".join(f"`{p}`" for p in r["derived_from"])
            lines.append(f"| `{r['id']}` | {parents} |")
        lines.append("")

    lines += [f"*Rendered {time.strftime('%Y-%m-%d %H:%M')}.*", "", END]
    return "\n".join(lines)


def main():
    block = render()
    if not os.path.exists(DOC):
        print("FINDINGS.md absent")
        return 1
    text = open(DOC, encoding="utf-8").read()

    if BEGIN in text and END in text:
        head = text.split(BEGIN)[0]
        tail = text.split(END, 1)[1]
        text = head + block + tail
    else:
        # First run: drop the block in after the document's opening section.
        marker = "\n## "
        i = text.find(marker, text.find(marker) + 1)
        i = i if i != -1 else len(text)
        text = text[:i] + "\n" + block + "\n" + text[i:]

    open(DOC, "w", encoding="utf-8").write(text)
    cur = facts.current()
    print(f"FINDINGS.md rendu: {len(cur)} faits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
