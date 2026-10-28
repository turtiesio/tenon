# Task 09: shorten (persistent URL shortener with a numbered journal)

## Goal

Write a persistent URL shortener driven by a line protocol on stdin and
stdout. Each stored URL gets a short code (its id in base 36), lookups count
hits, and links can be deleted. Every change is appended to a journal file
as a **numbered** record **before** it is acknowledged, so the state
survives the process being killed at any moment. On startup the program
replays the journal and keeps only its longest valid prefix: a record that
is torn, malformed, out of sequence or inconsistent ends the journal.

## Interface

```
shorten DIR
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

## Links and codes

A link has an **id**, a **URL** and a **hit count**. Ids are assigned from a
counter that starts at 1 and increases by 1 for every link ever created, so
an id is never reused, not even after the link is deleted or the program
restarts. A link's **code** is its id written in base 36 with the digits
`0`-`9` and `a`-`z`, lower case, without leading zeros: id 1 is `1`, id 10
is `a`, id 35 is `z`, id 36 is `10`, id 1296 is `100`.

## Commands

Tokens are separated by exactly one space, with no leading or trailing
spaces. Command names are uppercase.

- `<url>` matches `[!-~]{1,200}`: 1 to 200 printable ASCII characters
  without spaces.
- `<code>` matches `[0-9a-z]{1,8}`.

| Command | Response |
|---|---|
| `PUT <url>` | `CODE <code>`: creates a new link with the next id and hit count 0. The same URL may be stored any number of times; each `PUT` creates a new link. |
| `GET <code>` | `URL <url>`, and the link's hit count increases by 1. `ERR not found` if no existing link has this code. |
| `HITS <code>` | `HITS <n>`: the hit count. `ERR not found` if no existing link has this code. |
| `DEL <code>` | `OK`: deletes the link. `ERR not found` if no existing link has this code. |
| `INFO` | `links=<n> next=<code> records=<r>`: the number of existing links, the code that the next `PUT` will get, and the number of records in the journal (rule 5). |

Any other line (unknown or lower-case command, wrong token count, a bad
token, an empty line) gets `ERR bad command` and changes nothing. A code
that is syntactically valid but has leading zeros (such as `01`) or belongs
to no existing link simply gets `ERR not found`.

## The journal

The state lives in `DIR/journal`. Its format is fixed, because tests may
create it. Every record is one line terminated by `\n`, in one of these
exact forms (single spaces):

```
<seq> P <url>
<seq> H <code>
<seq> D <code>
```

- `<seq>` matches `[1-9][0-9]{0,8}` and must equal the record's position in
  the file: the first record has `<seq>` 1, the second 2, and so on.
- `P` creates a link with the next id and the given URL; `H` adds one hit to
  the link with that code; `D` deletes it.
- A missing `journal` means an empty state: no links, next id 1, 0 records.

## Rules

1. **Journaling.** Before printing the response to a command that changes
   the state, append exactly one record to `journal` and make sure it has
   been written to the file (not just kept in a user-space buffer):
   - a `PUT` appends `<seq> P <url>`;
   - a successful `GET` appends `<seq> H <code>`;
   - a successful `DEL` appends `<seq> D <code>`;

   where `<seq>` is the number of records in the journal before the append,
   plus 1. `HITS`, `INFO` and every error response append nothing.
2. **Recovery.** At startup, read `journal` from the beginning and find its
   **valid prefix**: the longest run of leading lines that are each
   - complete (terminated by `\n`),
   - exactly one of the three record forms,
   - numbered with the correct `<seq>`, and
   - consistent: an `H` or `D` record must name a link that exists at that
     point of the replay (created by an earlier `P` and not deleted).

   Replay the valid prefix in order. The first line that breaks any of these
   rules, and **everything after it**, is discarded. Before appending any new
   record, the file must be truncated (or rewritten) so that it holds only
   the valid prefix.
3. **Ids after recovery.** The next id is 1 plus the number of `P` records in
   the valid prefix.
4. **Guarantee.** If the process is killed at any point after printing a
   response, a later run sees exactly the state after the commands that were
   answered.
5. **`records`** is the number of records currently in `journal`: the valid
   prefix found at startup plus the records appended since.
6. **Limits.** At most 10000 commands per run, and at most 100000 records in
   a journal written by tests.

## Examples

Each line shown ends with `\n`, unless stated otherwise. In every example
the working directory starts empty, except where noted.

### Example 1: a single run

cmd: `shorten data`

stdin:
```
PUT https://example.com/a
PUT http://x.org/?q=1&r=2
GET 1
GET 1
GET 2
HITS 1
HITS 3
DEL 2
GET 2
DEL 2
PUT https://example.com/a
INFO
```
stdout:
```
CODE 1
CODE 2
URL https://example.com/a
URL https://example.com/a
URL http://x.org/?q=1&r=2
HITS 2
ERR not found
OK
ERR not found
ERR not found
CODE 3
links=2 next=4 records=7
```
exit: `0`

Afterwards `data/journal` contains:
```
1 P https://example.com/a
2 P http://x.org/?q=1&r=2
3 H 1
4 H 1
5 H 2
6 D 2
7 P https://example.com/a
```

### Example 2: killed, then restarted

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `shorten d`, killed right after its 3rd output line. Input
is sent one line at a time, so `DEL 1` is never sent.

stdin:
```
PUT u1
PUT u2
GET 2
DEL 1
```
stdout before the kill:
```
CODE 1
CODE 2
URL u2
```

**Step 2**: cmd `shorten d`.

stdin:
```
INFO
HITS 2
GET 1
PUT u4
```
stdout:
```
links=2 next=3 records=3
HITS 1
URL u1
CODE 3
```
exit: `0`

### Example 3: a torn final record

This is a multi-run test with two steps. The working directory starts with
`d/journal` containing these lines, where the last one, `5 D 2`, has **no**
final newline:

```
1 P a.com
2 H 1
3 P b.com
4 H 1
5 D 2
```

**Step 1**: cmd `shorten d`.

stdin:
```
INFO
HITS 1
GET 2
INFO
```
stdout:
```
links=2 next=3 records=4
HITS 2
URL b.com
links=2 next=3 records=5
```
exit: `0`

**Step 2**: cmd `shorten d`.

stdin:
```
INFO
GET 2
```
stdout:
```
links=2 next=3 records=5
URL b.com
```
exit: `0`

(The torn `5 D 2` is discarded, so link 2 still exists, and the `GET 2` of
step 1 is written as record 5.)

### Example 4: a sequence gap and an inconsistent record

- The working directory starts with `d/journal`:
  ```
  1 P a.com
  2 H 1
  4 P b.com
  5 H 1
  ```
  cmd: `shorten d` with stdin `INFO\nPUT c.com\n` gives stdout
  `links=1 next=2 records=2\nCODE 2\n` and exit `0`. Afterwards
  `d/journal` contains `1 P a.com\n2 H 1\n3 P c.com\n`.
- The working directory starts with `d/journal`:
  ```
  1 P a.com
  2 D 1
  3 H 1
  4 P b.com
  ```
  cmd: `shorten d` with stdin `INFO\nGET 1\nGET 2\n` gives stdout
  `links=0 next=2 records=2\nERR not found\nERR not found\n` and exit `0`
  (record 3 hits a deleted link, so it and record 4 are discarded).

### Example 5: errors

- cmd: `shorten` gives stdout (empty) and exit `2`.
- cmd: `shorten a b` gives stdout (empty) and exit `2`.
- The working directory contains a regular file `f`. cmd: `shorten f` gives
  stdout (empty) and exit `1`.
- cmd: `shorten e` with stdin
  `PUT\nPUT a b\nput x\nGET A1\nGET 123456789\n\nINFO \nGET 0\n` gives
  stdout `ERR bad command\n` seven times, then `ERR not found\n`, and exit
  `0`.

## Not required

- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the process
  is required. `fsync` is optional.
- Concurrent processes on the same `DIR`.
- Compaction of the journal.
- Validating URLs beyond the character rule.
- Any particular stderr wording.
