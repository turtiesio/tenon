# Task 09: helpdesk (persistent support tickets with a journal)

## Goal

Write a persistent support-ticket service driven by a line protocol on stdin
and stdout. Customers open tickets, which get increasing numbers that are
never reused; tickets are assigned to agents, closed and reopened. Every
change is appended to a journal file in a data directory **before** it is
acknowledged, so that the state, including the next ticket number, survives
the process being killed at any moment. On startup the program replays the
journal, discarding a torn last line left by a crash.

## Interface

```
helpdesk DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr, print nothing on stdout, and exit
  `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created, or `DIR` exists but is not a directory, print a
    message to stderr, print nothing on stdout, and exit `1`.
- **Startup.** Load `DIR/tickets.log` as described in "The journal". If it
  is not valid, print a message to stderr, print **nothing** on stdout,
  leave the file unchanged, and exit `1` without reading stdin.
- **stdin.** One command per line, ASCII. Lines are split on `\n`. The last
  line may lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `1` if `DIR` or the journal is
  unusable, `2` for a usage error.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces, except inside a title.

- `<customer>` and `<agent>` match `[a-z0-9]{1,12}`.
- `<ticket>` is `T<n>`, where `<n>` matches `[1-9][0-9]{0,8}`.
- `<title>` is everything after `OPEN <customer> ` (after the second space)
  up to the end of the line: 1 to 60 characters, each from `0x20` (space)
  to `0x7E`, not starting or ending with a space. Inner spaces, including
  runs of several spaces, are part of the title.

| Command | Response |
|---|---|
| `OPEN <customer> <title>` | `T<n>`: a new open, unassigned ticket. Numbers are 1, 2, 3, ... in the order tickets are opened, over the whole life of the journal. |
| `ASSIGN <ticket> <agent>` | `OK` (the ticket is now assigned to `<agent>`, replacing any earlier agent), or `UNCHANGED` if it is already assigned to `<agent>`. |
| `CLOSE <ticket>` | `OK`. The ticket keeps its agent. |
| `REOPEN <ticket>` | `OK`. The ticket is open again and keeps its agent. |
| `SHOW <ticket>` | `T<n> <state> <customer> <agent> <title>`, where `<state>` is `open` or `closed`, and `<agent>` is `-` if the ticket was never assigned. |
| `QUEUE <agent>` | The **open** tickets assigned to `<agent>`, as `T<n>` in increasing number order, joined with single spaces, or `-` if there are none. |
| `QUEUE -` | The same for the open tickets that are not assigned to anyone. |

Errors, checked in this order:

1. A line that is not exactly one of the forms above (unknown or lower-case
   command, wrong token count, malformed name, ticket or title, extra
   spaces, an empty line): `ERR bad command`.
2. A `<ticket>` that was never opened: `ERR no such ticket`.
3. `ASSIGN` or `CLOSE` on a closed ticket: `ERR closed`.
4. `REOPEN` on an open ticket: `ERR not closed`.

A command that gets an `ERR` or `UNCHANGED` response changes nothing.

## The journal

The state is kept in `DIR/tickets.log`, ASCII text. Its format is fixed,
because tests may create it.

1. **Records.** Every command that changes the state is a record, followed
   by `\n`:
   - an `OPEN` answered `T<n>` is recorded as `OPEN T<n> <customer> <title>`
     (the command with the new ticket number inserted after `OPEN`);
   - an `ASSIGN`, `CLOSE` or `REOPEN` answered `OK` is recorded as the
     command line itself (after `\r` removal).

   `SHOW`, `QUEUE`, `UNCHANGED` and errors are not recorded.
2. **Write before answering.** Append the record to the journal and make
   sure it is written to the file (flush it) **before** printing the
   response.
3. **Loading.** A missing journal means no tickets; it is created when the
   first record is written. Otherwise read the file:
   - If it does not end with `\n`, the bytes after the last `\n` (or the
     whole file, if it contains no `\n`) are a **torn** record from a crash.
     Ignore them.
   - Every complete line must be a record in the exact syntax of rule 1.
     Applying the lines in order must succeed: each `OPEN T<n>` record must
     carry exactly the next ticket number, and each other record must be a
     command that would be answered `OK` at that point. Otherwise the journal
     is **not valid** (exit `1` as described above, file unchanged).
   - If the journal is valid and had a torn record, **truncate** the file so
     that it ends right after the last `\n` (or is empty) before writing
     anything new.
