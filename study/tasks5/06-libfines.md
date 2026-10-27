# Task 06: libfines (library overdue fines report)

## Goal

Write a program that joins a catalog of books with a list of loans and
reports the overdue fines per library member. Each book has its own daily
fine and a cap on the fine for a single loan. Loans that refer to a book
missing from the catalog are skipped and counted. Days are plain day
numbers, so no calendar arithmetic is needed.

## Interface

```
libfines BOOKS LOANS TODAY
```

- **Arguments.** Exactly three. BOOKS and LOANS are file paths. TODAY is
  the current day number and must match `[0-9]{1,6}`. A wrong argument
  count or a malformed TODAY is a usage error: message on stderr, exit `2`,
  stdout empty. Usage errors are detected before any file is read.
- **stdin** is not read.
- **stdout.** The report (see "Output").
- **Exit codes.** `0` success, `1` a file cannot be read or is invalid, `2`
  usage error. On exit `1` print a message to stderr and **nothing** on
  stdout.

## Files

Both files are UTF-8 text. Lines are split on `\n`; if a file ends with
`\n`, there is no extra empty line after it, and a final line without `\n`
is still a line. One trailing `\r` is removed from each line. Lines that are
empty or start with `#` are ignored. Every other line is a record of fields
separated by `|` (no quoting; fields are not trimmed).

**BOOKS**: `<book_id>|<title>|<rate>|<cap>`

- `book_id` matches `[A-Za-z0-9-]{1,12}`. Book ids are unique within the
  file.
- `title` is any non-empty text without `|`.
- `rate` (fine per overdue day, in cents) and `cap` (the most one loan can
  be fined, in cents) each match `[0-9]{1,6}`.

**LOANS**: `<member>|<book_id>|<out>|<due>|<returned>`

- `member` matches `[a-z][a-z0-9]{0,11}`.
- `book_id` matches `[A-Za-z0-9-]{1,12}`.
- `out` and `due` are day numbers matching `[0-9]{1,6}`, with `due` ≥
  `out`.
- `returned` is either a day number matching `[0-9]{1,6}` that is ≥ `out`,
  or `-` if the book has not been returned.

A file is **invalid** if a record has the wrong number of fields or breaks
any of these rules, or if BOOKS contains a book id twice. A `book_id` in
LOANS that is not in BOOKS does **not** make the file invalid (rule 1).

## Rules

1. **Join.** A loan whose book id is not in BOOKS is **skipped**: it
   counts only toward `skipped` in the last line. All other rules apply to
   the remaining (matched) loans.
2. **Overdue days.** For a returned loan, days = max(0, returned − due).
   For a loan not returned, days = max(0, TODAY − due). A loan is **late**
   if days > 0.
3. **Fine.** fine = min(days × rate, cap), with the book's rate and cap.
   (A late loan may have a fine of 0, for example with rate 0.)
4. **Members.** A member appears in the report if they have at least one
   matched loan. A member's `loans` is the number of their matched loans,
   `late` the number of those that are late, and `fine` the sum of their
   fines.

## Output

1. For each member, sorted by fine **descending**, then by member name
   ascending (byte order):
   - `<member> loans=<n> late=<k> fine=<money>`
   - then, for each of that member's **late** loans, in the order they
     appear in LOANS: two spaces, `<book_id> <title> days=<d> fine=<money>`.
2. A last line `total=<money> skipped=<s>`: the sum of all fines and the
   number of skipped loans.

Money is cents written as whole units, `.`, and exactly two digits
(`0.00`, `1.25`, `30.00`). Every line ends with `\n`. Limits: at most 10000
books and 100000 loans.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by
spaces.

### Example 1: a report

The working directory contains `books.txt`:
```
# id|title|rate|cap
B1|Dune|25|500
B2|The Hobbit|10|100
B3|SICP|50|2000
```
and `loans.txt` (line 6 is empty):
```
ann|B1|1|15|20
ann|B2|3|17|-
bob|B3|5|19|19
cy|B9|2|16|30
bob|B2|20|34|39

dee|B1|40|54|-
```

cmd: `libfines books.txt loans.txt 40`

stdout:
```
ann loans=2 late=2 fine=2.25
  B1 Dune days=5 fine=1.25
  B2 The Hobbit days=23 fine=1.00
bob loans=2 late=1 fine=0.50
  B2 The Hobbit days=5 fine=0.50
dee loans=1 late=0 fine=0.00
total=2.75 skipped=1
```
exit: `0`

(ann's B2 loan is not returned: 40 − 17 = 23 days × 10 = 230, capped at
100. cy's only loan refers to the unknown book B9, so cy is not listed.)

### Example 2: caps, rate 0, CRLF

The working directory contains `b.txt` with the bytes
`X-1|Café Stories|0|0\nY|Big Book|100|300\n` and `l.txt` with the bytes
`zed|Y|1|2|6\namy|Y|1|2|3\namy|X-1|1|2|-\nzed|Q|1|2|3\r\n`.

cmd: `libfines b.txt l.txt 9`

stdout:
```
zed loans=1 late=1 fine=3.00
  Y Big Book days=4 fine=3.00
amy loans=2 late=2 fine=1.00
  Y Big Book days=1 fine=1.00
  X-1 Café Stories days=7 fine=0.00
total=4.00 skipped=1
```
exit: `0`

### Example 3: no loans

With `books.txt` from Example 1 and an empty file `empty.txt`, cmd:
`libfines books.txt empty.txt 0` gives stdout `total=0.00 skipped=0\n` and
exit `0`.

### Example 4: errors

In each case the working directory contains `books.txt` and `loans.txt`
from Example 1, plus the named file.

- `short.txt` contains `B1|Dune|25\n`. cmd: `libfines short.txt loans.txt 1`
  gives stdout (empty) and exit `1`.
- `early.txt` contains `ann|B1|10|5|-\n` (due before out). cmd:
  `libfines books.txt early.txt 1` gives stdout (empty) and exit `1`.
- `dup.txt` contains `B1|Dune|25|500\nB1|Again|1|1\n`. cmd:
  `libfines dup.txt loans.txt 1` gives stdout (empty) and exit `1`.
- cmd: `libfines books.txt missing.txt 1` (no such file) gives stdout
  (empty) and exit `1`.
- cmd: `libfines books.txt loans.txt` gives stdout (empty) and exit `2`.
- cmd: `libfines books.txt loans.txt -1` gives stdout (empty) and exit `2`.

## Not required

- Calendar dates; day numbers are plain integers.
- Quoting or escaping `|` in titles.
- Checking that `returned` is not after TODAY (it may be).
- Any particular stderr wording.
