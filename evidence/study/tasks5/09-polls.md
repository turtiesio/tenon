# Task 09: polls (persistent voting service with a journal)

## Goal

Write a persistent poll service driven by a line protocol on stdin and
stdout. Polls have a fixed list of options; each voter has at most one vote
per poll and may change it until the poll is closed. Every change is
appended to a journal file in a data directory **before** it is
acknowledged, so the state survives the process being killed at any moment.
On startup the program replays the journal, discarding a torn last line
left by a crash.

## Interface

```
polls DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr and exit `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created, or `DIR` exists but is not a directory, print a
    message to stderr and exit `1`.
- **Startup.** Load `DIR/polls.log` as described in "The journal". If it is
  not valid, print a message to stderr, print **nothing** on stdout, leave
  the file unchanged, and exit `1` without reading stdin.
- **stdin.** One command per line. Lines are split on `\n`. The last line
  may lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `1` if `DIR` or the journal is
  unusable, `2` for a usage error.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces. Every `<poll>`, `<voter>` and `<option>`
matches `[a-z0-9]{1,12}`.

| Command | Response |
|---|---|
| `CREATE <poll> <o1> <o2> ...` | 2 to 9 options, all different. `OK`, or `ERR poll exists` if a poll with this name exists (open or closed). |
| `VOTE <poll> <voter> <option>` | `VOTED` if the voter had no vote in this poll; `CHANGED` if the voter had voted for a different option (the vote is replaced); `UNCHANGED` if the voter had already voted for this option. |
| `CLOSE <poll>` | `OK`. The poll stays readable but accepts no more votes. |
| `RESULT <poll>` | `<poll> <open\|closed>` followed by ` <option>=<count>` for every option in the order given at `CREATE`. |

(The `\|` in the table is only Markdown escaping for `|`; the response
contains the word `open` or `closed`.)

Errors, checked in this order:

- A line that is not exactly one of the forms above (unknown or lower-case
  command, wrong token count, malformed name, fewer than 2 or more than 9
  options, a repeated option in `CREATE`, extra spaces, an empty line):
  `ERR bad command`.
- `VOTE`, `CLOSE` or `RESULT` naming a poll that does not exist:
  `ERR no such poll`.
- `VOTE` or `CLOSE` on a closed poll: `ERR poll closed`.
- `VOTE` with an option that the poll does not have: `ERR no such option`.

A command that gets an `ERR` response changes nothing.

## The journal

The state is kept in `DIR/polls.log`. Its format is fixed, because tests may
create it.

1. **Records.** Every command that changes the state (a `CREATE` or `CLOSE`
   answered `OK`, a `VOTE` answered `VOTED` or `CHANGED`) is a record. Its
   record is the command line itself (after `\r` removal) followed by
   `\n`. `RESULT`, `UNCHANGED` votes and errors are not recorded.
2. **Write before answering.** Append the record to the journal and make
   sure it is written to the file (flush it) **before** printing the
   response.
3. **Loading.** A missing journal means no polls; it is created when the
   first record is written. Otherwise read the file:
   - If it does not end with `\n`, the bytes after the last `\n` (or the
     whole file, if it contains no `\n`) are a **torn** record from a
     crash. Ignore them and **truncate** the file so that it ends right
     after the last `\n` (or is empty), before writing anything new.
   - Every complete line must be a `CREATE`, `VOTE` or `CLOSE` command in
     the exact syntax above, and applying the lines in order must give each
     of them the response `OK`, `VOTED` or `CHANGED`. Otherwise the journal
     is **not valid** (exit `1` as described above).
4. **Guarantee.** If the process is killed at any moment after printing a
   response, a later run sees exactly the state after all the commands that
   were answered.
5. **Limits.** At most 10000 commands per run, 100000 journal records, and
   1000 polls.

## Examples

Each line shown ends with `\n`. In every example the working directory
starts empty, except where noted.

### Example 1: a single run

cmd: `polls data`

stdin:
```
CREATE lunch pizza sushi tacos
VOTE lunch ann sushi
VOTE lunch bob pizza
VOTE lunch ann pizza
VOTE lunch ann pizza
VOTE lunch cy salad
VOTE dinner ann pizza
RESULT lunch
CLOSE lunch
VOTE lunch dee tacos
CLOSE lunch
RESULT lunch
CREATE lunch a b
CREATE x only
CREATE y a a
RESULT nope
vote lunch ann pizza
```
stdout:
```
OK
VOTED
VOTED
CHANGED
UNCHANGED
ERR no such option
ERR no such poll
lunch open pizza=2 sushi=0 tacos=0
OK
ERR poll closed
ERR poll closed
lunch closed pizza=2 sushi=0 tacos=0
ERR poll exists
ERR bad command
ERR bad command
ERR no such poll
ERR bad command
```
exit: `0`

Afterwards `data/polls.log` contains exactly:
```
CREATE lunch pizza sushi tacos
VOTE lunch ann sushi
VOTE lunch bob pizza
VOTE lunch ann pizza
CLOSE lunch
```

### Example 2: killed, then restarted

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `polls d`, killed right after its 3rd output line. Input is
sent one line at a time, so `VOTE p cy no` is never sent.

stdin:
```
CREATE p yes no
VOTE p ann yes
VOTE p bob no
VOTE p cy no
```
stdout before the kill:
```
OK
VOTED
VOTED
```

**Step 2**: cmd `polls d`.

stdin:
```
RESULT p
VOTE p bob yes
RESULT p
```
stdout:
```
p open yes=1 no=1
CHANGED
p open yes=2 no=0
```
exit: `0`

### Example 3: a torn last record

This is a multi-run test with two steps. The working directory starts with
`d/polls.log` containing exactly the bytes `CREATE a x y\nVOTE a bob x` (no
final newline).

**Step 1**: cmd `polls d`.

stdin:
```
RESULT a
VOTE a ann y
```
stdout:
```
a open x=0 y=0
VOTED
```
exit: `0`

**Step 2**: cmd `polls d`.

stdin:
```
RESULT a
```
stdout:
```
a open x=0 y=1
```
exit: `0`

(The torn `VOTE a bob x` was discarded and cut off, so the new record
starts on its own line.)

### Example 4: errors

- The working directory starts with `d/polls.log` containing exactly the
  bytes `CREATE a x y\nVOTE a bob z\n` (no option `z`). cmd: `polls d` with
  stdin `RESULT a\n` gives stdout (empty) and exit `1`.
- The working directory starts with `d/polls.log` containing exactly the
  bytes `CREATE a x y\nVOTE a bob x\nVOTE a bob x\n` (the third record
  would be `UNCHANGED`). cmd: `polls d` with stdin `RESULT a\n` gives stdout
  (empty) and exit `1`.
- The working directory contains a regular file `f`. cmd: `polls f` gives
  stdout (empty) and exit `1`.
- cmd: `polls` gives stdout (empty) and exit `2`.
- cmd: `polls a b` gives stdout (empty) and exit `2`.

## Not required

- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the process
  is required. `fsync` is optional.
- Compacting the journal.
- Concurrent processes on the same `DIR`.
- Reopening polls or withdrawing votes.
- Any particular stderr wording.
