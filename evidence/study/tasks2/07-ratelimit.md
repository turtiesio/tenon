# Task 07: rl (token-bucket rate limiter service)

## Goal

Write a rate-limiter service driven by a line protocol on stdin and stdout.
Named policies define token buckets (a capacity and a refill interval). Each
client of a policy has its own bucket. Requests carry an explicit logical
timestamp, so the behaviour is fully deterministic: the program never reads
the real clock.

## Interface

```
rl
```

- **Arguments.** None. If any argument is given, print a message to stderr
  and exit `2` without reading stdin.
- **stdin.** One command per line. Lines are split on `\n`. The last line may
  lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit code.** `0` at end of input.

## Commands

Tokens are separated by exactly one space, with no leading or trailing
spaces. Command names are uppercase.

- `<name>` (policy or client) matches `[a-z0-9_.-]{1,32}`.
- `<time>` matches `[0-9]{1,15}`.
- `<capacity>`, `<interval>` and `<cost>` match `[0-9]{1,9}` and must be at
  least 1.
- Leading zeros are allowed in all numbers.

| Command | Success response |
|---|---|
| `POLICY <policy> <capacity> <interval>` | `OK`. Creates a policy: buckets hold at most `capacity` tokens, and one token is added every `interval` time units. |
| `HIT <time> <policy> <client>` or `HIT <time> <policy> <client> <cost>` | `ALLOW <remaining>` or `DENY <retry_after>` (rules below). The default cost is 1. |
| `PEEK <time> <policy> <client>` | `TOKENS <n>`: the client's tokens at `time`, after refill. |
| `RESET <policy> <client>` | `OK`. Deletes the client's bucket. |
| `STATS <policy>` | `allowed=<a> denied=<d> clients=<c>` |

## Rules

1. **Malformed commands.** A line that does not match any form above (wrong
   token count, unknown or lowercase command, a bad name or number, a zero
   capacity, interval or cost, an empty line) gets `ERR bad command` and
   changes nothing.
2. **Clock.** The service keeps a clock, initially 0. A well-formed `HIT` or
   `PEEK` whose `<time>` is smaller than the clock gets
   `ERR time went backwards` and changes nothing. Otherwise, the clock is set
   to `<time>`, **even if the command then fails** with one of the errors
   below. Equal times are allowed.
3. **Errors**, checked in this order after rules 1 and 2:
   - `POLICY` with an existing policy name: `ERR policy exists`.
   - `HIT`, `PEEK`, `RESET` or `STATS` with an unknown policy:
     `ERR no such policy`.
   - `HIT` with `cost > capacity`: `ERR cost exceeds capacity`.
   - `RESET` of a client that has no bucket in that policy:
     `ERR no such client`.

   An error response changes nothing (apart from the clock, per rule 2). In
   particular, it does not create a bucket.
4. **Buckets.** A bucket has `tokens` and an `anchor` time. A successful
   `HIT` or `PEEK` for a client without a bucket first creates it with
   `tokens = capacity` and `anchor = time`.
5. **Refill.** Every successful `HIT` or `PEEK` at time `now` first refills the
   bucket:
   - If `tokens == capacity`: set `anchor = now`.
   - Otherwise: let `k = (now - anchor) div interval` (integer division). Set
     `tokens = min(capacity, tokens + k)`. If now `tokens == capacity`, set
     `anchor = now`. Otherwise set `anchor = anchor + k * interval`.
6. **HIT.** After the refill, if `tokens ≥ cost`, set `tokens = tokens - cost`
   and respond `ALLOW <tokens>` (the tokens left). Otherwise respond
   `DENY <r>` with `r = anchor + (cost - tokens) * interval - now`, the time
   until enough tokens will have been added. A denied hit consumes nothing.
7. **Counters.** Each policy counts `allowed` and `denied` hits since it was
   created. `RESET` does not change them. `clients` is the number of buckets
   that currently exist in the policy.
8. **Limits.** At most 100000 commands. All values fit in a signed 64-bit
   integer.

## Examples

Each line shown ends with `\n`.

### Example 1: consuming and refilling

cmd: `rl` (no arguments)

stdin:
```
POLICY api 3 10
HIT 0 api alice
HIT 1 api alice
HIT 2 api alice
HIT 3 api alice
HIT 12 api alice
PEEK 12 api alice
HIT 25 api alice 2
STATS api
```
stdout:
```
OK
ALLOW 2
ALLOW 1
ALLOW 0
DENY 7
ALLOW 0
TOKENS 0
DENY 5
allowed=4 denied=2 clients=1
```
exit: `0`

(At 3: no token yet, the next one comes at 0 + 10, so retry after 7. At 12:
one token was added, and the anchor moves to 10. At 25: one more token
(anchor 20), but cost 2 needs one more at 30, so retry after 5.)

### Example 2: errors and the clock

stdin:
```
HIT 5 api bob
POLICY api 2 100
POLICY api 5 5
HIT 50 api bob 3
HIT 40 api bob
hit 60 api bob
HIT 60 api bob
RESET api bob
RESET api bob
PEEK 61 api bob
STATS web
STATS api
```
stdout:
```
ERR no such policy
OK
ERR policy exists
ERR cost exceeds capacity
ERR time went backwards
ERR bad command
ALLOW 1
OK
ERR no such client
TOKENS 2
ERR no such policy
allowed=1 denied=0 clients=1
```
exit: `0`

(`HIT 50 ...` fails, but it still moves the clock to 50, so `HIT 40` goes
backwards.)

### Example 3: the anchor while the bucket is full

stdin:
```
POLICY p 2 10
HIT 0 p c
HIT 0 p c
HIT 15 p c
HIT 100 p c
HIT 105 p c
HIT 109 p c
HIT 110 p c
```
stdout:
```
OK
ALLOW 1
ALLOW 0
ALLOW 0
ALLOW 1
ALLOW 0
DENY 1
ALLOW 0
```
exit: `0`

(At 100 the bucket refills to full, so the anchor becomes 100 and no tokens
are "banked" from the idle time. The next token after that is due at 110.)

### Example 4: arguments are a usage error

cmd: `rl extra` gives stdout (empty) and exit `2`.

## Not required

- Reading the real clock, persistence, multiple threads.
- Changing or deleting a policy.
- Any particular stderr wording.
