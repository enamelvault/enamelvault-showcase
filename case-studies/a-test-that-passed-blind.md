# A test that passed without looking

**In one line:** a guard test kept reporting PASSED while it could not even see the file it
was guarding, and that turned out to be a pattern, not a one-off.

## What went wrong

The project keeps a short status file that each working session reads at the start and
updates at the end. Left alone it bloats: it once reached 1,365 lines and began contradicting
itself, and a stale line in it caused real wrong work. So a test enforces a budget: the file
must stay under 200 lines, with no dated diary entries.

That test was green. It was also measuring nothing in most of the sessions doing the work.

## How it was found

By asking a simple question of a green test: what did it actually read on its last run in
a worktree? The answer was nothing.

## Why it happened

The status file is deliberately not committed to git, so it exists only in the main copy of
the repository. Most working sessions run in a separate **git worktree**, a second checkout
of the same repository, and a worktree does not get uncommitted files.

The test looked for the file relative to the current folder. In a worktree it found nothing,
treated that as "this machine has no status file", returned early, and reported **PASSED**.
A skipped check and a passing check looked exactly the same.

## The same shape, elsewhere

Once I knew the shape, I found it twice more:

- **A route guard that only read one app.** A test checks that every route that *does*
  something sits behind the terms-acceptance gate. It read the family app's router. The
  repository holds several apps, and the kitchen app shipped with its whole surface ungated
  while the suite stayed green, because a guard covering one app reports success for the
  apps it cannot see.
- **A fingerprint that could hash the wrong file.** A test fingerprints the terms page so
  that changing the wording forces a version bump. Both apps have a page at
  `pages/Terms.tsx`. Matching by a short suffix would have quietly hashed the kitchen's
  terms instead of the family's: it would fail once, get its hash updated, and then pass
  forever while guarding the wrong document.

## The fix

- **The status-file test finds the main checkout itself** with
  `git rev-parse --git-common-dir`, which returns the main repository's `.git` folder even
  from inside a worktree. One code path now works in both places.
- **It also checks its own mechanism.** A third test, which never skips, confirms the main
  checkout was actually found. If the lookup ever breaks again, that test fails instead of
  the other two going quiet.
- **Every app's router now has its own guard**, and the phone app is guarded by its
  structure rather than a scan: its screens are only ever drawn inside the gate, so no route
  can escape it.
- **The fingerprint helper refuses an ambiguous path.** A short suffix that matches two
  files now throws, so the caller has to name the full path.

## What stops it coming back

The rule I now apply to every check: **watch it fail before trusting it passing.** Break the
thing it guards on purpose, see it go red, then put it back. A check nobody has seen fail is
not evidence of anything, and a guard that cannot see its subject is worse than no guard,
because it also reports success.

## What I took from it

"Skipped" must never look like "passed". When a check depends on finding something, the
finding is a thing to test too.
