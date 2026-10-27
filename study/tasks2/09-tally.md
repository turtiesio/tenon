# Task 09: tally (persistent counters with a write-ahead log)

## Goal

Write a persistent store of named integer counters, driven by a line protocol
on stdin and stdout. Every change is appended to a log file **before** it is
acknowledged, so the state survives the process being killed at any moment.
On startup the program replays the log. It must cope with a log whose last
record was only partly written (a torn write), and it can compact the log
into a minimal snapshot using an atomic rename.

## Interface

```
tally DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr and exit `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created, or `DIR` exists but is not a directory, print a
    message to stderr and exit `1`.
- **stdin.** One command per line. Lines are split on `\n`. The last line may
  lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `1` if `DIR` is unusable, `2` for a
  usage error.

## Commands

Tokens are separated by exactly one space, with no leading or trailing
spaces. Command names are uppercase.

- `<name>` matches `[a-z][a-z0-9_]{0,31}`.
- `<int>` matches `-?[0-9]{1,15}` (leading zeros allowed, `-0` is 0).

| Command | Response |
|---|---|
| `SET <name> <int>` | `OK`. The counter is set to the value (created if missing). |
| `ADD <name> <int>` | The new value as a decimal integer. A missing counter counts as 0 and is created. |
| `GET <name>` | The value, or `NONE` if the counter does not exist. |
| `DEL <name>` | `OK` if the counter existed (it is deleted), otherwise `NONE`. |
| `LIST` | `<n>` followed by ` <name>=<value>` for every counter, sorted by name ascending (byte-wise), all on one line. With no counters, just `0`. |
| `INFO` | `counters=<n> log_records=<r>` (see rule 5). |
| `COMPACT` | `OK <r>`: rewrites the log (rule 6), where `r` is the number of records in the new log. |

Any other line (wrong token count, bad name or number, lowercase command,
empty line) gets `ERR bad command` and changes nothing. Values are printed
without leading zeros, with `-` for negatives, and `0` for zero.

## The log file

The state lives in `DIR/tally.log`. Its format is fixed, because tests may
create it. Every record is one line terminated by `\n`, in one of these exact
forms (single spaces, `<name>` and `<int>` as above):

```
S <name> <int>
A <name> <int>
D <name>
```

- `S` sets a counter, `A` adds to a counter (a missing counter counts as 0 and
  is created), and `D` deletes a counter (a no-op if it does not exist).
- A missing `tally.log` means an empty state and zero records.

## Rules

1. **Logging.** Before printing the response to a command that changes state,
   append exactly one record to `tally.log` and make sure it has been written
   to the file (not just kept in a user-space buffer):
   - `SET` appends `S <name> <value>`;
   - `ADD` appends `A <name> <int>` (the delta, as given or normalised);
   - `DEL` of an existing counter appends `D <name>`.

   `GET`, `LIST`, `INFO`, `DEL` of a missing counter and errors append nothing.
2. **Recovery.** At startup, read `tally.log` from the beginning and find its
   **valid prefix**: the longest run of leading lines that are each complete
   (terminated by `\n`) and exactly match one of the three record forms.
   Replay those records in order. The first line that is incomplete or does
   not match, and **everything after it**, is discarded. Before appending any
   new record, the file must be truncated (or rewritten) so that it holds only
   the valid prefix.
3. **Temporary file.** At startup, before reading the log, delete
   `DIR/tally.log.tmp` if it exists. It may be left over from a crash and may
   contain anything. It never affects the state.
4. **Guarantee.** If the process is killed at any point after printing a
   response, a later run sees exactly the state after the commands that were
   answered.
5. **`log_records`** is the number of records currently in `tally.log`: the
   valid prefix found at startup, plus the records appended since, or the
   count written by the last `COMPACT`.
6. **COMPACT** writes one `S <name> <value>` record per existing counter,
   sorted by name, to `DIR/tally.log.tmp`, flushes or closes it, then renames
   it to `DIR/tally.log`, replacing the old log. With no counters, the new log
   is empty and the response is `OK 0`. The counter values do not change.
7. **Limits.** At most 10000 commands per run, and at most 100000 records in
   a log written by tests. All values stay within ±10^17.

## Examples

Each line shown ends with `\n`, unless stated otherwise. In every example the
working directory starts empty, except where noted.

### Example 1: a single run

cmd: `tally data`

stdin:
```
SET apples 5
ADD apples 3
ADD pears -2
GET apples
GET plums
DEL pears
DEL pears
LIST
INFO
COMPACT
INFO
```
stdout:
```
OK
8
-2
8
NONE
OK
NONE
1 apples=8
counters=1 log_records=4
OK 1
counters=1 log_records=1
```
exit: `0`

### Example 2: killed, then restarted

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `tally d`, killed right after its 3rd output line. Input is
sent one line at a time, so `SET a 0` is never sent.

stdin:
```
SET a 1
ADD a 10
ADD b 7
SET a 0
```
stdout before the kill:
```
OK
11
7
```

**Step 2**: cmd `tally d`.

stdin:
```
LIST
INFO
```
stdout:
```
2 a=11 b=7
counters=2 log_records=3
```
exit: `0`

### Example 3: a torn final record

This is a multi-run test with two steps. The working directory starts with
`d/tally.log` containing exactly these 17 bytes, where `\n` stands for a
newline byte and the last record has no final newline:

```
S x 5\nA x 2\nA x 9
```

**Step 1**: cmd `tally d`.

stdin:
```
GET x
INFO
ADD x 1
```
stdout:
```
7
counters=1 log_records=2
8
```
exit: `0`

**Step 2**: cmd `tally d`.

stdin:
```
GET x
INFO
```
stdout:
```
8
counters=1 log_records=3
```
exit: `0`

(The torn `A x 9` is discarded. If it were left in the file, the appended
`A x 1` would be glued to it and lost on the next start.)

### Example 4: a bad record in the middle, and a leftover temporary file

This is a multi-run test with two steps. The working directory starts with
`d/tally.log`:

```
S a 1
S b 2
X junk
S c 3
```
and `d/tally.log.tmp` containing `S zzz 999\n`.

**Step 1**: cmd `tally d`.

stdin:
```
LIST
INFO
ADD c 1
```
stdout:
```
2 a=1 b=2
counters=2 log_records=2
1
```
exit: `0`

**Step 2**: cmd `tally d`.

stdin:
```
LIST
GET zzz
set a 1
```
stdout:
```
3 a=1 b=2 c=1
NONE
ERR bad command
```
exit: `0`

### Example 5: usage and directory errors

- cmd: `tally` gives stdout (empty) and exit `2`.
- cmd: `tally a b` gives stdout (empty) and exit `2`.
- The working directory contains a regular file `f`. cmd: `tally f` gives
  stdout (empty) and exit `1`.

## Not required

- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the process
  is required. `fsync` is optional.
- Concurrent processes on the same `DIR`.
- Logs larger than the stated limits.
- Any particular stderr wording.
