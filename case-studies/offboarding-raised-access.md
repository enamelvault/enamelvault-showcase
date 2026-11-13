# Offboarding an employee increased their access

A permission check in Postgres refused every wrong role and let through anyone with no role
at all, including an employee the kitchen had just removed.

## What went wrong

The kitchen app records which version of a dish a restaurant approved, and cooks, chefs and
owners can do different things in it. Only owners and chefs can create a dish, revise it,
send it to a trial and sign it onto the live menu.

Each of those steps is a Postgres function, and each started with a gate like this:

```sql
if kitchen.staff_role(v_org) not in ('owner', 'chef') then
  raise exception 'only an owner or a chef may start a dish';
end if;
```

A cook was correctly refused. Once the owner removed that cook from the kitchen, though, the
same person could create a dish, revise it, trial it and sign it onto the live menu, with
the approval recorded in their own name. Taking their access away had given them more of it.

## How it was found

I ran a full security audit of my own on the day the kitchen app launched, and this was its
only finding rated HIGH. None of the existing tests caught it, because every one of them used
a person who had a role, just the wrong one.

## Why it happened

`staff_role()` is a plain lookup, and for someone with no staff row it returns `NULL`.

In SQL, `NULL not in ('owner', 'chef')` isn't `true`, it's `NULL`. PL/pgSQL skips the body
of an `IF` whose condition is `NULL`, so the `raise` never ran and the function carried on
into the privileged work.

A second fault made this reachable. Functions added after the kitchen schema's first
migration kept Postgres's default grant of `EXECUTE` to `PUBLIC`, so any signed-in user could
call them directly, with no connection to that kitchen at all.

Which way a check is written decides how it fails. `if role = 'owner' then <do the work>`
fails closed, because a `NULL` skips the work. `if role not in (...) then <refuse>` fails
open, because a `NULL` skips the refusal.

## The fix

One migration replaced all four functions and wrapped the lookup as
`coalesce(kitchen.staff_role(v_org), '') not in ('owner', 'chef')`. The same migration
revoked `EXECUTE` from `PUBLIC` across the kitchen schema and granted it back only to
signed-in users. Every kitchen migration since then ends with that revoke and re-grant.

## What stops it coming back

This was the second time the same kind of bug had turned up in unrelated code. An earlier
migration nearly shipped a function that returned `NULL` instead of `false` into a policy
behind `not`, which would have hidden the public feed from every signed-out visitor. With two
cases, a note wasn't going to be enough, so the guard became tests:

- A static check over every migration fails on a negated comparison (`not in`, `<>`, `!=`)
  against a lookup that can return `NULL`. It judges only the latest definition of each
  function and ignores SQL comments, so the fix's own explanation of the bug doesn't trip it.
- A second static check fails if the kitchen schema's blanket `EXECUTE` revoke ever goes
  missing.
- Integration tests run against a real database as an ordinary user and attempt the exploit.
  A complete outsider, an anonymous visitor and a removed employee each try every step of
  the pipeline and are refused. One more test confirms the real owner can still run it, so
  the fix didn't just lock everybody out.

## What I took from it

Test the person with no role, not only the person with the wrong one. And when a check can
see `NULL`, write it so that `NULL` refuses.
