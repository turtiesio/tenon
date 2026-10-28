# Task 01: numlines (number the lines of a text)

## Goal

Write a command-line tool that copies a text to stdout and puts a line
number in front of some or all of its lines. Options choose which lines are
numbered, the first number and the step between numbers, the width and
alignment of the number field, and the separator between the number and the
line. The text comes from a file named on the command line or from stdin.

## Interface

```
numlines [-b STYLE] [-w WIDTH] [-s SEP] [-v START] [-i STEP] [-f FORMAT] [FILE]
```

- **Arguments** are examined left to right. Options and FILE may appear in
  any order. Every option takes a value, which is always the **next**
  argument, whatever it looks like (so `-s -` sets SEP to `-`). If an option
  appears more than once, the last value wins.
  - `-b STYLE`: which lines are numbered. STYLE is exactly `a` (all lines),
    `t` (non-empty lines only) or `n` (no lines). Default `t`.
  - `-w WIDTH`: the width of the number field. WIDTH matches
    `[1-9][0-9]?` and is at most `20`. Default `6`.
  - `-s SEP`: the separator printed between the number field and the line.
    Any string, including the empty string and strings with spaces. Default
    a single tab character (`\t`).
  - `-v START`: the first line number. START matches `-?[0-9]{1,9}`.
    Default `1`.
  - `-i STEP`: added to the number after each **numbered** line. STEP
    matches `-?[0-9]{1,9}` (zero and negative steps are allowed). Default
    `1`.
  - `-f FORMAT`: how the number is written into the field, exactly `ln`,
    `rn` or `rz` (rule 3). Default `rn`.
  - An argument that does not start with `-` is FILE. At most one FILE may
    be given.
- **Usage errors.** Anything else is a usage error: an unknown argument
  starting with `-` (including `-` alone and combined forms such as `-ba`),
  an option without a following argument, a value that does not match its
  option's rule, or a second FILE. Print a message to stderr, print
  **nothing** on stdout, do not read stdin, and exit `2`.
- **Input.** The bytes of FILE, or of stdin if no FILE is given. If FILE
  cannot be opened or read, print a message to stderr, print **nothing** on
  stdout, and exit `1`.
- **Exit codes.** `0` success, `1` FILE unreadable, `2` usage error.

## Rules

1. **Lines.** The input is split on `\n`. If the input ends with `\n`, there
   is no extra empty line after it. A final line without `\n` is still a
   line. Empty input has no lines and gives no output. `\r` is an ordinary
   character: it is not removed, and a line holding only `\r` is not empty.
   Lines are copied byte for byte (the input is UTF-8 text, but nothing
   depends on the encoding).
2. **Numbered lines.** With `-b a` every line is numbered; with `-b t` every
   line except empty ones (zero characters); with `-b n` none. A numbered
   line is printed as the number field, then SEP, then the line, then `\n`.
   An unnumbered line is printed unchanged, followed by `\n`. Every output
   line ends with `\n`, also when the last input line had none.
3. **Number field.** Let N be the current number and D its decimal digits
   (no leading zeros; `0` for zero), with a leading `-` if N is negative.
   - `rn`: D right-aligned in WIDTH characters, padded on the left with
     spaces.
   - `ln`: D left-aligned in WIDTH characters, padded on the right with
     spaces.
   - `rz`: right-aligned and padded on the left with zeros. For a negative
     N the `-` comes first and the zeros go between it and the digits, so
     that the whole field is WIDTH characters (N = -7 with WIDTH 4 is
     `-007`).
   If D (with its `-`) is longer than WIDTH, it is printed in full, without
   padding and without truncation.
4. **Counting.** The first numbered line gets START. After every numbered
   line, STEP is added. Unnumbered lines do not change the number. Numbers
   stay within ±10^12, so they fit in a signed 64-bit integer.
5. **Limits.** At most 100000 lines.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces,
except where an argument contains a space; then the arguments are listed one
by one.

### Example 1: defaults

cmd: `numlines`

stdin: `alpha\nbeta\n\ngamma` (no final newline)

stdout, as escaped bytes:
```
     1\talpha\n     2\tbeta\n\n     3\tgamma\n
```
exit: `0`

(The empty line is not numbered and does not use up a number. The field is
5 spaces and the digit, 6 characters wide, followed by a tab.)

### Example 2: all lines, custom start, step and separator

arguments, one per item: `-b`, `a`, `-w`, `3`, `-s`, `: ` (a colon and a
space), `-v`, `9`, `-i`, `2`

stdin:
```
a

b
```
stdout:
```
  9: a
 11: 
 13: b
```
exit: `0`

(The second output line is ` 11: ` with a trailing space: the field, the
separator and the empty line.)

### Example 3: zero padding with negative numbers

cmd: `numlines -f rz -w 4 -v -2 -s | -b a`

stdin:
```
a
b

c
d
```
stdout:
```
-002|a
-001|b
0000|
0001|c
0002|d
```
exit: `0`

### Example 4: left alignment, numbers wider than the field

cmd: `numlines -f ln -w 3 -v 998 -s =`

stdin:
```
x
y

z
```
stdout:
```
998=x
999=y

1000=z
```
exit: `0`

With `-f ln -v 5 -w 3 -s =` the line `x` would be printed as `5  =x`.

### Example 5: files and errors

- The working directory contains a file `in.txt` with the bytes
  `one\ntwo\n`. cmd: `numlines -b n in.txt` gives stdout `one\ntwo\n` and
  exit `0`; stdin is not read.
- cmd: `numlines missing.txt` (no such file) gives stdout (empty) and exit
  `1`.
- Each of these gives stdout (empty) and exit `2`: `numlines -w 0`,
  `numlines -w 21`, `numlines -b x`, `numlines -s`, `numlines -x`,
  `numlines -v 1.5`, `numlines a.txt b.txt`.

## Not required

- Logical pages, section delimiters, or numbering lines that match a
  pattern.
- Reading more than one file, or `-` as a name for stdin.
- Any particular stderr wording.
