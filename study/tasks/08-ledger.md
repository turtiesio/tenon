# Task 08: ledger (bank ledger with a write-ahead log and exactly-once requests)

## Goal

Write a small bank-ledger service driven by a line protocol on stdin and
stdout. All state lives in a **write-ahead log** file inside a data directory
named on the command line.

- Every successful mutating command carries a client request id, and it is
  appended to the log **before** it is acknowledged.
- A rerun replays the log. A retried request id is answered `DUP` instead of
  being applied twice.
- The process may be killed at any moment. A torn (incomplete) final log
  record must be discarded on recovery.

Together these give the guarantee: **after any crash, a rerun reflects every
acknowledged operation exactly once.**

## Interface

```
ledger DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr and exit `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created (for example, the parent is missing), or `DIR`
    exists but is not a directory, print a message to stderr and exit `1`.
  - The state file is `DIR/ledger.log` (format below). The program must not
    store state anywhere else.
- **stdin.** One command per line. A line ends with `\n` (a trailing `\r` is
  removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.**
  - `0`: EOF reached normally.
  - `1`: `DIR` unusable.
  - `2`: usage error.
  - `3`: corrupt log (see Recovery). Nothing is written to stdout and stdin is
    not read.

## Commands

Tokens are separated by one or more spaces. Leading and trailing spaces are
ignored.

- `<rid>` (request id) matches `[A-Za-z0-9_-]{1,32}`.
- `<acct>` (account) matches `[a-z][a-z0-9_]{0,15}`.
- `<amt>` (amount) matches `[1-9][0-9]{0,11}` (1 to 999999999999).

Mutating commands:

| Command | Success response |
|---|---|
| `<rid> OPEN <acct>` | `OK <rid>`. Creates the account with balance 0. |
| `<rid> DEPOSIT <acct> <amt>` | `OK <rid> <new balance>` |
| `<rid> WITHDRAW <acct> <amt>` | `OK <rid> <new balance>` |
| `<rid> TRANSFER <from> <to> <amt>` | `OK <rid>` |

Read-only commands:

| Command | Response |
|---|---|
| `BALANCE <acct>` | `<acct> <balance>`, or `ERR no such account` |
| `ACCOUNTS` | `<acct>=<balance>` for every account in ascending byte order, separated by single spaces, or `-` if there are no accounts |

## Rules

1. **Parsing.**
   - A line whose tokens are exactly `BALANCE <acct>` or exactly `ACCOUNTS` is
     a read-only command.
   - Otherwise the line is a mutating command: the first token is the rid, the
     second is one of `OPEN`, `DEPOSIT`, `WITHDRAW` or `TRANSFER`, and the
     argument count and syntax must match the table.
   - Anything else, including an empty line, gets `ERR bad command`.
2. **Exactly-once.** After a mutating command parses, check its rid first. If
   the rid belongs to a mutating command that **succeeded** earlier, whether
   in this run or in any earlier run (that is, it is in the log), respond
   `DUP <rid>` and do nothing else. The rest of the command is not compared.
   Failed commands are not recorded, so their rid may be used again.
3. **Semantic errors.** These are checked in this order, and the response is
   `ERR <rid> <reason>`. Nothing is changed or logged.
   - `OPEN`: `exists` if the account already exists.
   - `DEPOSIT`: `no such account`, then `limit` if the new balance would
     exceed 10^15.
   - `WITHDRAW`: `no such account`, then `insufficient` if amt > balance.
   - `TRANSFER`:
     - `same account` if from = to;
     - `no such account` if either account is missing;
     - `insufficient` if amt > the balance of from;
     - `limit` if the balance of to would exceed 10^15.
4. **Durability (write-ahead).** For each successful mutating command:
   1. Append its log record (below) to `ledger.log` in a single write that
      ends with `\n`.
   2. Flush it to the operating system. `fsync` is allowed but not required.
   3. Only then update memory and print the `OK` response.

   Balances never go negative, never exceed 10^15, and fit in 53 bits.

## Log format and recovery

- `ledger.log` is UTF-8 text with one record per line. A record is the
  mutating command in canonical form: its tokens joined by single spaces, then
  `\n`. For example: `r4 TRANSFER alice bob 30`. A missing or empty file means
  empty state.
- **Startup.** Read the whole log before reading any stdin.
- **Torn tail.** If the file is non-empty and does not end with `\n`, the bytes
  after the last `\n` (or the whole file, if it has no `\n`) are a torn record.
  Discard them, even if they look like a complete command, and **truncate the
  file** so that it ends right after the last `\n`. Later appends then start on
  a fresh line.
- **Corruption.** Every complete line (ending in `\n`) must parse as a
  mutating command under rule 1, where one or more spaces may separate tokens.
  If any complete line does not parse, the log is corrupt: print
  `ledger: corrupt log at line <n>` to stderr and exit `3` without printing to
  stdout.
- **Replay.** Apply the records in order, without re-checking the semantic
  rules (tests only provide semantically valid logs). Every replayed rid
  counts as seen for rule 2.
- The program must not rewrite, compact or reorder `ledger.log`. The only
  changes it may make are appending records and truncating a torn tail.

## Examples

Each line shown ends with `\n` unless stated otherwise. In every example the
working directory starts empty, except where noted.

### Example 1: a single run

cmd: `ledger data`

stdin:
```
r1 OPEN alice
r2 OPEN bob
r3 DEPOSIT alice 100
r4 TRANSFER alice bob 30
r5 WITHDRAW bob 50
r3 DEPOSIT alice 100
BALANCE alice
ACCOUNTS
```
stdout:
```
OK r1
OK r2
OK r3 100
OK r4
ERR r5 insufficient
DUP r3
alice 70
alice=70 bob=30
```
exit: `0`

Afterwards `data/ledger.log` contains exactly:
```
r1 OPEN alice
r2 OPEN bob
r3 DEPOSIT alice 100
r4 TRANSFER alice bob 30
```

### Example 2: killed, then the client retries everything

This is a multi-run test with three steps in one working directory.

**Step 1**: cmd `ledger data`. The process is killed right after its 2nd
output line. Input is sent one line at a time, so `t3` is never sent.

stdin:
```
t1 OPEN carol
t2 DEPOSIT carol 500
t3 WITHDRAW carol 200
```
stdout before the kill:
```
OK t1
OK t2 500
```

**Step 2**: cmd `ledger data`, with the same stdin as step 1.

stdout:
```
DUP t1
DUP t2
OK t3 300
```
exit: `0`

**Step 3**: cmd `ledger data`.

stdin:
```
BALANCE carol
```
stdout:
```
carol 300
```
exit: `0`

### Example 3: a torn tail is discarded

Working directory contains `data/ledger.log`, whose last line has **no**
trailing newline:
```
a1 OPEN dave
a2 DEPOSIT dave 70
a3 DEPOSIT dave 5
```
cmd: `ledger data`

stdin:
```
BALANCE dave
a3 DEPOSIT dave 5
BALANCE dave
```
stdout:
```
dave 70
OK a3 75
dave 75
```
exit: `0`

(Afterwards the log holds the three records, each ending with `\n`.)

### Example 4: corrupt log

Working directory contains `data/ledger.log`:
```
a1 OPEN dave
this is junk
a2 OPEN erin
```
cmd: `ledger data`

stdin:
```
ACCOUNTS
```
stdout: (empty)

exit: `3`

### Example 5: usage and semantic errors

- cmd: `ledger` gives stdout (empty) and exit `2`.
- cmd: `ledger d`, with this stdin:

  ```
  x1 OPEN Bob
  x1 OPEN bob
  x2 OPEN bob
  x3 TRANSFER bob bob 1
  x4 DEPOSIT zed 5
  x5 DEPOSIT bob 999999999999
  BALANCE zed
  ACCOUNTS
  ```

  gives this stdout and exit `0`:

  ```
  ERR bad command
  OK x1
  ERR x2 exists
  ERR x3 same account
  ERR x4 no such account
  OK x5 999999999999
  ERR no such account
  bob=999999999999
  ```

## Not required

- Concurrent access by several processes to the same `DIR`.
- Detecting semantically invalid but well-formed log records, such as an
  overdraft or a duplicate rid.
- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the process
  is required.
- Log compaction or snapshots (they are not allowed; see above).
- Any particular stderr wording.
