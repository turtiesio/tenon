# Task 09: bookmarks (persistent tagged bookmarks with a journal and snapshots)

## Goal

Write a persistent bookmark store driven by a line protocol on stdin and
stdout. Bookmarks have a unique name, a URL and a set of tags. Every change
is appended to a numbered journal in a data directory **before** it is
acknowledged. A `COMPACT` command writes the whole state to a snapshot file
(through a temporary file and an atomic rename) and then empties the
journal. On startup the program loads the snapshot, replays the journal
records the snapshot does not already contain, discards a torn last journal
line left by a crash, and ignores a leftover temporary file.

## Interface

```
bookmarks DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr, print nothing on stdout, and
  exit `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created, or `DIR` exists but is not a directory, print a
    message to stderr, print nothing on stdout, and exit `1`.
- **Startup.** Load the state as described in "Files". If the snapshot or
  the journal is not valid, print a message to stderr, print **nothing** on
  stdout, leave all files unchanged, and exit `1` without reading stdin.
- **stdin.** One command per line, ASCII. Lines are split on `\n`. If the
  input ends with `\n`, there is no extra empty line after it. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `1` if `DIR`, the snapshot or the
  journal is unusable, `2` for a usage error.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces. `<name>` matches `[a-z0-9-]{1,20}`,
`<url>` is 1 to 200 characters from `!` (`0x21`) to `~` (`0x7E`) (no
spaces), and `<tag>` matches `[a-z0-9]{1,12}`.

| Command | Response |
|---|---|
| `ADD <name> <url>` | `OK`: a new bookmark without tags. `ERR exists` if a bookmark with this name exists. |
| `DEL <name>` | `OK`: the bookmark and its tags are removed. |
| `TAG <name> <tag>` | `OK` if the tag was added, `UNCHANGED` if the bookmark already had it. |
| `UNTAG <name> <tag>` | `OK` if the tag was removed, `UNCHANGED` if the bookmark did not have it. |
| `GET <name>` | `<name> <url> <tags>`, where `<tags>` is the bookmark's tags sorted in byte order and joined with `,`, or `-` if it has none. |
| `FIND <tag>` | The names of all bookmarks with this tag, sorted in byte order, joined with single spaces, or `-` if there are none. |
| `COMPACT` | Writes a snapshot (see "Files"): `OK <seq>`, where `<seq>` is the snapshot's sequence number. |

`DEL`, `TAG`, `UNTAG` and `GET` on a name that has no bookmark get
`ERR no such bookmark`. A line that is not exactly one of the forms above
(unknown or lower-case command, wrong token count, malformed name, URL or
tag, extra spaces, an empty line) gets `ERR bad command`; this is checked
first. A command that gets an `ERR` or `UNCHANGED` response changes
nothing.

## Files

All files are in `DIR`. Their formats are fixed, because tests may create
them. All lines end with `\n`.

1. **Journal records.** `DIR/journal` holds one record per line:
   `<seq> <command>`, where `<command>` is the command line as received
   (after `\r` removal) and `<seq>` is a decimal number without leading
   zeros. Every `ADD`, `DEL`, `TAG` or `UNTAG` answered `OK` is a record.
   Nothing else is recorded.
2. **Sequence numbers.** Records are numbered 1, 2, 3, ... over the whole
   life of the data directory; the numbering continues across runs and
   across compactions. The *last sequence number* L is the number of the
   latest record ever written (0 if none).
3. **Write before answering.** Append the record to the journal and make
   sure it is written to the file (flush it) **before** printing the
   response.
4. **Snapshot.** `DIR/snapshot` has a first line `bookmarks <S>`, where S
   is a decimal number without leading zeros (`0` allowed), followed by
   one line per bookmark, sorted by name in byte order:
   `<name> <url> <tags>`, with `<tags>` written as in `GET`. It holds the
   state after all records with sequence numbers up to S.
5. **COMPACT** does, in this order: write the snapshot with S = L to
   `DIR/snapshot.tmp`; flush and close it; rename it to `DIR/snapshot`
   (replacing any old snapshot); empty the journal (truncate it to 0 bytes,
   or delete it); respond `OK <L>`. `COMPACT` is not a record and does not
   change L.
6. **Loading.**
   1. A file `DIR/snapshot.tmp` is a leftover of an interrupted `COMPACT`.
      Ignore its contents completely. It may be deleted (also when
      startup fails).
   2. If `DIR/snapshot` exists, it must be valid: the first line as in item
      4, then lines of the form `<name> <url> <tags>` with names valid and
      strictly increasing in byte order, and `<tags>` either `-` or one or
      more valid tags strictly increasing in byte order joined with `,`;
      the file ends with `\n`. Load it and let S be its number. If there is
      no snapshot, the state is empty and S = 0.
   3. A missing journal is the same as an empty one. If the journal does
      not end with `\n`, the bytes after the last `\n` (or the whole file,
      if it has no `\n`) are a **torn** record from a crash: ignore them
      and **truncate** the file so that it ends right after the last `\n`
      (or is empty) before writing anything new.
   4. Every complete journal line must be `<seq> <command>` with a valid
      `ADD`, `DEL`, `TAG` or `UNTAG` command. The sequence numbers must be
      consecutive (each is the previous plus 1). If there is at least one
      record, the first number must be at most S + 1 and the last at least
      S, so that the records continue the snapshot without a gap.
   5. Records with a number up to S are already in the snapshot: skip
      them. Apply the others in order; each must get the response `OK`.
   6. Any violation of items 2, 4 or 5 makes the data **not valid**
      (startup fails as described above).
   7. L is the larger of S and the last record number (S if there are no
      records). The next record gets L + 1.
