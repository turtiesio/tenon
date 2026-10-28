# Task 05: reconcile (match a bank statement against a ledger)

## Goal

Write a program that reconciles a bank statement with a bookkeeping ledger.
Both are small CSV files of dated amounts. Each bank line is matched with at
most one ledger line of exactly the same amount whose date is at most a
given number of days away, choosing the closest date first. The program
prints the matches, the lines left over on each side, and a summary with the
difference between the unmatched totals.

## Interface

```
reconcile [-d DAYS] BANK LEDGER
```

- **Arguments** are examined left to right.
  - `-d DAYS`: the largest allowed date distance. The value is the **next**
    argument and must match `0|[1-9][0-9]{0,2}` and be at most `365`.
    Default `3`. If `-d` appears more than once, the last value wins.
  - Any other argument starting with `-` is a usage error.
  - Every other argument is a file name. Exactly two must be given: first
    the bank statement, then the ledger.
  - A usage error (also `-d` without a value, a bad DAYS, or not exactly two
    file names) prints a message to stderr, prints **nothing** on stdout,
    and exits `2`.
- **Files.** If either file cannot be read, or either contains an invalid
  line (rule 1), print a message to stderr, print **nothing** on stdout,
  and exit `1`.
- **stdin** is not read.
- **Exit codes.** `0` success (whether or not everything matched), `1`
  unreadable file or invalid line, `2` usage error.

## Rules

1. **File format.** Both files have the same format: ASCII text, split on
   `\n`. If a file ends with `\n`, there is no extra empty line after it. A
   final line without `\n` is still a line. One trailing `\r` is removed
   from each line. Lines are numbered from 1 in each file, counting every
   line, including empty ones. An empty line is skipped (but keeps its
   number). Every other line must be exactly `<date>,<amount>,<text>`:
   - `<date>` is `YYYY-MM-DD`, a valid date of the Gregorian calendar with
     a year from 1970 to 2099 (leap years: divisible by 4, and 2000 is a
     leap year; there are no other century years in range).
   - `<amount>` matches `-?(0|[1-9][0-9]{0,8})\.[0-9]{2}`, for example
     `12.50`, `-0.99` or `1200.00`. It is an exact number of cents; `-0.00`
     equals `0.00`.
   - `<text>` is 1 to 40 characters from `0x20` (space) to `0x7E`, without
     `,`, not starting or ending with a space.
   There is no header line. Any other non-empty line is invalid.
2. **Date distance.** The distance between two dates is the absolute
   number of days between them (2028-02-28 and 2028-03-01 are 2 days apart,
   2027-02-28 and 2027-03-01 are 1 day apart).
3. **Matching.** Go through the bank lines in file order. For each one, the
   *candidates* are the ledger lines that are not matched yet, have exactly
   the same amount (in cents) and have a date distance of at most DAYS.
   If there is a candidate, the bank line is matched with the candidate of
   the **smallest** distance; among equally distant candidates, the one
   with the smallest line number. Otherwise the bank line stays unmatched.
   A matched ledger line cannot be matched again. Earlier choices are never
   revisited.
4. **Amounts in the output** are written from the cent value: an optional
   `-` (only for negative values), the whole units without leading zeros
   (`0` if none), `.` and exactly two digits. So `-0.00` is printed `0.00`.
5. **Output.** Every line ends with `\n`. In this order:
   1. For each match, in bank-line order: `M <bank line no> <ledger line
      no> <amount> <distance>`.
   2. For each unmatched bank line, in file order: `B <line no> <date>
      <amount> <text>`.
   3. For each unmatched ledger line, in file order: `L <line no> <date>
      <amount> <text>`.
   4. One summary line: `matched=<m> bank_only=<b> ledger_only=<l>
      diff=<amount>`, where `diff` is the sum of the unmatched bank amounts
      minus the sum of the unmatched ledger amounts.
6. **Limits.** At most 10000 lines per file.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: closest date, leftovers on both sides

The working directory contains `bank.csv`:
```
2026-03-01,-45.00,Grocer
2026-03-02,1200.00,Salary
2026-03-03,-45.00,Grocer
2026-03-10,-9.99,Stream
2026-03-31,-2.50,Fee
```
and `book.csv`:
```
2026-02-28,-45.00,R1
2026-03-04,-45.00,R2
2026-03-02,1200.00,R3
2026-03-14,-9.99,R4
2026-03-05,-45.00,R5
```

cmd: `reconcile bank.csv book.csv`

stdout:
```
M 1 1 -45.00 1
M 2 3 1200.00 0
M 3 2 -45.00 1
B 4 2026-03-10 -9.99 Stream
B 5 2026-03-31 -2.50 Fee
L 4 2026-03-14 -9.99 R4
L 5 2026-03-05 -45.00 R5
matched=3 bank_only=2 ledger_only=2 diff=42.50
```
exit: `0`

(Bank line 1 has candidates R1 at distance 1 and R2 at distance 3; R5 is 4
days away. Bank line 3 then has R2 (1 day) and R5 (2 days). The stream
payment is 4 days from R4. diff = (−9.99 − 2.50) − (−9.99 − 45.00) =
42.50.)

### Example 2: a wider window

Same files as example 1.

cmd: `reconcile -d 5 bank.csv book.csv`

stdout:
```
M 1 1 -45.00 1
M 2 3 1200.00 0
M 3 2 -45.00 1
M 4 4 -9.99 4
B 5 2026-03-31 -2.50 Fee
L 5 2026-03-05 -45.00 R5
matched=4 bank_only=1 ledger_only=1 diff=42.50
```
exit: `0`

### Example 3: leap years, month and year ends, ties

The working directory contains `b.csv`:
```
2028-03-01,100.00,Rent
2027-03-01,7.00,Coffee shop
2026-01-02,0.50,Tip
```
and `k.csv` (its 4th line is empty):
```
2028-03-03,100.00,late
2028-02-28,100.00,early
2027-02-28,7.00,k1

2025-12-31,0.50,k2
```

cmd: `reconcile b.csv k.csv -d 2`

stdout:
```
M 1 1 100.00 2
M 2 3 7.00 1
M 3 5 0.50 2
L 2 2028-02-28 100.00 early
matched=3 bank_only=0 ledger_only=1 diff=-100.00
```
exit: `0`

(Both `100.00` ledger lines are 2 days from 2028-03-01, because 2028 has a
29 February; the one on line 1 wins the tie.)

### Example 4: errors

- The working directory contains `b.csv` as in example 3 and `bad.csv`
  with the single line `2027-02-29,1.00,x` (2027 is not a leap year).
  cmd: `reconcile bad.csv b.csv` gives stdout (empty) and exit `1`.
- With `b.csv` as in example 3 and no file `nope.csv`, cmd:
  `reconcile b.csv nope.csv` gives stdout (empty) and exit `1`.
- Each of these gives stdout (empty) and exit `2`: `reconcile b.csv`,
  `reconcile -d 400 b.csv b.csv`, `reconcile -d b.csv b.csv`,
  `reconcile -x b.csv b.csv`, `reconcile a b c`.

## Not required

- Quoted CSV fields, header lines, or currencies.
- Finding the matching with the most matches overall; only the greedy rule
  above is wanted.
- Any particular stderr wording.
