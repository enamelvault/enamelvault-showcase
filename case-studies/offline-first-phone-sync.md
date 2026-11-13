# Editing recipes with no signal

The phone app lets a cook read, edit and even create recipes with no connection, then sends
the changes when the signal comes back. This is a design write-up rather than a bug story,
and one caveat comes first: **the phone app is built and tested, but it has not yet run on a
real phone.** Everything below is checked by tests, not by use in a real kitchen.

## Why offline

The family web app already works in a phone browser. A browser tab can't work with no
signal, though, and the two places this app gets used are a kitchen with patchy wifi and a
shop with none. So the phone keeps a copy of every recipe the cook can read in a local
SQLite database, and treats the network as something that comes and goes.

## The hard part: a queue that lies

The easy version of offline sync is a list of pending writes that gets sent later. The
trouble is that the server's security rules decline some writes, and a declined write comes
back as a success that changed nothing. (The [refused writes](silent-refused-writes.md)
case study covers this.) On the web, someone is looking at the screen when that happens. An
offline queue replays hours later with nobody watching, so a refusal there turns into lost
work that nobody notices.

So the queue follows three rules:

1. Every queued write asks for the row it wrote back, and treats getting nothing back as a
   failure.
2. A failed write is shown to the cook, on the recipe and on their shelf. It is never retried
   forever in silence, and never dropped.
3. One failure doesn't hold up the rest. If the cook has lost access to one recipe, their
   other edits still go through.

The phone also gets no authority of its own. The server's rules still decide what is
allowed, and the queue only changes when a write is attempted.

## Queueing intents, not rows

A queued edit doesn't overwrite the recipe's row directly. It records what the cook meant
to do, plus the version of the recipe they started from, and replays through the same
server function the web app uses to publish an edit. Some of the publishing rules live in a
database trigger, and a second write path would be one more place for a rule to be
forgotten. This project has had to fix a rule that lived in two places twice already.

## Two people edit the same recipe

When a queued edit reaches the server, the phone checks whether the recipe has changed since
the edit began. That is an exact comparison of the timestamp string the server returned, not
a date comparison, because a date conversion is how timezone bugs get in, and the app has
already had one.

If the recipe has moved on, the edit stops as a **conflict**. Silently letting the last
write win would destroy somebody's work. The conflict screen shows both versions and the
cook picks one, and the screen has to make it obvious which version is whose before they
tap. The queue never replays a conflicted edit on its own, since that would be sending a
decision nobody made.

## Creating a recipe offline

A recipe created with no signal needs an id before the server has assigned one. It gets a
temporary id with a `local:` prefix, so no code can mistake it for a real one. When the
create goes through, the temporary id is replaced by the server's everywhere it appears,
inside one database transaction, including in later queued edits to the same recipe. The
queue is re-read after every write for that reason: replaying from a stale snapshot would
send a later edit against an id the server has never heard of.

## Losing access

When the phone catches up, it fetches the full list of recipes the cook can currently read,
not just what changed since last time. A list of changes can't express a recipe someone has
lost access to, because that is an absence. With an incremental list, the phone would keep
serving a private copy of a recipe the family had taken back. The full list costs more on
every catch-up, and at a family's number of recipes that is the right trade.

## Where it stands

The sync engine, the local store, the conflict screen, Cook Mode and timers that ring with
the phone locked are all built, with unit tests around the queue, replay, conflicts and
catch-up. What's left is the part tests can't do: running it on a real phone, in a real
kitchen, with the signal actually dropping.