4. **Guarantee.** If the process is killed at any moment after printing a
   response, a later run sees exactly the state after all the commands that
   were answered, and the next `OPEN` gets the next number.
5. **Limits.** At most 10000 commands per run, 100000 journal records, and
   100000 tickets.

## Examples

Each line shown ends with `\n`. In every example the working directory
starts empty, except where noted.

### Example 1: a single run

cmd: `helpdesk hd`

stdin (the second line has two spaces between `drops` and `every`; the 12th
line has two spaces after `acme`):
```
OPEN acme Printer on 3rd floor jams
OPEN bolt VPN drops  every hour
ASSIGN T1 kim
ASSIGN T1 kim
ASSIGN T2 lee
ASSIGN T1 lee
CLOSE T1
CLOSE T1
ASSIGN T1 kim
REOPEN T2
REOPEN T1
OPEN acme  leading space
OPEN Acme Upper
SHOW T1
SHOW T2
SHOW T9
QUEUE lee
QUEUE kim
OPEN cog Email
QUEUE -
open x y
```
stdout:
```
T1
T2
OK
UNCHANGED
OK
OK
OK
ERR closed
ERR closed
ERR not closed
OK
ERR bad command
ERR bad command
T1 open acme lee Printer on 3rd floor jams
T2 open bolt lee VPN drops  every hour
ERR no such ticket
T1 T2
-
T3
T3
ERR bad command
```
exit: `0`

Afterwards `hd/tickets.log` contains exactly:
```
OPEN T1 acme Printer on 3rd floor jams
OPEN T2 bolt VPN drops  every hour
ASSIGN T1 kim
ASSIGN T2 lee
ASSIGN T1 lee
CLOSE T1
REOPEN T1
OPEN T3 cog Email
```

### Example 2: killed, then restarted

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `helpdesk d`, killed right after its 3rd output line. Input
is sent one line at a time, so `CLOSE T2` is never sent.

stdin:
```
OPEN acme Broken chair
OPEN bolt No coffee
ASSIGN T2 kim
CLOSE T2
```
stdout before the kill:
```
T1
T2
OK
```

**Step 2**: cmd `helpdesk d`.

stdin:
```
SHOW T2
OPEN cog Desk lamp
QUEUE kim
```
stdout:
```
T2 open bolt kim No coffee
T3
T2
```
exit: `0`

### Example 3: a torn last record

This is a multi-run test with two steps. The working directory starts with
`d/tickets.log` containing exactly the bytes
`OPEN T1 acme Chair\nCLOSE T1\nASSIGN T1 ki` (no final newline).

**Step 1**: cmd `helpdesk d`.

stdin:
```
SHOW T1
REOPEN T1
OPEN bolt Desk
```
stdout:
```
T1 closed acme - Chair
OK
T2
```
exit: `0`

**Step 2**: cmd `helpdesk d`.

stdin:
```
SHOW T1
SHOW T2
```
stdout:
```
T1 open acme - Chair
T2 open bolt - Desk
```
exit: `0`

(The torn `ASSIGN T1 ki` was discarded and cut off, so the new records
start on their own line.)

### Example 4: errors

- The working directory starts with `d/tickets.log` containing exactly
  `OPEN T2 acme Chair\n` (the first ticket must be `T1`). cmd: `helpdesk d`
  with stdin `SHOW T1\n` gives stdout (empty) and exit `1`.
- The working directory starts with `d/tickets.log` containing exactly
  `OPEN T1 acme Chair\nASSIGN T1 kim\nASSIGN T1 kim\n` (the third record
  would be `UNCHANGED`). cmd: `helpdesk d` with stdin `SHOW T1\n` gives
  stdout (empty) and exit `1`.
- The working directory contains a regular file `f`. cmd: `helpdesk f` with
  stdin `SHOW T1\n` gives stdout (empty) and exit `1`.
- cmd: `helpdesk` gives stdout (empty) and exit `2`.
- cmd: `helpdesk a b` gives stdout (empty) and exit `2`.

## Not required

- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the
  process is required. `fsync` is optional.
- Compacting the journal, deleting tickets, or comments on tickets.
- Concurrent processes on the same `DIR`.
- Any particular stderr wording.
