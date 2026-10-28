# Task 03: colalign (align text into columns)

## Goal

Write a command-line filter in the style of `column -t`. It reads lines from
stdin, splits each line into fields, and prints the fields aligned in
columns: every column is as wide as its widest field. Options choose the
input separator, the output separator, and which columns are right-aligned.

## Interface

```
colalign [-s CHAR] [-o OUTSEP] [-r LIST]
```

- **Arguments** are processed left to right. Each option takes the **next**
  argument as its value. Options may appear in any order and may be
  repeated; the last value wins.
  - `-s CHAR`: split fields on CHAR, which must be exactly one character
    (one Unicode code point). Default: split on whitespace (rule 1).
  - `-o OUTSEP`: the string placed between output fields, used literally
    (may be empty). Default: two spaces.
  - `-r LIST`: right-align the listed columns. LIST must match
    `[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*`; columns are numbered from 1.
    Repeated numbers are fine, and numbers beyond the last column are
    ignored.
- **Usage errors (exit 2).** Any other argument (including file names), an
  option without a following argument, a `-s` value that is not exactly one
  character, or a malformed LIST. Print a message to stderr, print
  **nothing** on stdout, and do not read stdin.
- **stdin.** UTF-8 text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n`
  is still a line. One trailing `\r` is removed from each line before
  anything else. Empty input has no lines.
- **stdout.** One output line per input line, each ending with `\n`.
- **Exit codes.** `0` success, `2` usage error.

## Rules

1. **Fields.**
   - Without `-s`: fields are the maximal runs of characters other than
     space and tab. Leading and trailing spaces and tabs are ignored, so a
     line made only of spaces and tabs (or an empty line) has **no**
     fields.
   - With `-s CHAR`: an empty line has no fields. Any other line is split at
     **every** occurrence of CHAR, so empty fields are possible: `a::b` split
     on `:` gives `a`, (empty), `b`, and `:c:` gives (empty), `c`, (empty).
     Spaces are ordinary characters in this mode and are kept.
2. **Widths.** The length of a field is its number of Unicode code points.
   The width of column k is the largest length of a k-th field over **all**
   lines (lines with fewer than k fields do not take part).
3. **Padding.** In each line, the k-th field is padded with spaces to the
   width of column k: on the **left** if column k is right-aligned, on the
   **right** otherwise. Exception: the **last** field of a line is not
   padded if its column is left-aligned (so lines never end with padding
   spaces from a left-aligned column). A right-aligned last field is padded
   as usual.
4. **Output.** Each line's padded fields are joined with OUTSEP. A line
   with no fields is printed as an empty line.
5. **Limits.** At most 10000 lines and 100 fields per line.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces;
`' | '` stands for one argument of three characters (space, `|`, space). In
stdout blocks, the end of each line is shown with `|` after it where
trailing spaces matter; that `|` is **not** part of the output.

### Example 1: right-aligned numbers

cmd: `colalign -r 2,3`

stdin:
```
name qty price
apple 3 1.25
kiwi 12 0.5
```
stdout:
```
name   qty  price
apple    3   1.25
kiwi    12    0.5
```
exit: `0`

(Widths are 5, 3 and 5.)

### Example 2: whitespace splitting and blank lines

cmd: `colalign`

stdin (line 1 starts with two spaces, line 2 is empty, line 4 is a single
tab, line 5 starts with a space):
```
  a   bb  c

ddd e
	
 x
```
stdout:
```
a    bb  c

ddd  e

x
```
exit: `0`

That is, exactly the bytes `a    bb  c\n\nddd  e\n\nx\n`.

### Example 3: a separator character, an output separator, UTF-8

cmd: `colalign -s , -o ' | ' -r 3`

stdin:
```
id,city,pop
1,Zürich,421878
22,,9
333,Bern
```
stdout (the `|` at the end of each line marks the line end):
```
id  | city   |    pop|
1   | Zürich | 421878|
22  |        |      9|
333 | Bern|
```
exit: `0`

That is, exactly the bytes
`id  | city   |    pop\n1   | Zürich | 421878\n22  |        |      9\n333 | Bern\n`.
(`Zürich` has 6 code points. In the last line `Bern` is the last field and
its column is left-aligned, so it is not padded.)

### Example 4: empty fields and CRLF

cmd: `colalign -s : -o -` with stdin `a:b\r\n:c:\n` gives stdout
`a-b\n -c-\n` and exit `0`. (The second line has the fields (empty), `c`,
(empty); the first column has width 1.)

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `colalign -s`
- cmd: `colalign -s ab`
- cmd: `colalign -r 0`
- cmd: `colalign -r 1,,2`
- cmd: `colalign -x`
- cmd: `colalign file.txt`

## Not required

- Display width of wide (East Asian) or combining characters; a code point
  counts as 1.
- Quoting or escaping of separators.
- Reading files given as arguments.
- Any particular stderr wording.
