# A refused write is not an error

**In one line:** the database blocked writes correctly, but it blocked them silently, so the
app told people "Saved" when nothing had been saved.

## What went wrong

Security in Enamel Vault lives in Postgres row-level security (RLS): every table has
policies saying who may read and who may write each row. Sharing features make the two
different. A family member may **read** a relative's recipe but not **edit** it. Anyone a
meal plan is shared with may **read** it, but only its owner may **change** it.

Three bugs shipped from that gap, all in the same shape:

- A family member who opened a relative's recipe by typing its edit address could make
  changes, press Save, and see "Saved". Nothing was written, and the work was lost.
- A shared meal plan offered every control to a relative: Remove, the servings steppers,
  the day and slot pickers, drag to reorder. None of them worked. A removed item quietly came
  back on the next refresh.
- The comment thread offered Delete on every comment in the family, not just your own.

In every case the database did the right thing. **Nobody was able to change anything they
should not have.** The damage was to trust: the app said one thing and did another.

## How it was found

The first one turned up in a security pass looking for a different hole, which turned out
not to be there. Then I went looking for the same shape everywhere else, and found the other
two the same day.

## Why it happened

A policy does not *reject* a row. It fails to *match* it. So an `UPDATE` or `DELETE` that
RLS declines affects zero rows and finishes successfully. The Supabase client resolves with
`error: null`, and code that only checked for an error carried on as if the write had
happened:

```ts
const { error } = await supabase.from("recipes").update(changes).eq("id", id);
if (error) throw error;
// No error, and also nothing written.
```

The interface made it worse. It hid the Edit button from people who could not edit, which
looked like enough. But the edit page was still a normal URL, and a hidden button is not a
locked door.

## The fix

Two rules, applied everywhere:

1. **Every write in the data layer asks for the rows it wrote back, and throws if none
   come back.** A refused write now fails loudly, with a message that says what was refused.
2. **A page never shows a control the viewer's policy would refuse.** The recipe page, the
   meal plan page and the comment thread each work out what the viewer may do, from the same
   rules the database uses, before drawing a button.

One useful exception came out of it. A `SELECT ... FOR UPDATE` applies the **update**
policy, not just the read policy, so it refuses early and loudly. That is why one function
was already safe while the plain call next to it was not, and why removing a `FOR UPDATE` to
tidy a function can quietly open it.

## What stops it coming back

The lesson had been written down beside the first bug, and the same mistake still shipped
twice more. So it became tests rather than prose:

- **An integration test pins what the database actually does**: as an ordinary user, it
  attempts a refused delete on a comment, a refused delete on a recipe, and a refused write
  to someone else's shared plan, and asserts that each one comes back as success with zero
  rows. A final test confirms the owner can still do all three. If anyone later "simplifies"
  the guards on the belief that an error would be raised, this test is the proof that it
  would not.
- **Unit tests** hold the data-layer functions to throwing when nothing comes back, and
  were watched failing with the check removed before they were trusted.
- **Page tests** check that a viewer who cannot edit is not shown the controls.

## What I took from it

When reading is wider than writing, every write needs its own proof that it happened.
"No error" is not the same as "it worked".
