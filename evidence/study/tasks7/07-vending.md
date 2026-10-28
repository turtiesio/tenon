# Task 07: vending (vending machine service with coin change)

## Goal

Write a vending machine controller driven by a line protocol on stdin and
stdout. An operator loads products into slots and fills the coin tubes; a
customer inserts coins, which are held apart as *credit*, and then selects
a product or asks for a refund. On a sale the inserted coins go into the
tubes and the change is paid from the tubes with a fixed greedy rule; if
that rule cannot pay the exact change, the sale is refused and the credit
is kept. A refund always returns exactly the coins that were inserted.

## Interface

```
vending
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print **nothing** on stdout, do not read stdin, and exit `2`.
- **stdin.** One command per line, ASCII. Lines are split on `\n`. If the
  input ends with `\n`, there is no extra empty line after it. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. Flush stdout after every response.
- **Exit codes.** `0` at end of input, `2` usage error.

## State and rules

All amounts are integer cents.

1. **Denominations.** The machine knows exactly six coins: `5`, `10`, `20`,
   `50`, `100` and `200`.
2. **Tubes.** For each denomination the machine has a count of coins in its
   tube, initially 0. There is no upper limit.
3. **Slots.** Slot names are a letter `A` to `F` followed by a digit `1` to
   `9` (`A1` ... `F9`). Initially every slot is empty (not loaded). A loaded
   slot has a product name, a price and a count.
4. **Credit.** The coins inserted since the last sale or refund are kept in
   an **escrow** list, apart from the tubes. The credit is their sum.
5. **Change.** To pay change of amount R from a collection of coins, go
   through the denominations from largest to smallest; for each, take as
   many coins as are available and as fit into what is still owed
   (min(available, owed div denomination)). If something is still owed at
   the end, the change **cannot be paid**. No other combination is tried,
   even if one exists.
6. **Coin lists** in responses are written from the largest denomination to
   the smallest, as `<denomination>x<count>` for each denomination with a
   non-zero count, joined with single spaces, or `-` if there are no coins.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces. `<slot>` is a slot name as in rule 3.

| Command | Response |
|---|---|
| `LOAD <slot> <name> <price> <count>` | `OK`. The slot now holds `<count>` items of `<name>` at `<price>`, replacing whatever it held. `<name>` matches `[a-z]{1,12}`; `<price>` matches `[1-9][0-9]{0,3}` and is a multiple of 5; `<count>` matches `0\|[1-9][0-9]?` (0 to 99). |
| `FILL <coin> <n>` | `OK`. Adds `<n>` coins to the tube of `<coin>`. `<coin>` is one of the six denominations written exactly as in rule 1; `<n>` matches `[1-9][0-9]{0,2}`. |
| `INSERT <coin>` | `<coin>` matches `[1-9][0-9]{0,5}`. If it is one of the six denominations, the coin is added to the escrow and the response is `CREDIT <credit>`. Otherwise the coin is not accepted: `REJECT <coin>`, and nothing changes. |
| `SELECT <slot>` | See "Selecting". |
| `REFUND` | `REFUND <credit> <coins>`: returns exactly the escrow coins (as a coin list) and empties the escrow. With no credit: `REFUND 0 -`. |
| `STOCK <slot>` | `<slot> <name> <price> <count>`, or `ERR no such slot` if the slot was never loaded. |
| `COINS` | The tube contents for all six denominations, from smallest to largest, including zeros, as `5x<n> 10x<n> 20x<n> 50x<n> 100x<n> 200x<n>`. Escrow coins are not included. |

(The `\|` in the table is only Markdown escaping for `|`.)

### Selecting

`SELECT <slot>` is checked in this order:

1. The slot was never loaded: `ERR no such slot`.
2. Its count is 0: `ERR sold out`.
3. The credit is below the price: `ERR need <price − credit>`.
4. Otherwise, add the escrow coins to the tubes and pay the change
   R = credit − price from the tubes by rule 5.
   - If it cannot be paid, undo everything: the escrow coins go back to the
     escrow (credit unchanged), the tubes are as before, and the response
     is `ERR no change`.
   - If it can be paid, remove the change coins from the tubes, empty the
     escrow, decrease the slot's count by 1, and respond
     `VEND <name> <R> <coins>`, where `<coins>` is the coin list of the
     change (`-` if R is 0).

Because the escrow coins are added first, the change may include coins the
customer just inserted.

**Errors.** A line that is not exactly one of the forms above (unknown or
lower-case command, wrong token count, a malformed slot, name, price, count
or number, a price that is not a multiple of 5, a `FILL` coin that is not a
denomination, extra spaces, an empty line) gets `ERR bad command`. A command
that gets an `ERR` or `REJECT` response changes nothing.

At most 10000 commands.

## Examples

Each line shown ends with `\n`. cmd is `vending` in every example.

### Example 1: sales with change

stdin:
```
LOAD A1 cola 120 2
FILL 10 5
FILL 50 2
INSERT 100
SELECT A1
INSERT 20
INSERT 50
SELECT A1
SELECT A1
INSERT 200
SELECT A1
SELECT A1
STOCK A1
COINS
```
stdout:
```
OK
OK
OK
CREDIT 100
ERR need 20
CREDIT 120
CREDIT 170
VEND cola 50 50x1
ERR need 120
CREDIT 200
VEND cola 80 50x1 20x1 10x1
ERR sold out
A1 cola 120 0
5x0 10x4 20x0 50x1 100x1 200x1
```
exit: `0`

(The second sale pays 80: one 50, then the 20 inserted for the first sale,
then one 10. The sold-out check comes before the credit check.)

### Example 2: the greedy rule fails

stdin:
```
LOAD B2 chips 40 5
FILL 50 1
FILL 20 3
INSERT 100
SELECT B2
FILL 10 1
SELECT B2
COINS
```
stdout:
```
OK
OK
OK
CREDIT 100
ERR no change
OK
VEND chips 60 50x1 10x1
5x0 10x0 20x3 50x0 100x1 200x0
```
exit: `0`

(Change 60 could be paid as three 20s, but the rule takes the 50 first and
then finds no 10. After a 10 is added, 50 + 10 works.)

### Example 3: escrow, rejects and refunds

stdin:
```
INSERT 25
INSERT 5
INSERT 200
INSERT 5
COINS
REFUND
REFUND
SELECT C3
LOAD C3 gum 5 0
SELECT C3
LOAD C3 gum 5 1
INSERT 5
SELECT C3
COINS
```
stdout:
```
REJECT 25
CREDIT 5
CREDIT 205
CREDIT 210
5x0 10x0 20x0 50x0 100x0 200x0
REFUND 210 200x1 5x2
REFUND 0 -
ERR no such slot
OK
ERR sold out
OK
CREDIT 5
VEND gum 0 -
5x1 10x0 20x0 50x0 100x0 200x0
```
exit: `0`

### Example 4: malformed commands

stdin (the 12th line is empty; the last line ends with a space):
```
insert 5
INSERT  5
INSERT 05
LOAD A0 x 5 1
LOAD A1 x 7 1
LOAD G1 x 5 1
LOAD A1 X 5 1
FILL 25 1
FILL 5 0
STOCK A1
REFUND now

SELECT A1 
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
ERR no such slot
ERR bad command
ERR bad command
ERR bad command
```
exit: `0`

## Not required

- Coin tube limits, banknotes, or paying change with an optimal coin
  combination.
- Any particular stderr wording.
