"""Guards the showcase against the mistakes a public page cannot take back.

Run before every commit: python scripts/check.py  (exit 0 = clean)

It fails on:
  - an em or en dash (the owner's writing rule)
  - the production Supabase project ref
  - the owner's surname anywhere but the one credit line in README.md
  - a relative link or image path that does not resolve to a file

It cannot see pixels: a real person's name inside a screenshot is a human's check.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DASHES = ("—", "–")
FORBIDDEN = ("ghcclshgdtbystosfzjl",)
SURNAME = "Pokhrel"
CREDIT = "Built by Aayush Pokhrel"
LINK = re.compile(r"\]\(([^)\s]+)\)|src=\"([^\"]+)\"")

problems = []
surname_hits = []

for path in sorted(ROOT.rglob("*")):
    if path.suffix not in (".md", ".svg") or ".git" in path.parts:
        continue
    rel = path.relative_to(ROOT)
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for d in DASHES:
            if d in line:
                problems.append(f"{rel}:{n}: dash {d!r}")
        for f in FORBIDDEN:
            if f in line:
                problems.append(f"{rel}:{n}: forbidden string {f!r}")
        if SURNAME in line:
            surname_hits.append((rel, n, line))
        for m in LINK.finditer(line):
            target = (m.group(1) or m.group(2)).split("#")[0]
            if not target or re.match(r"[a-z]+:", target):
                continue  # in-page anchor, or an absolute URL / mailto
            if not (path.parent / target).exists():
                problems.append(f"{rel}:{n}: broken link {target!r}")

ok_credit = [h for h in surname_hits if str(h[0]) == "README.md" and CREDIT in h[2]]
if len(surname_hits) != 1 or len(ok_credit) != 1:
    for rel, n, _ in surname_hits:
        problems.append(f"{rel}:{n}: surname must appear exactly once, in README.md's credit line")
    if not surname_hits:
        problems.append("README.md: credit line missing")

for p in problems:
    print(p)
sys.exit(1 if problems else 0)
