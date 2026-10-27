# Task 07: parking (parking garage service)

## Goal

Write a parking garage service driven by a line protocol on stdin and
stdout. Cars enter and leave at given times. Each entering car gets the
lowest-numbered free spot, and each leaving car is charged a fee computed
from its parking duration with a grace period, hourly charges and a daily
cap. The service keeps a clock that may not go backwards, and reports where
a car is parked and the totals so far. Each command produces exactly one
response line.

## Interface

```
parking CAPACITY
```

- **Arguments.** Exactly one argument, CAPACITY, matching `[0-9]{1,4}` with a
  value from 1 to 1000: the number of spots, numbered 1 to CAPACITY.
  Anything else (no argument, more arguments, a bad value) is a usage error:
  print a message to stderr, print nothing on stdout, exit `2`, and do not
  read stdin.
- **stdin.** One command per line. A line ends with `\n` (a trailing `\r` is
  removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `2` usage error.

## Commands

Tokens are separated by exactly one space. There are no leading or trailing
spaces, and command names are uppercase.

```
IN <plate> <time>
OUT <plate> <time>
WHERE <plate>
STATUS
```

- `<plate>` matches `[A-Z0-9]{1,8}`.
- `<time>` matches `[0-9]{1,7}`: minutes since the garage opened (leading
  zeros allowed).

Any line that is not exactly one of these forms (bad token, wrong token
count, extra spaces, lower-case command, empty line) gets `ERR bad command`
and changes nothing.

## Rules

1. **Clock.** The garage clock starts at 0. For `IN` and `OUT`, after the
   syntax check and **before anything else**: if `<time>` is smaller than the
   clock, respond `ERR bad time` and change nothing. Otherwise set the clock
   to `<time>`. The clock stays set even if the command then fails with
   `ERR already parked`, `FULL` or `ERR not parked`. Equal times are allowed.
2. **IN.** In this order:
   - If the plate is currently parked: `ERR already parked`.
   - If all spots are taken: `FULL`.
   - Otherwise the car takes the **lowest-numbered free** spot s and its entry
     time is recorded: respond `OK <s>`.
3. **OUT.** If the plate is not currently parked: `ERR not parked`.
   Otherwise the car leaves, its spot becomes free, the fee (rule 4) is
   added to the revenue, and the response is `FEE <amount>`.
4. **Fee.** Let `d` = exit time − entry time, in minutes. The fee in cents
   is:
   - `0` if `d ≤ 15` (grace period);
   - otherwise, with `days = d / 1440` and `rest = d % 1440` (integer
     division): `days × 2000 + min(2000, 250 × ceil(rest / 60))`.

   So each started hour costs 250 cents, a day costs at most 2000 cents, and
   a rest of 0 minutes costs nothing. For example: d=16 and d=60 cost 250,
   d=61 costs 500, d=600 costs 2000, d=1440 costs 2000, d=1441 costs 2250.
5. **WHERE.** `SPOT <s>` if the plate is parked in spot s, otherwise
   `ERR not parked`.
6. **STATUS.** `free=<f> parked=<p> revenue=<amount>`, where the revenue is
   the sum of all fees charged so far.
7. **Amounts** of c cents are written as `c / 100` (decimal, no leading
   zeros, `0` if zero), `.`, and `c % 100` as exactly two digits: `0.00`,
   `2.50`, `142.05`.
8. A plate that has left may enter again later, as a new stay.
9. **Limits.** At most 100000 commands.

## Examples

Each line shown ends with `\n`.

### Example 1: spots, FULL and reuse of the lowest spot

cmd: `parking 2`

stdin:
```
IN AB12 0
IN CD34 5
IN EF56 10
OUT AB12 20
IN EF56 20
WHERE EF56
STATUS
OUT CD34 70
STATUS
```
stdout:
```
OK 1
OK 2
FULL
FEE 2.50
OK 1
SPOT 1
free=0 parked=2 revenue=2.50
FEE 5.00
free=1 parked=1 revenue=7.50
```
exit: `0`

### Example 2: the clock, the grace period and a stay over a day

cmd: `parking 1`

stdin:
```
IN A 100
IN B 90
OUT A 115
IN B 115
OUT B 1556
OUT B 1600
IN A 0100
OUT A 1640
STATUS
```
stdout:
```
OK 1
ERR bad time
FEE 0.00
OK 1
FEE 22.50
ERR not parked
ERR bad time
ERR not parked
free=1 parked=0 revenue=22.50
```
exit: `0`

(A stays 15 minutes, which is free. B stays 1441 minutes: one day, 2000
cents, plus one started hour, 250 cents. `OUT B 1600` sets the clock to 1600
even though it fails, so `IN A 0100` is too early.)

### Example 3: the daily cap

cmd: `parking 5`

stdin:
```
IN Z 0
IN Y 0
OUT Z 600
IN Z 600
OUT Y 1440
OUT Z 3540
STATUS
```
stdout:
```
OK 1
OK 2
FEE 20.00
OK 1
FEE 20.00
FEE 42.50
free=5 parked=0 revenue=82.50
```
exit: `0`

(Z's first stay is 600 minutes: 10 started hours, capped at 2000. Y stays
exactly 1440 minutes. Z's second stay is 2940 minutes: two days and 60
minutes, 4000 + 250.)

### Example 4: malformed commands and errors

cmd: `parking 3`

stdin (the 8th line is `STATUS` followed by a space, and the 9th line is
empty):
```
in A 1
IN a 1
IN A  1
IN ABCDEFGHI 1
IN A 12345678
IN A
WHERE
STATUS 

IN A 1
IN A 2
WHERE B
OUT B 3
```
stdout:
```
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
OK 1
ERR already parked
ERR not parked
ERR not parked
```
exit: `0`

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `parking`
- cmd: `parking 0`
- cmd: `parking 1001`
- cmd: `parking x`
- cmd: `parking 5 6`

## Not required

- Persistence between runs.
- Reservations, spot types, or different rates per car.
- Times beyond 9999999 minutes.
- Any particular stderr wording.
