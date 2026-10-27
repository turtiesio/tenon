# Task 04: lfagg (logfmt parser and group-by aggregator)

## Goal

Write a program that reads log lines in *logfmt* (`key=value` pairs, with
quoted values) from standard input, groups the lines by the value of one key,
and prints per-group counts. If a numeric field is named, it also prints
count, sum, minimum, maximum and mean of that field per group. Malformed lines
are skipped and counted.

## Interface

```
lfagg BY [FIELD]
```

- **Arguments.** One or two arguments. `BY` is the grouping key and `FIELD`
  the optional numeric key. Each must match the key grammar
  `[A-Za-z_][A-Za-z0-9_.]*`. Anything else (zero or more than two arguments, or
  an argument that is not a valid key) is a usage error.
- **stdin.** Log lines, ASCII, with no tab characters. Lines are split on
  `\n`. A final line without `\n` is still a line. One trailing `\r` is
  removed from each line.
- **stdout.** Group lines, then one totals line (formats below), each ending
  with `\n`.
- **stderr.** Usage messages. Not tested.
- **Exit codes.** `0` on success (malformed input lines do not change this),
  `2` for a usage error (nothing on stdout).

## Parsing a line

A line that is empty or contains only spaces is **blank**: it is ignored
completely and not counted anywhere.

Any other line is parsed from left to right into a list of pairs:

1. Skip any number of spaces. If the end of the line is reached, parsing is
   finished.
2. Read a **key**: the longest run of characters matching
   `[A-Za-z_][A-Za-z0-9_.]*` at this position. If the character here cannot
   start a key, the line is malformed.
3. Look at the character after the key:
   - end of line or a space: the pair is `key` with the value `true` (a
     *flag*);
   - `=`: read a value (step 4);
   - anything else: the line is malformed.
4. **Value** after `=`:
   - **Quoted**, if the next character is `"`. Read characters up to the next
     unescaped `"`. Inside the quotes, `\"` stands for `"` and `\\` stands for
     `\`. A backslash followed by any other character, or a missing closing
     quote, makes the line malformed. After the closing quote, the next
     character must be a space or the end of the line, otherwise the line is
     malformed.
   - **Bare**, otherwise. The value is the longest run of non-space
     characters (it may be empty, as in `user=` at the end of a line or before
     a space). If it contains `"` or `=`, the line is malformed.
5. Go back to step 1.

If the same key occurs twice in one line, the line is malformed. A malformed
line is skipped entirely. All other non-blank lines are **valid**.

A value is the decoded string: `user=bob` and `user="bob"` have the same
value.

## Aggregation

- A valid line **without** the key BY is not grouped. It is counted as
  `nokey`.
- A valid line **with** BY belongs to the group named by BY's value (which may
  be the empty string).
- With FIELD given, a group's **numeric values** are the values of FIELD on
  the group's lines where FIELD is present and its value matches
  `-?[0-9]{1,15}` (`-0` is 0). Other lines still count toward the group's
  count.

## Output

1. One line per group, sorted by **count descending**, then by group value
   **ascending, byte-wise** (the empty string sorts first).
   - Without FIELD: `<group> count=<c>`
   - With FIELD: `<group> count=<c> n=<n> sum=<s> min=<min> max=<max> avg=<avg>`,
     where `n` is the number of numeric values, `sum`, `min` and `max` are
     their sum, minimum and maximum, and `avg` is `sum / n` rounded to **2
     decimal places, half away from zero**, always printed with exactly two
     digits after the point (for example `100.00`, `0.67`, `-0.13`). A result
     that rounds to zero is printed `0.00`, never `-0.00`. If `n = 0`, print
     `n=0 sum=0 min=- max=- avg=-`.
   - `<group>` is the raw decoded value, printed as is (it may contain
     spaces). The empty group value is printed as `""` (two double-quote
     characters).
2. One totals line: `lines=<v> malformed=<m> nokey=<k>`, where `v` is the
   number of valid lines (including the nokey ones) and `m` the number of
   malformed lines.

Limits: at most 200000 lines, each at most 4000 characters. All sums fit in a
signed 64-bit integer.

## Examples

Every line shown ends with `\n`.

### Example 1: groups with a numeric field

cmd: `lfagg svc dur`

stdin:
```
ts=1 level=info svc=api dur=120 msg="GET /users"
ts=2 level=error svc=db dur=900 msg="timeout after \"30s\""
ts=3 level=info svc=api dur=80
ts=4 level=info svc=web msg=hi
bad line with "quote
ts=5 svc=api dur=abc
ts=6 level=warn dur=15 cached
```
stdout:
```
api count=3 n=2 sum=200 min=80 max=120 avg=100.00
db count=1 n=1 sum=900 min=900 max=900 avg=900.00
web count=1 n=0 sum=0 min=- max=- avg=-
lines=6 malformed=1 nokey=1
```
exit: `0`

(Line 5 is malformed because `"quote` cannot start a key. Line 6 counts for
`api` but `abc` is not numeric. Line 7 has no `svc`, and `cached` is a flag.)

### Example 2: quoting, empty values, duplicates, a blank line

cmd: `lfagg user`

stdin (the third line is empty):
```
user=bob action=login
user="bob" action=logout

user=alice action=login
user= action=ping
action=x user="a b"
user=bob user=carol
```
stdout:
```
bob count=2
"" count=1
a b count=1
alice count=1
lines=5 malformed=1 nokey=0
```
exit: `0`

(The last line repeats `user`, so it is malformed. Among the groups with
count 1, the empty value sorts first, and `a b` sorts before `alice` because
a space is smaller than `l`.)

### Example 3: rounding of the mean

cmd: `lfagg k v`

stdin:
```
k=x v=1
k=x v=1
k=x v=0
k=y v=-1
k=y v=0
k=y v=0
k=y v=0
k=y v=0
k=y v=0
k=y v=0
k=y v=0
```
stdout:
```
y count=8 n=8 sum=-1 min=-1 max=0 avg=-0.13
x count=3 n=3 sum=2 min=0 max=1 avg=0.67
lines=11 malformed=0 nokey=0
```
exit: `0`

(-1/8 = -0.125, which rounds half away from zero to -0.13. 2/3 rounds to
0.67.)

### Example 4: empty input

cmd: `lfagg svc`

stdin: (empty)

stdout:
```
lines=0 malformed=0 nokey=0
```
exit: `0`

### Example 5: usage errors

- cmd: `lfagg` gives stdout (empty) and exit `2`.
- cmd: `lfagg a b c` gives stdout (empty) and exit `2`.
- cmd: `lfagg 9lives` gives stdout (empty) and exit `2`.

## Not required

- Escape sequences other than `\"` and `\\` (for example `\n`).
- Tabs or non-ASCII input.
- Numeric values outside `-?[0-9]{1,15}` (they are simply non-numeric).
- Any particular stderr wording.
