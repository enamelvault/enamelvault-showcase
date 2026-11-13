# A test that passed without looking

A guard test kept reporting PASSED while it couldn't see the file it was guarding. Once I
knew to look, I found the same mistake in two other tests.

## What went wrong

The project keeps a short status file that each working session reads at the start and
updates at the end. Left alone, it grows: it once reached 1,365 lines and began
contradicting itself, and a stale line in it led to real wrong work. So a test enforces a
budget of 200 lines and no dated diary entries.

The test was green. In most of the sessions doing the work, it was also measuring nothing.

## How it was found

I asked a green test what it had actually read on its last run in a worktree, and the
answer was nothing.

## Why it happened

The status file is deliberately left out of git, so it exists only in the main copy of the
repository. Most working sessions run in a separate git worktree, which is a second checkout
of the same repository, and a worktree doesn't get files that were never committed.

The test looked for the file relative to the current folder. In a worktree it found
nothing, took that to mean "this machine has no status file", returned early, and reported
PASSED. A skipped check looked exactly like a passing one.

## The same mistake in two other tests

A test checks that every route that does something sits behind the terms-acceptance gate.
It read only the family app's router. The repository holds several apps, and the kitchen app
shipped with its whole surface outside the gate while the suite stayed green, because a
guard that covers one app reports success for the apps it can't see.

Another test fingerprints the terms page, so that changing the wording forces a version
bump. Both apps have a page at `pages/Terms.tsx`, and matching by a short suffix would have
hashed the kitchen's terms instead of the family's. It would have failed once, had its hash
updated, and then passed for good while guarding the wrong document.

## The fix

The status-file test now finds the main checkout itself, with
`git rev-parse --git-common-dir`. That returns the main repository's `.git` folder even from
inside a worktree, so one code path works in both places. A third test, which never skips,
confirms that the main checkout was found. If the lookup breaks again, that test fails
instead of the other two going quiet.

Every app's router now has its own guard. The phone app is guarded by its structure instead
of a scan: its screens are only ever drawn inside the gate, so no route can get outside it.

The fingerprint helper now throws when a short path matches two files, so the caller has to
give the full path.

## What stops it coming back

I now watch every check fail before I trust it passing: break the thing it guards on
purpose, see it go red, then put it back. A check nobody has seen fail isn't evidence of
anything. A guard that can't see what it's guarding is worse than having no guard, because
it still reports success.

## What I took from it

A skip must never look like a pass. When a check depends on finding something, test the
finding too.
