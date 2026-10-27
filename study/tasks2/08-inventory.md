# Task 08: inv (inventory with expiring reservations)

## Goal

Write an inventory service driven by a line protocol on stdin and stdout.
Stock is added and removed per SKU. Customers place **holds** (reservations)
that take stock out of the available amount until they are committed (the
stock leaves the warehouse), released, or they expire. Every command carries
a logical timestamp, and expiry is computed from those timestamps only.

## Interface

```
inv
```

- **Arguments.** None. If any argument is given, print a message to stderr
  and exit `2` without reading stdin.
- **stdin.** One command per line. Lines are split on `\n`. The last line may
  lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit code.** `0` at end of input.

## Commands

Every command starts with a time. Tokens are separated by exactly one space,
with no leading or trailing spaces. Command names are uppercase.

- `<t>` matches `[0-9]{1,12}`.
- `<sku>` matches `[A-Z0-9-]{1,20}`.
- `<qty>` and `<ttl>` match `[0-9]{1,9}` and must be at least 1.
- `<id>` matches `[0-9]{1,9}`.
- Leading zeros are allowed in all numbers.

| Command | Success response |
|---|---|
| `<t> ADD <sku> <qty>` | `OK <on_hand>`: adds stock, and prints the new on-hand amount. |
| `<t> REMOVE <sku> <qty>` | `OK <on_hand>`: removes stock (write-off), and prints the new on-hand amount. |
| `<t> RESERVE <sku> <qty> <ttl>` | `HOLD <id>`: creates a hold that expires at time `t + ttl`. |
| `<t> COMMIT <id>` | `OK`: the held quantity leaves the warehouse. |
| `<t> RELEASE <id>` | `OK`: the hold is cancelled, and its quantity becomes available again. |
| `<t> AVAIL <sku>` | `<sku> on_hand=<h> held=<r> available=<a>` |
| `<t> STATS` | `holds=<active> committed=<c> expired=<e> released=<r>` |

## Rules

1. **Malformed commands.** A line that does not match any form above (wrong
   token count, unknown or lowercase command, bad SKU or number, zero qty or
   ttl, empty line) gets `ERR bad command` and changes nothing.
2. **Time.** The service keeps a clock, initially 0. A well-formed command
   whose `<t>` is smaller than the clock gets `ERR time went backwards` and
   changes nothing. Otherwise, the clock is set to `<t>`. Equal times are
   allowed.
3. **Expiry first.** Right after the clock is set to `t` (before the command
   itself is carried out), every active hold whose expiry time is `≤ t`
   becomes **expired**: its quantity is no longer held. A hold created at time
   `t0` with ttl `d` is therefore usable at times `t0 .. t0 + d - 1`.
4. **Quantities per SKU.** `on_hand` is the stock in the warehouse, `held` is
   the sum of the quantities of active holds on the SKU, and
   `available = on_hand - held`. A SKU never seen before has all three equal
   to 0. `AVAIL` of such a SKU is not an error.
5. **ADD** increases `on_hand` by `qty`.
6. **REMOVE** fails with `ERR insufficient <available>` if `qty > available`.
   Otherwise it decreases `on_hand` by `qty`. Held stock can never be removed.
7. **RESERVE** fails with `ERR insufficient <available>` if
   `qty > available`. Otherwise it creates an active hold with the next id and
   responds `HOLD <id>`. Ids start at 1 and increase by 1 per successful
   `RESERVE` only.
8. **COMMIT / RELEASE** apply to a hold id:
   - active: `COMMIT` decreases `on_hand` by the hold's quantity and marks
     the hold committed; `RELEASE` marks it released. Both respond `OK`, and
     the hold is no longer active, so its quantity is no longer held.
   - expired: `ERR expired`.
   - committed, released, or never issued: `ERR no such hold`.
9. **STATS** counts holds by state: `holds` = currently active, `committed`,
   `expired` and `released` = totals since start.
10. **Limits.** At most 100000 commands. All quantities fit in a signed 64-bit
    integer.

## Examples

Each line shown ends with `\n`. In every example, cmd is `inv` with no
arguments.

### Example 1: holds, commit and expiry

stdin:
```
0 ADD WIDGET 10
1 RESERVE WIDGET 4 10
2 RESERVE WIDGET 5 5
3 AVAIL WIDGET
4 RESERVE WIDGET 2 10
5 COMMIT 1
7 AVAIL WIDGET
8 RESERVE WIDGET 2 10
11 COMMIT 2
12 STATS
```
stdout:
```
OK 10
HOLD 1
HOLD 2
WIDGET on_hand=10 held=9 available=1
ERR insufficient 1
OK
WIDGET on_hand=6 held=0 available=6
HOLD 3
ERR expired
holds=1 committed=1 expired=1 released=0
```
exit: `0`

(Hold 2 was created at 2 with ttl 5, so it expires at 7, and `AVAIL` at 7
no longer counts it.)

### Example 2: errors, REMOVE and RELEASE

stdin:
```
0 ADD A-1 5
0 RESERVE A-1 5 3
1 REMOVE A-1 1
2 RELEASE 1
2 RELEASE 1
2 REMOVE A-1 5
3 AVAIL A-1
2 AVAIL A-1
3 RESERVE B 1 1
3 ADD a 1
4 COMMIT 99
```
stdout:
```
OK 5
HOLD 1
ERR insufficient 0
OK
ERR no such hold
OK 0
A-1 on_hand=0 held=0 available=0
ERR time went backwards
ERR insufficient 0
ERR bad command
ERR no such hold
```
exit: `0`

### Example 3: the expiry boundary

stdin:
```
0 ADD X 2
0 RESERVE X 1 10
0 RESERVE X 1 10
9 COMMIT 1
10 COMMIT 2
10 STATS
10 AVAIL X
```
stdout:
```
OK 2
HOLD 1
HOLD 2
OK
ERR expired
holds=0 committed=1 expired=1 released=0
X on_hand=1 held=0 available=1
```
exit: `0`

### Example 4: arguments are a usage error

cmd: `inv now` gives stdout (empty) and exit `2`.

## Not required

- Persistence, reading the real clock.
- Extending or modifying holds, partial commits.
- Any particular stderr wording.
