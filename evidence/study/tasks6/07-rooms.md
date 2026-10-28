# Task 07: rooms (meeting-room booking service)

## Goal

Write a meeting-room booking service driven by a line protocol on stdin and
stdout. Rooms have a capacity; bookings are time ranges within one day.
The service rejects overlapping bookings and names the booking that is in
the way, lists a room's schedule, cancels bookings, and finds the earliest
free slot of a given length during working hours in any room that is big
enough.

## Interface

```
rooms
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print **nothing** on stdout, do not read stdin, and exit `2`.
- **stdin.** One command per line, ASCII. Lines are split on `\n`. If the
  input ends with `\n`, there is no extra empty line after it. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. Flush stdout after every response.
- **Exit codes.** `0` at end of input, `2` usage error.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces.

- `<room>` and `<who>` match `[a-z0-9]{1,12}`.
- `<cap>` and `<people>` match `[1-9][0-9]{0,2}`; `<minutes>` matches
  `[1-9][0-9]{0,3}`.
- A **time** is `HH:MM`, exactly two digits each, from `00:00` to `24:00`
  (`HH` 00-23 with `MM` 00-59, or exactly `24:00`). Times are minutes of one
  day: `HH × 60 + MM`.
- A **booking id** is `B<n>`, where `<n>` matches `[1-9][0-9]{0,8}`.
- A booking covers the half-open range [start, end): `09:00-10:00` and
  `10:00-11:00` do **not** overlap. Two ranges [s1, e1) and [s2, e2) overlap
  if s1 < e2 and s2 < e1.

| Command | Response |
|---|---|
| `ROOM <room> <cap>` | `OK`, or `ERR room exists`. Rooms cannot be removed or changed. |
| `BOOK <room> <start> <end> <who>` | `OK B<n>`: the booking is stored with the next id. Ids are 1, 2, 3, ... in the order bookings succeed, and are never reused. |
| `CANCEL B<n>` | `OK`: the booking is removed. `ERR no such booking` if there is no current booking with this id (never created, or already cancelled). |
| `SCHEDULE <room>` | The room's current bookings sorted by start time, each written `B<n> <start>-<end> <who>`, joined with `, ` (comma and space). `(empty)` if it has none. |
| `FIND <people> <minutes>` | `<room> <start> <end>` for the earliest free slot (rule below), or `NONE`. Nothing is booked. |

Times in responses are written `HH:MM` with two digits each (an end of the
day is `24:00`).

**FIND.** Consider every room with capacity ≥ `<people>`, and every start
time s (a whole minute) with `08:00` ≤ s and s + `<minutes>` ≤ `18:00`, such
that [s, s + `<minutes>`) overlaps none of that room's current bookings. Of
all such (room, s), choose the smallest s; if several rooms have it, the
room with the smallest capacity; if still tied, the room whose name is first
in byte order. Answer with the room, s, and s + `<minutes>`.

**Errors**, checked in this order:

1. A line that is not exactly one of the forms above (unknown or
   lower-case command, wrong token count, malformed name, number, time or
   id, extra spaces, an empty line): `ERR bad command`.
2. `BOOK` with start ≥ end: `ERR bad time`.
3. `BOOK` or `SCHEDULE` naming a room that does not exist:
   `ERR no such room`.
4. `BOOK` whose range overlaps one or more current bookings of the room:
   `ERR conflict B<k>`, where `B<k>` is the overlapping booking with the
   earliest start.

A command that gets an `ERR` response changes nothing (and uses no id).
At most 10000 commands, 100 rooms and 10000 bookings.

## Examples

Each line shown ends with `\n`. cmd is `rooms` in every example.

### Example 1: booking, conflicts, cancelling

stdin:
```
ROOM atlas 8
ROOM nile 4
ROOM atlas 6
BOOK atlas 09:00 10:30 ann
BOOK atlas 10:30 11:00 bob
BOOK atlas 08:00 09:30 cy
BOOK atlas 10:00 12:00 dee
BOOK nile 11:00 11:00 eve
BOOK mars 09:00 10:00 eve
BOOK nile 23:00 24:00 eve
BOOK nile 07:00 25:00 eve
SCHEDULE atlas
SCHEDULE nile
CANCEL B1
CANCEL B1
SCHEDULE atlas
book atlas 09:00 10:00 x
```
stdout:
```
OK
OK
ERR room exists
OK B1
OK B2
ERR conflict B1
ERR conflict B1
ERR bad time
ERR no such room
OK B3
ERR bad command
B1 09:00-10:30 ann, B2 10:30-11:00 bob
B3 23:00-24:00 eve
OK
ERR no such booking
B2 10:30-11:00 bob
ERR bad command
```
exit: `0`

(`10:00-12:00` overlaps both B1 and B2; B1 starts earlier. `25:00` is not a
time.)

### Example 2: finding a free slot

stdin:
```
ROOM big 10
ROOM mid 6
ROOM tiny 2
BOOK mid 08:00 09:00 a
BOOK big 08:30 10:00 b
BOOK tiny 07:00 18:00 c
FIND 2 60
FIND 2 30
FIND 1 480
FIND 7 540
FIND 11 10
ROOM zed 6
ROOM alpha 6
FIND 3 60
CANCEL B2
FIND 8 60
BOOK alpha 08:00 18:00 d
BOOK zed 17:30 24:00 e
FIND 6 600
FIND 6 60
```
stdout:
```
OK
OK
OK
OK B1
OK B2
OK B3
mid 09:00 10:00
big 08:00 08:30
mid 09:00 17:00
NONE
NONE
OK
OK
alpha 08:00 09:00
OK
big 08:00 09:00
OK B4
OK B5
big 08:00 18:00
zed 08:00 09:00
```
exit: `0`

(`FIND 2 30`: `big` is free from 08:00 to 08:30, which is earlier than
`mid` at 09:00. `FIND 7 540`: only `big` is large enough, and after 10:00 no
540 minutes remain before 18:00. `FIND 3 60`: `zed` and `alpha` are both
free at 08:00 with capacity 6; `alpha` comes first by name. `FIND 6 60`:
`big` and `zed` are free at 08:00; `zed` is smaller.)

### Example 3: edges

stdin (the second-last line ends with `\r\n`, and the last line has no
`\n`; the 10th line has two spaces after `r1`):
```
ROOM r1 3
BOOK r1 00:00 24:00 night
SCHEDULE r1
FIND 1 1
CANCEL B1
FIND 1 1
BOOK r1 24:00 24:00 x
BOOK r1 9:00 10:00 x
BOOK r1 09:00 10:00 X
BOOK r1  09:00 10:00 x
CANCEL 1
CANCEL B0
SCHEDULE r2
FIND 0 10
SCHEDULE r1
BOOK r1 12:00 12:01 amy
SCHEDULE r1
```
stdout:
```
OK
OK B1
B1 00:00-24:00 night
NONE
OK
r1 08:00 08:01
ERR bad time
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR no such room
ERR bad command
(empty)
OK B2
B2 12:00-12:01 amy
```
exit: `0`

### Example 4: usage error

cmd: `rooms extra` gives stdout (empty) and exit `2`.

## Not required

- Several days, recurring bookings, or time zones.
- Changing or deleting rooms, or listing bookings by person.
- Any particular stderr wording.
