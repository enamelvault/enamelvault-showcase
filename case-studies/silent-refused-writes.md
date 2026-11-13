# A refused write is not an error

The database blocked writes correctly, but it blocked them silently, so the app told people
"Saved" when nothing had been saved.

## What went wrong

Security in Enamel Vault lives in Postgres row-level security (RLS): each table has policies
saying who may read each row and who may write it. Sharing features make those two
different. A family member may read a relative's recipe but not edit it, and anyone a meal
plan is shared with may read it while only its owner may change it.

Three bugs shipped from that gap, all with the same shape:

- A family member who opened a relative's recipe by typing its edit address could make
  changes, press Save and see "Saved". Nothing was written, and the work was lost.
- A shared meal plan offered every control to a relative, including Remove, the servings
  steppers, the day and slot pickers and drag to reorder. None of them worked, and a removed
  item came back on the next refresh.
- The comment thread offered Delete on every comment in the family, not only your own.

In each case the database did its job, and nobody changed anything they shouldn't have. The
harm was that the app said one thing and did another.

## How it was found

The first one turned up during a security pass that was looking for a different hole, which
turned out not to exist. I then looked for the same shape everywhere else and found the
other two that day.

## Why it happened

A policy doesn't reject a row. It fails to match it, so an `UPDATE` or `DELETE` that RLS
declines affects zero rows and finishes successfully. The Supabase client resolves with
`error: null`, and code that only checked for an error carried on as if the write had
happened:

```ts
const { error } = await supabase.from("recipes").update(changes).eq("id", id);
if (error) throw error;
// No error, and also nothing written.
```

The interface made it worse. It hid the Edit button from people who couldn't edit, which
looked like enough, but the edit page was still an ordinary URL anyone could type.

## The fix

Two rules now apply everywhere:

1. Every write in the data layer asks for the rows it wrote back and throws if none come
   back, so a refused write fails loudly with a message saying what was refused.
2. A page never shows a control the viewer's policy would refuse. The recipe page, the meal
   plan page and the comment thread each work out what the viewer may do, from the same rules
   the database uses, before drawing a button.

There's one useful exception. A `SELECT ... FOR UPDATE` applies the update policy as well as
the read policy, so it refuses early and loudly. That's why one function was already safe
while the plain call next to it wasn't, and why removing a `FOR UPDATE` while tidying a
function can open it up without anyone noticing.

## What stops it coming back

The lesson had been written down next to the first bug, and the same mistake still shipped
twice more. So it became tests instead of prose:

- An integration test pins what the database actually does. As an ordinary user, it attempts
  a refused delete on a comment, a refused delete on a recipe and a refused write to someone
  else's shared plan, and asserts that each comes back as success with zero rows. A last test
  confirms the owner can still do all three. If anyone later removes the guards believing an
  error would be raised, this test shows it wouldn't.
- Unit tests hold the data-layer functions to throwing when nothing comes back. They were
  watched failing with the check removed before they were trusted.
- Page tests check that a viewer who can't edit isn't shown the controls.

## What I took from it

When reading is wider than writing, every write needs its own proof that it happened. No
error doesn't mean it worked.
