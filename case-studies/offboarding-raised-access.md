# Offboarding an employee increased their access

**In one line:** a permission check in Postgres refused every wrong role, and let through
anyone who had no role at all. That included an employee the kitchen had just removed.

## What went wrong

The kitchen app records which version of a dish a restaurant approved, so a cook, a chef and
an owner can do different things. Creating a dish, revising it, sending it to a trial and
signing it onto the live menu are all limited to owners and chefs.

Each of those steps is a Postgres function, and each started with a gate like this:

```sql
if kitchen.staff_role(v_org) not in ('owner', 'chef') then
  raise exception 'only an owner or a chef may start a dish';
end if;
```

A cook was correctly refused. But once the owner **removed** that cook from the kitchen, the
same person could create a dish, revise it, trial it and sign it onto the live menu, with an
approval recorded in their own name. Removing someone's access gave them more of it.

## How it was found

Through a full security audit I ran myself, on the kitchen app's launch day. It was the
audit's only finding rated HIGH. Nothing in the existing tests caught it, because every test
used a person who *had* a role, just the wrong one.

## Why it happened

`staff_role()` is a plain lookup. For someone with no staff row, it returns `NULL`, not an
empty string.

In SQL, `NULL not in ('owner', 'chef')` is not `true`. It is `NULL`. And in PL/pgSQL, an
`IF` whose condition is `NULL` skips its body. So the `raise` never ran, and the function
carried on into the privileged work.

A second fault made it reachable. Functions added after the schema's first migration kept
Postgres's default `EXECUTE` grant to `PUBLIC`, so any signed-in user could call them
directly, even with no connection to that kitchen.

The direction is what matters:

- `if role = 'owner' then <do the work>` fails **closed**. A `NULL` skips the work.
- `if role not in (...) then <refuse>` fails **open**. A `NULL` skips the refusal.

## The fix

One migration replaced all four functions and wrapped the lookup:
`coalesce(kitchen.staff_role(v_org), '') not in ('owner', 'chef')`. It also revoked
`EXECUTE` from `PUBLIC` across the kitchen schema and re-granted it only to signed-in users.
Every later migration ends with the same three-line revoke and re-grant.

## What stops it coming back

This was the **second** time the same class of bug turned up in unrelated code. An earlier
migration nearly shipped a function returning `NULL` instead of `false` into a policy behind
`not`, which would have hidden the public feed from every signed-out visitor. Twice is a
pattern, so the guard became a test rather than a note:

- **A static check** over every migration fails on a negated comparison (`not in`, `<>`,
  `!=`) against a lookup that can return `NULL`. It judges only the latest definition of each
  function, and it ignores SQL comments, so the fix's own explanation of the bug does not trip
  it.
- **Another static check** fails if the kitchen schema's blanket `EXECUTE` revoke ever goes
  missing.
- **Integration tests** run against a real database as an ordinary user and try the exploit:
  a complete outsider, an anonymous visitor, and a removed employee all try every step of the
  pipeline, and all are refused. A final test confirms the real owner can still run it, so the
  fix did not simply lock everyone out.

## What I took from it

Test the person with **no** role, not just the person with the wrong one. And when a check
can see `NULL`, write it so that `NULL` refuses.
