# Task 09: todo (persistent to-do list with atomic snapshots)

## Goal

Write a persistent to-do list service driven by a line protocol on stdin and
stdout. Items have a number, a priority and a text, and can be marked done
and purged. The whole state is kept in one file in a data directory, which
is **replaced atomically** (write a temporary file, then rename it) after
every change and **before** the change is acknowledged. So the state survives
the process being killed at any moment. On startup the program loads the
file, validates it strictly, and ignores a leftover temporary file.

## Interface

```
todo DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr and exit `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created, or `DIR` exists but is not a directory, print a
    message to stderr and exit `1`.
- **Startup.** First delete `DIR/todo.db.tmp` if it exists (rule 6). Then load
  `DIR/todo.db` (see "The state file"). If that file exists but is not valid,
  print a message to stderr, print **nothing** on stdout, leave the file
  unchanged, and exit `1` without reading stdin.
- **stdin.** One command per line. Lines are split on `\n`. The last line may
  lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `1` if `DIR` or `todo.db` is unusable,
  `2` for a usage error.

## Items

An item has:

- an **id**: a positive integer. Ids are assigned from a counter `next`
  that starts at 1 and only ever increases, so an id is **never reused**, not
  even after the item is purged or the program restarts;
- a **priority**: a digit `1`-`9` (1 is the most urgent);
- a **status**: open or done;
- a **text**: one or more characters, each a space or a printable ASCII
  character (bytes 0x20-0x7E).

## Commands

Command names are upper case. Tokens are separated by exactly one space.
`<id>` must match `[0-9]{1,9}` (leading zeros allowed). `<prio>` is one digit
`1`-`9`. `<text>` is the **rest of the line** after the space that follows
`<prio>`; it must not be empty and may contain spaces.

| Command | Response |
|---|---|
| `ADD <prio> <text>` | `ADDED <id>`: creates an open item with the id `next`, then increases `next` by 1. |
| `DONE <id>` | `OK`: marks the item done. `ERR no such item` if no item has this id; `ERR already done` if it is done. |
| `SHOW <id>` | `<id> <prio> <open\|done> <text>`, or `ERR no such item`. |
| `LIST` | `OPEN` followed by a space and the ids of all **open** items, sorted by priority ascending, then id ascending, separated by single spaces. Just `OPEN` if there are none. |
| `NEXT` | The first item that `LIST` would show, in the `SHOW` format, or `NONE`. |
| `PURGE` | `PURGED <k>`: deletes all done items; k is how many. |
| `STATS` | `open=<a> done=<b> next_id=<n>` |

Ids in responses are written without leading zeros. In the `SHOW` format the
status is the word `open` or `done` (the `\|` in the table is only Markdown
escaping for `|`).

Any other line (unknown or lower-case command, wrong number of tokens, a bad
id, a priority that is not one digit `1`-`9`, an empty text, a character
outside 0x20-0x7E, an empty line) gets `ERR bad command` and changes nothing.

## The state file

The state lives in `DIR/todo.db`. Its format is fixed, because tests may
create it. It is ASCII, and every line, including the last, ends with `\n`:

```
TODO 1
next <n>
<id> <prio> <o|d> <text>
...
```

- Line 1 is exactly `TODO 1`.
- Line 2 is `next ` followed by `n` matching `[1-9][0-9]{0,8}`.
- Every further line is one item: `<id>` matching `[1-9][0-9]{0,8}`, one
  space, `<prio>` (`1`-`9`), one space, `o` (open) or `d` (done), one space,
  and the text (everything up to the `\n`, non-empty, bytes 0x20-0x7E).
- Item ids are strictly increasing from line to line, and every id is
  smaller than `n`.

A file that breaks any of these rules (including an empty file, or a missing
final `\n`) is **not valid**. A missing `todo.db` means an empty list with
`next` = 1.

## Rules

1. **Writing.** After each command that changes the state (a successful
   `ADD`, a successful `DONE`, and a `PURGE` that deletes at least one item),
   and **before** printing its response, write the complete new state in the
   format above (items in id order) to `DIR/todo.db.tmp`, make sure it is
   written to the file (flush or close it), and rename it to `DIR/todo.db`,
   replacing the old file. Commands that do not change the state need not
   write.
