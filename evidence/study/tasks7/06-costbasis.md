# Task 06: costbasis (realized gains with first-in, first-out lots)

## Goal

Write a program that reads a list of share trades and computes the realized
gain or loss of every sale. Each purchase creates a *lot*; a sale uses up
the oldest shares first (first in, first out), taking a proportional,
exactly rounded part of a lot's cost when it uses only part of the lot.
Stock splits multiply the share counts without changing the costs. At the
end the program prints the remaining holdings and the total realized gain.
All money is handled as integer cents.

## Interface

```
costbasis
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print **nothing** on stdout, do not read stdin, and exit `2`.
- **stdin.** ASCII text, one trade per line. Lines are split on `\n`. If the
  input ends with `\n`, there is no extra empty line after it. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
  Lines are numbered from 1, counting every line (also empty and comment
  lines).
- **stdout.** One line for each sale, split and error, in input order,
  then the holdings and the total (rule 7).
- **Exit codes.** `0` if no line produced an `ERR` line, `1` if at least one
  did, `2` usage error.

## Rules

1. **Line forms.** Tokens are separated by exactly one space, with no
   leading or trailing spaces. `<sym>` matches `[A-Z]{1,5}`, `<qty>`
   matches `[1-9][0-9]{0,5}`, `<price>` (per share) matches
   `(0|[1-9][0-9]{0,5})\.[0-9]{2}` and is read as cents, and `<ratio>` is
   an integer from `2` to `10` (no leading zeros).
   - `BUY <sym> <qty> <price>`
   - `SELL <sym> <qty> <price>`
   - `SPLIT <sym> <ratio>`
   - An empty line, or a line whose first character is `#`, is ignored and
     prints nothing.
   - Any other line (lower-case words, a missing or extra token, a price
     without exactly two decimals, ...) prints `<n>: ERR bad line`, where
     `<n>` is its line number, and is otherwise ignored.
2. **Lots.** Each symbol has a list of lots, oldest first. A lot has a
   quantity q and a cost C in cents. `BUY` appends a new lot with q =
   `<qty>` and C = `<qty>` × `<price>`. It prints nothing.
3. **Selling.** For `SELL <sym> <k> <price>`, let h be the total quantity
   of the symbol's lots.
   - If k > h, print `<n>: ERR insufficient <sym> held=<h>` and change
     nothing (h is `0` for a symbol with no lots).
   - Otherwise, take k shares from the lots, oldest first. A lot that is
     used up completely contributes its whole cost C and is removed. If
     only j of a lot's q shares are needed (j < q), that lot contributes
     the part P = C × j / q rounded to the nearest cent, with an exact half
     rounded **up**: in integer arithmetic P = (2 × C × j + q) div (2 × q).
     The lot keeps q − j shares and cost C − P.
   - The sale's cost is the sum of the contributions, its proceeds are
     k × `<price>`, and its gain is proceeds − cost (it may be negative).
     Print `<n>: SELL <sym> <k> proceeds=<p> cost=<c> gain=<g>`.
4. **Splits.** For `SPLIT <sym> <r>`: if the symbol has no lots, print
   `<n>: ERR not held <sym>`. Otherwise multiply the quantity of every lot
   of the symbol by r; costs do not change. Print
   `<n>: SPLIT <sym> <r> held=<h>` with the new total quantity h.
5. **Money** is printed from its cent value: an optional `-` (only for
   negative values), the whole units without leading zeros (`0` if none),
   `.` and exactly two digits, for example `27.00`, `0.33`, `-3.10`.
6. **Total gain.** The sum of the gains of all successful sales.
7. **Output.** Every line ends with `\n`. After the per-line output, print
   one line `HOLD <sym> <h> cost=<c> lots=<l>` for every symbol that still
   has lots, sorted by symbol (byte order), where h is the total quantity,
   c the total remaining cost and l the number of lots. Then print
   `TOTAL gain=<g>`.
8. **Limits.** At most 10000 lines. Tests keep every lot's quantity and
   cost below 10^9, so 2 × C × j fits in a signed 64-bit integer.

## Examples

Each line shown ends with `\n`. cmd is `costbasis` in every example.

### Example 1: first in, first out

stdin:
```
BUY ACME 10 12.50
BUY ACME 5 14.00
SELL ACME 12 15.00
BUY ZED 3 1.00
SELL ACME 3 13.00
```
stdout:
```
3: SELL ACME 12 proceeds=180.00 cost=153.00 gain=27.00
5: SELL ACME 3 proceeds=39.00 cost=42.00 gain=-3.00
HOLD ZED 3 cost=3.00 lots=1
TOTAL gain=24.00
```
exit: `0`

(The first sale uses the whole first lot, cost 125.00, and 2 of the 5
shares of the second lot, 70.00 × 2 / 5 = 28.00. The second lot keeps 3
shares and cost 42.00, which the second sale uses up.)

### Example 2: a split and rounding

stdin:
```
BUY X 1 1.00
SPLIT X 3
SELL X 1 0.50
SELL X 1 0.50
SELL X 1 0.40
```
stdout:
```
2: SPLIT X 3 held=3
3: SELL X 1 proceeds=0.50 cost=0.33 gain=0.17
4: SELL X 1 proceeds=0.50 cost=0.34 gain=0.16
5: SELL X 1 proceeds=0.40 cost=0.33 gain=0.07
TOTAL gain=0.40
```
exit: `0`

(After the split the lot is 3 shares costing 100 cents. 100 × 1 / 3 =
33.33 rounds to 33, leaving 2 shares at 67 cents. 67 × 1 / 2 = 33.5 rounds
up to 34, leaving 1 share at 33 cents. All symbols are sold out, so there
is no `HOLD` line.)

### Example 3: errors, comments and blank lines

stdin (the 3rd line is empty):
```
# opening positions
BUY AB 4 2.50

SELL AB 5 3.00
SPLIT CD 2
sell AB 1 3.00
BUY AB 1 3.0
BUY  AB 1 3.00
SELL AB 4 2.00
BUY Q 2 0.00
```
stdout:
```
4: ERR insufficient AB held=4
5: ERR not held CD
6: ERR bad line
7: ERR bad line
8: ERR bad line
9: SELL AB 4 proceeds=8.00 cost=10.00 gain=-2.00
HOLD Q 2 cost=0.00 lots=1
TOTAL gain=-2.00
```
exit: `1`

### Example 4: several lots and symbols

stdin:
```
BUY B 3 10.00
BUY A 2 5.00
BUY B 4 11.00
SPLIT B 2
SELL B 7 6.00
SELL A 1 5.01
```
stdout:
```
4: SPLIT B 2 held=14
5: SELL B 7 proceeds=42.00 cost=35.50 gain=6.50
6: SELL A 1 proceeds=5.01 cost=5.00 gain=0.01
HOLD A 1 cost=5.00 lots=1
HOLD B 7 cost=38.50 lots=1
TOTAL gain=6.51
```
exit: `0`

(After the split the lots of B are 6 shares for 30.00 and 8 shares for
44.00. Selling 7 uses up the first lot and takes 1 of the 8 shares of the
second: 4400 × 1 / 8 = 550 cents, so the cost is 30.00 + 5.50 = 35.50 and
the second lot keeps 7 shares at 38.50. Holdings are sorted by symbol, not
by first purchase.)

## Not required

- Fees, dividends, short selling, fractional shares or reverse splits.
- Dates or holding periods.
- Any particular stderr wording.