7. **Guarantee.** If the process is killed at any moment after printing a
   response, a later run sees exactly the state after all the commands that
   were answered.
8. **Limits.** At most 10000 commands per run, 100000 journal records and
   1000 bookmarks.

## Examples

Each line shown ends with `\n`. In every example the working directory
starts empty, except where noted.

### Example 1: a single run with a compaction

cmd: `bookmarks data`

stdin:
```
ADD tenon https://example.org/tenon
ADD py https://python.org
TAG py lang
TAG tenon lang
TAG tenon new
TAG tenon new
UNTAG py zz
GET tenon
FIND lang
FIND zz
ADD py https://x
DEL nope
COMPACT
DEL py
GET py
add x y
```
stdout:
```
OK
OK
OK
OK
OK
UNCHANGED
UNCHANGED
tenon https://example.org/tenon lang,new
py tenon
-
ERR exists
ERR no such bookmark
OK 5
OK
ERR no such bookmark
ERR bad command
```
exit: `0`

Afterwards `data/snapshot` contains exactly:
```
bookmarks 5
py https://python.org lang
tenon https://example.org/tenon lang,new
```
and `data/journal` contains exactly:
```
6 DEL py
```

### Example 2: killed, then restarted

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `bookmarks d`, killed right after its 4th output line.
Input is sent one line at a time, so `TAG b x` is never sent.

stdin:
```
ADD a http://a
COMPACT
ADD b http://b
TAG a x
TAG b x
```
stdout before the kill:
```
OK
OK 1
OK
OK
```

**Step 2**: cmd `bookmarks d`.

stdin:
```
FIND x
GET b
COMPACT
```
stdout:
```
a
b http://b -
OK 3
```
exit: `0`

### Example 3: snapshot and journal overlap, a torn record, a stale temporary file

This is a multi-run test with two steps. The working directory starts with
these files:

- `d/snapshot`, exactly:
  ```
  bookmarks 3
  a http://a x
  b http://b -
  ```
- `d/journal` (left behind by a `COMPACT` that was killed after the rename
  but before emptying the journal, and then by a crash in the middle of a
  write), exactly the bytes
  `2 ADD b http://b\n3 TAG a x\n4 TAG b y\n5 DEL a\n6 ADD c ht`
  (no final newline).
- `d/snapshot.tmp`, exactly `bookmarks 9\nz http://z -\n`.

**Step 1**: cmd `bookmarks d`.

stdin:
```
FIND x
FIND y
GET z
ADD c http://c
COMPACT
```
stdout:
```
-
b
ERR no such bookmark
OK
OK 6
```
exit: `0`

(Records 2 and 3 are already in the snapshot; 4 and 5 are applied; the torn
`6 ADD c ht` is discarded, so the new `ADD c` gets number 6.)

**Step 2**: cmd `bookmarks d`.

stdin:
```
GET b
GET c
```
stdout:
```
b http://b y
c http://c -
```
exit: `0`

### Example 4: errors

- The working directory starts with `d/journal` containing exactly
  `1 ADD a http://a\n3 TAG a x\n` (a gap). cmd: `bookmarks d` with stdin
  `GET a\n` gives stdout (empty) and exit `1`.
- The working directory starts with `d/journal` containing exactly
  `1 ADD a http://a\n2 ADD a http://b\n` (the second record would be
  `ERR exists`). cmd: `bookmarks d` with stdin `GET a\n` gives stdout
  (empty) and exit `1`.
- The working directory starts with `d/snapshot` containing exactly
  `bookmarks 2\nb http://b -\na http://a -\n` (not sorted). cmd:
  `bookmarks d` with stdin `GET a\n` gives stdout (empty) and exit `1`.
- The working directory starts with `d/snapshot` containing exactly
  `bookmarks 5\n` and `d/journal` containing exactly `1 ADD a http://a\n`
  (records 2 to 5 are missing). cmd: `bookmarks d` with stdin `GET a\n`
  gives stdout (empty) and exit `1`.
- The working directory contains a regular file `f`. cmd: `bookmarks f`
  gives stdout (empty) and exit `1`.
- cmd: `bookmarks` gives stdout (empty) and exit `2`.

## Not required

- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the
  process is required. `fsync` is optional.
- Concurrent processes on the same `DIR`.
- Renaming bookmarks or changing a URL.
- Any particular stderr wording.