2. **Guarantee.** If the process is killed at any moment after printing a
   response, a later run sees exactly the state after all the commands that
   were answered.
3. **Ids after restart.** `next` is part of the state file, so ids continue
   after a restart and are not reused after `PURGE`.
4. **Responses are exact strings.** The only error responses are
   `ERR bad command`, `ERR no such item` and `ERR already done`.
5. **Limits.** At most 10000 commands per run and 10000 items. Texts are at
   most 200 bytes.
6. **Leftover temporary file.** A `DIR/todo.db.tmp` found at startup may be
   left over from a crash and may contain anything. It is deleted and never
   affects the state.

## Examples

Each line shown ends with `\n`. In every example the working directory starts
empty, except where noted.

### Example 1: a single run

cmd: `todo data`

stdin:
```
ADD 2 buy milk
ADD 1 fix the roof
ADD 2 call mom
LIST
NEXT
DONE 2
DONE 2
DONE 9
LIST
SHOW 2
PURGE
STATS
ADD 3 water plants
SHOW 04
```
stdout:
```
ADDED 1
ADDED 2
ADDED 3
OPEN 2 1 3
2 1 open fix the roof
OK
ERR already done
ERR no such item
OPEN 1 3
2 1 done fix the roof
PURGED 1
open=2 done=0 next_id=4
ADDED 4
4 3 open water plants
```
exit: `0`

### Example 2: killed, then restarted

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `todo d`, killed right after its 3rd output line. Input is
sent one line at a time, so `ADD 3 gamma` is never sent.

stdin:
```
ADD 1 alpha
ADD 2 beta
DONE 1
ADD 3 gamma
```
stdout before the kill:
```
ADDED 1
ADDED 2
OK
```

**Step 2**: cmd `todo d`.

stdin:
```
STATS
LIST
ADD 1 delta
```
stdout:
```
open=1 done=1 next_id=3
OPEN 2
ADDED 3
```
exit: `0`

### Example 3: ids are never reused

This is a multi-run test with two steps.

**Step 1**: cmd `todo d`.

stdin:
```
ADD 1 a
DONE 1
PURGE
STATS
```
stdout:
```
ADDED 1
OK
PURGED 1
open=0 done=0 next_id=2
```
exit: `0`

**Step 2**: cmd `todo d`.

stdin:
```
ADD 1 b
SHOW 1
LIST
```
stdout:
```
ADDED 2
ERR no such item
OPEN 2
```
exit: `0`

### Example 4: an existing state file and a leftover temporary file

The working directory starts with `d/todo.db`:
```
TODO 1
next 8
3 2 o water plants
5 1 d pay rent
7 1 o book flights
```
and `d/todo.db.tmp` containing `garbage` (no newline).

cmd: `todo d`

stdin:
```
LIST
NEXT
STATS
ADD 5 later
SHOW 5
```
stdout:
```
OPEN 7 3
7 1 open book flights
open=2 done=1 next_id=8
ADDED 8
5 1 done pay rent
```
exit: `0`

### Example 5: errors

- The working directory starts with `d/todo.db` containing exactly the bytes
  `TODO 1\nnext 3\n5 1 o x\n` (id 5 is not smaller than `next`). cmd:
  `todo d` with stdin `LIST\n` gives stdout (empty) and exit `1`.
- The working directory starts with `d/todo.db` containing exactly the bytes
  `TODO 1\nnext 3\n1 1 o x` (no final newline). cmd: `todo d` with stdin
  `LIST\n` gives stdout (empty) and exit `1`.
- cmd: `todo` gives stdout (empty) and exit `2`.
- cmd: `todo a b` gives stdout (empty) and exit `2`.
- The working directory contains a regular file `f`. cmd: `todo f` gives
  stdout (empty) and exit `1`.
- cmd: `todo d` with stdin `ADD 0 x\nADD 10 x\nADD 1 \nadd 1 x\nDONE x\n`
  gives stdout `ERR bad command\n` five times and exit `0`.

## Not required

- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the process
  is required. `fsync` is optional.
- Concurrent processes on the same `DIR`.
- Editing item texts or priorities, or reopening done items.
- Any particular stderr wording.
