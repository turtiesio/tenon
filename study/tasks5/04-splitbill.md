# Task 04: splitbill (shared expenses and settlement)

## Goal

Write a program that reads a list of shared expenses and money transfers
between people, computes each person's balance in exact cents, and prints a
deterministic list of payments that settles all debts. Expenses are split
equally among their participants, and leftover cents are assigned by a fixed
rule.

## Interface

```
splitbill
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdout empty, stdin not read.
- **stdin.** UTF-8 text, one record per line. Lines are split on `\n`. If
  the input ends with `\n`, there is no extra empty line after it. A final
  line without `\n` is still a line. One trailing `\r` is removed from each
  line.
- **stdout.** The report (see "Output").
- **Exit codes.** `0` success, `1` invalid input, `2` usage error.

## Input

Each line is split into **tokens** at runs of spaces and tabs; leading and
trailing spaces and tabs are ignored.

- A line with no tokens is ignored.
- A line whose first token starts with `#` is a comment and is ignored.
- `expense <payer> <amount> <p1> [<p2> ...]`: the payer paid the amount for
  the listed participants (one or more). The payer may or may not be one of
  the participants.
- `transfer <from> <to> <amount>`: `from` gave `to` the amount of money
  directly.

Tokens:

- A **name** matches `[a-z][a-z0-9_]{0,15}`.
- An **amount** matches `[0-9]{1,7}\.[0-9]{2}` (exactly two decimals; no
  sign) and must not be zero. `12.50` is 1250 cents.

The input is **invalid** if any line that is not ignored breaks these rules:
an unknown first token (keywords are lower case), a wrong number of tokens
(`expense` needs at least 4, `transfer` exactly 4), a malformed name or
amount, a zero amount, a participant listed twice in one `expense`, or a
`transfer` whose `from` and `to` are the same. Then print a message to
stderr, print **nothing** on stdout, and exit `1`.

## Rules

All arithmetic is in integer cents.

1. **People.** Every name that appears in a valid record is a person. Each
   person has a balance, starting at 0. A positive balance means the person
   is owed money; a negative balance means the person owes money.
2. **Expense.** Let the amount be A cents and the participants p1..pn in the
   order listed. Let q = A div n and r = A mod n. Participants p1..pr owe
   q + 1 cents and the others owe q cents (so the shares add up to A). The
   payer's balance increases by A, and each participant's balance decreases
   by their share. (A payer who is also a participant gets both changes.)
3. **Transfer.** `from`'s balance increases by the amount, and `to`'s
   balance decreases by it.
4. **Settlement.** Work on a copy of the balances. Repeat while some
   balance is negative:
   - the **debtor** is the person with the most negative balance (ties: the
     name that sorts first, by byte order);
   - the **creditor** is the person with the largest positive balance
     (ties: the name that sorts first);
   - let x = min(−debtor's balance, creditor's balance). Output the payment
     "debtor pays creditor x", add x to the debtor's balance and subtract x
     from the creditor's balance.

   Balances always add up to zero, so a creditor exists whenever a debtor
   does.

## Output

1. One line per person, sorted by name (byte order): `<name> <balance>`.
2. A line `--`.
3. One line per settlement payment, in the order produced by rule 4:
   `<debtor> pays <creditor> <amount>`.

Money is written as whole units, `.`, and exactly two digits of cents, with
no leading zeros in the whole part (`0.05`, `12.00`, `1234.50`). Balances
also get a sign: `+` if positive, `-` if negative, none if zero (`+6.64`,
`-3.28`, `0.00`). Payment amounts have no sign. Every line ends with `\n`.
An input with no records gives just `--\n`.

Limits: at most 10000 lines, 1000 people, and 50 participants per expense.

## Examples

Each line shown ends with `\n`. For every example, cmd is `splitbill`.

### Example 1: a transfer

stdin:
```
expense ann 30.00 ann bob cy
expense bob 10.00 bob cy
transfer cy ann 5.00
```
stdout:
```
ann +15.00
bob -5.00
cy -10.00
--
cy pays ann 10.00
bob pays ann 5.00
```
exit: `0`

(ann: +30.00 − 10.00 − 5.00. bob: −10.00 + 10.00 − 5.00. cy: −10.00 − 5.00
+ 5.00.)

### Example 2: leftover cents, comments and spacing

stdin (the third line is empty; the fourth line starts with two spaces and
has a tab after `expense`):
```
# trip
expense dan 10.00 dan eve fay

  expense	 eve 0.05   fay dan  
```
stdout:
```
dan +6.64
eve -3.28
fay -3.36
--
fay pays dan 3.36
eve pays dan 3.28
```
exit: `0`

(1000 cents over 3 people: dan owes 334, eve and fay 333 each. 5 cents over
2 people: fay owes 3, dan owes 2.)

### Example 3: ties between creditors

stdin:
```
expense ann 90.00 ann bob cy
expense bob 60.00 bob cy dee
```
stdout:
```
ann +60.00
bob +10.00
cy -50.00
dee -20.00
--
cy pays ann 50.00
dee pays ann 10.00
dee pays bob 10.00
```
exit: `0`

(After the first payment, ann and bob are both owed 10.00; ann sorts
first.)

### Example 4: already settled, empty input

- stdin `expense gus 12.00 hal\ntransfer hal gus 12.00\n` gives stdout
  `gus 0.00\nhal 0.00\n--\n` and exit `0`.
- empty stdin gives stdout `--\n` and exit `0`.

### Example 5: errors

Each of these gives stdout (empty) and exit `1`:

- stdin `expense ann 5 bob\n` (amount without cents)
- stdin `expense ann 5.00 bob bob\n` (participant listed twice)
- stdin `expense ann 0.00 bob\n` (zero amount)
- stdin `transfer ann ann 1.00\n`
- stdin `refund ann 1.00\n`

And cmd `splitbill x` gives stdout (empty) and exit `2`.

## Not required

- Unequal (weighted) shares, currencies, or negative amounts.
- Minimizing the number of payments; the greedy rule above is the answer.
- Any particular stderr wording.
