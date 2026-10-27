# Task 06: kvtx (in-memory key-value store with nested transactions)

## Goal

Write an in-memory key-value service driven by a line protocol on stdin and
stdout. Each input line is one command, and each command produces exactly one
response line. It supports string values, integer increments with overflow
checks, value counting, key listing, and **nested transactions** with
`BEGIN`, `COMMIT` and `ROLLBACK`. Every read sees the effects of all open
transactions.

## Interface

```
kvtx
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. A line ends with `\n` (a trailing `\r` is
  removed), and the last line may lack `\n`. Input ends at EOF.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.** Tests may wait for each
  response before sending the next command.
- **Exit code.** `0` at EOF. Any transactions still open at EOF are discarded
  silently.

## Commands

Tokens are separated by one or more spaces. Leading and trailing spaces are
ignored. Command names are case-sensitive and uppercase. Keys and values are
non-empty strings of printable non-space ASCII (bytes 0x21-0x7E).

| Command | Response |
|---|---|
| `SET <key> <value>` | `OK` |
| `GET <key>` | the value, or `NULL` if the key is absent |
| `DEL <key>` | `1` if the key existed (and is now removed), `0` otherwise |
| `INCR <key>` / `INCR <key> <delta>` | the new value (see Integers). The delta defaults to `1`. |
| `COUNT <value>` | the number of keys whose current value equals `<value>` exactly |
| `KEYS` | all present keys in ascending byte order, separated by single spaces, or `(empty)` if there are none |
| `BEGIN` | `OK`. Opens a new transaction nested inside the current one (if any). |
| `ROLLBACK` | `OK`. Discards every change made in the innermost open transaction and closes it. `ERR no transaction` if none is open. |
| `COMMIT` | `OK`. Closes the innermost transaction and merges its changes into the enclosing transaction, or into the permanent store if it was the outermost. `ERR no transaction` if none is open. |

## Rules

1. **Malformed commands.** Any line that is not exactly one of the forms above
   gets the response `ERR bad command` and changes nothing. That includes an
   unknown or lowercase command name, the wrong number of tokens, and an empty
   or all-space line.
2. **Transaction visibility.** `GET`, `COUNT`, `KEYS`, `INCR` and `DEL` all
   operate on the **current view**: the permanent store with all open
   transactions applied in order, from outermost to innermost. A `DEL` inside a
   transaction hides the key until that transaction is rolled back. Rolling
   back an inner transaction restores exactly the view that existed when it
   began.
3. **Integers.** A string is an *integer* if it matches `-?(0|[1-9][0-9]*)`
   and its absolute value is ≤ 10^15. (`-0`, `+5`, `007` and
   `9999999999999999` are not integers.)
   - In `INCR`, an absent key counts as `0`.
   - If the current value or `<delta>` is not an integer, respond
     `ERR not an integer` and change nothing.
   - If the result's absolute value would exceed 10^15, respond `ERR overflow`
     and change nothing.
   - Otherwise store the result in canonical decimal form (no leading zeros,
     no `+`) and respond with it.
4. **Responses are exact strings.** The only error responses are
   `ERR bad command`, `ERR not an integer`, `ERR overflow` and
   `ERR no transaction`.
5. **Limits.** At most 100000 commands, at most 10000 distinct keys, and a
   nesting depth of at most 100. Every token is at most 100 bytes.

## Examples

Each line shown ends with `\n`. For every example, cmd is `kvtx` and exit is
`0`, except where noted.

### Example 1: basics

stdin:
```
SET a 10
GET a
INCR a 5
GET b
DEL a
DEL a
KEYS
```
stdout:
```
OK
10
15
NULL
1
0
(empty)
```

### Example 2: nested transactions

stdin:
```
SET x 1
BEGIN
SET x 2
BEGIN
DEL x
GET x
ROLLBACK
GET x
COMMIT
GET x
ROLLBACK
```
stdout:
```
OK
OK
OK
OK
1
NULL
OK
2
OK
2
ERR no transaction
```

### Example 3: COUNT and KEYS see the transaction view

stdin:
```
SET a red
SET b red
BEGIN
SET c red
SET a blue
COUNT red
KEYS
ROLLBACK
COUNT red
COUNT green
KEYS
```
stdout:
```
OK
OK
OK
OK
OK
2
a b c
OK
2
0
a b
```

### Example 4: integer errors and malformed commands

stdin:
```
INCR k
SET s abc
INCR s
INCR k 999999999999999
INCR k 1
GET k
INCR k -2000000000000000
set k 1
SET k
```
stdout:
```
1
OK
ERR not an integer
1000000000000000
ERR overflow
1000000000000000
ERR not an integer
ERR bad command
ERR bad command
```

### Example 5: usage error

cmd: `kvtx extra`

stdout: (empty)

exit: `2`

## Not required

- Persistence of any kind.
- Values that contain spaces.
- Commands other than those listed (for example `EXPIRE` or `MULTI`).
- Performance beyond the stated limits.
