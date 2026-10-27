# Task 07: orderbook (limit-order matching service)

## Goal

Write a single-instrument limit-order matching engine driven by a line
protocol on stdin and stdout. Buy and sell orders are matched with
**price-time priority**. Each trade executes at the resting (maker) order's
price, and unfilled remainders rest in the book. Orders can be cancelled, and
the book can be printed as aggregated price levels. Each command produces
exactly one response line.

## Interface

```
orderbook
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. A line ends with `\n` (a trailing `\r` is
  removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit code.** `0` at EOF.

## Commands

Tokens are separated by exactly one space. There are no leading or trailing
spaces, and command names are uppercase.

```
BUY <id> <qty> <price>
SELL <id> <qty> <price>
CANCEL <id>
BOOK
```

- `<id>` matches `[A-Za-z0-9_-]{1,16}`.
- `<qty>` and `<price>` match `[1-9][0-9]{0,8}` (1 to 999999999, no leading
  zeros).

## Rules

1. **Malformed commands.** Any line that is not exactly one of the forms above
   gets `ERR bad command`. That includes a bad token, the wrong token count,
   extra spaces and an empty line. The id is **not** consumed.
2. **Duplicate ids.** A syntactically valid `BUY`/`SELL` whose id was already
   used by any earlier **accepted** order (resting, filled or cancelled) gets
   `ERR duplicate id` and is ignored.
3. **Matching.** An incoming BUY at limit price P matches resting SELL orders
   whose price is ≤ P. An incoming SELL at limit P matches resting BUY orders
   whose price is ≥ P.
   - Candidates are taken in priority order. For resting sells, the lowest
     price comes first. For resting buys, the highest price comes first. At
     equal price, the earlier accepted order comes first (time priority).
   - Each match trades `min(remaining incoming, remaining resting)` at the
     **resting order's price**.
   - A fully filled resting order leaves the book.
   - Matching continues until the incoming order is filled or no candidate is
     left. Any remainder then **rests** in the book at its own limit price,
     with time priority equal to its acceptance time.
4. **Order response.** An accepted order is answered with:

   ```
   OK <id> filled=<F> resting=<R> trades=<T>
   ```

   - `F` is the total quantity traded by this order.
   - `R` is the quantity left resting (F + R = qty).
   - `T` is `-` if there were no trades. Otherwise it lists the trades in
     execution order, separated by commas without spaces, each written as
     `<maker id>:<qty>@<price>`.
5. **CANCEL.**
   - If `<id>` is an order currently resting in the book, remove it and
     respond `CANCELED <id> <remaining qty>`.
   - Otherwise (never seen, already fully filled, or already cancelled)
     respond `ERR unknown order`.
   - A malformed CANCEL gets `ERR bad command`.
6. **BOOK.** Respond with:

   ```
   BOOK bids=<levels> asks=<levels>
   ```

   - Levels aggregate all resting quantity at one price, written as
     `<price>:<total qty>` and separated by commas.
   - Bids are listed in descending price order and asks in ascending price
     order. An empty side is `-`.
7. **Numbers.** All quantities and prices are printed as plain decimal
   integers. Per-level totals stay below 2^53.
8. **Limits.** At most 100000 commands.

## Examples

Each line shown ends with `\n`. For every example, cmd is `orderbook` and exit
is `0`, except where noted.

### Example 1: sweeping several levels with time priority

stdin:
```
SELL s1 10 101
SELL s2 5 100
SELL s3 5 100
BUY b1 12 101
BOOK
```
stdout:
```
OK s1 filled=0 resting=10 trades=-
OK s2 filled=0 resting=5 trades=-
OK s3 filled=0 resting=5 trades=-
OK b1 filled=12 resting=0 trades=s2:5@100,s3:5@100,s1:2@101
BOOK bids=- asks=101:8
```

### Example 2: cancel, then a partially resting sell

stdin:
```
BUY b1 5 99
BUY b2 7 99
BUY b3 1 98
CANCEL b1
CANCEL b1
SELL s1 10 98
BOOK
```
stdout:
```
OK b1 filled=0 resting=5 trades=-
OK b2 filled=0 resting=7 trades=-
OK b3 filled=0 resting=1 trades=-
CANCELED b1 5
ERR unknown order
OK s1 filled=8 resting=2 trades=b2:7@99,b3:1@98
BOOK bids=- asks=98:2
```

### Example 3: errors and duplicate ids

stdin:
```
BUY a 0 10
BUY a 5 10
SELL a 5 10
SELL b 5 11
CANCEL a
HELLO
BUY c 3 011
BOOK
```
stdout:
```
ERR bad command
OK a filled=0 resting=5 trades=-
ERR duplicate id
OK b filled=0 resting=5 trades=-
CANCELED a 5
ERR bad command
ERR bad command
BOOK bids=- asks=11:5
```

### Example 4: aggregated levels; filled orders cannot be cancelled or reused

stdin:
```
BUY x 3 50
BUY y 4 50
BUY z 2 49
SELL w 3 51
SELL v 3 50
CANCEL x
BUY x 1 10
BOOK
```
stdout:
```
OK x filled=0 resting=3 trades=-
OK y filled=0 resting=4 trades=-
OK z filled=0 resting=2 trades=-
OK w filled=0 resting=3 trades=-
OK v filled=3 resting=0 trades=x:3@50
ERR unknown order
ERR duplicate id
BOOK bids=50:4,49:2 asks=51:3
```

### Example 5: usage error

cmd: `orderbook --verbose`

stdout: (empty)

exit: `2`

## Not required

- Market orders, IOC/FOK, order amendment, or more than one instrument.
- Persistence.
- Self-trade prevention: an order may match any resting order.
