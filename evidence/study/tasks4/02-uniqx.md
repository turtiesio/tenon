# Task 02: uniqx (collapse runs of repeated lines)

## Goal

Write a command-line filter in the style of `uniq`. It reads lines from
stdin, groups **adjacent** lines that compare equal, and prints one line per
group. Options print a count in front of each line, keep only repeated or
only unique groups, compare case-insensitively, and ignore a number of
leading fields and characters when comparing.

## Interface

```
uniqx [-c] [-d] [-u] [-i] [-f N] [-s N]
```

- **Arguments** are processed left to right. Each option is a separate
  argument, and options may appear in any order and be repeated (for `-f` and
  `-s`, the last value wins).
  - `-c`: prefix each printed line with its group size (rule 5).
  - `-d`: print only groups of 2 or more lines.
  - `-u`: print only groups of exactly 1 line.
  - `-i`: compare ASCII case-insensitively (rule 3).
  - `-f N`: skip N fields before comparing (rule 2). Default `0`.
  - `-s N`: skip N characters before comparing, after skipping fields
    (rule 2). Default `0`.

  The value of `-f` and `-s` is the **next** argument and must match
  `[0-9]{1,4}` (leading zeros allowed).
- **Usage errors (exit 2).** Any other argument (including file names,
  combined forms such as `-ci`, and `--`), `-f` or `-s` without a following
  argument, or a malformed value. Print a message to stderr, print
  **nothing** on stdout, and do not read stdin.
- **stdin.** ASCII text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line before anything
  else. Empty lines are lines too. Empty input has no lines.
- **stdout.** The selected groups (rule 4), each line ending with `\n`.
- **Exit codes.** `0` success, `2` usage error.

## Rules

1. **Groups.** A group is a maximal run of adjacent lines whose comparison
   keys (rule 2) are equal. Lines with equal keys that are not adjacent are in
   different groups. The **first** line of a group represents it and is
   printed exactly as it was read (after `\r` removal), not as its key.
2. **Comparison key.** Start at the beginning of the line. Repeat N times
   (N from `-f`): skip any run of blanks (space or tab), then skip any run of
   non-blank characters. The rest of the line, including any blanks it
   starts with, is the remainder. Then drop the first M characters of the
   remainder (M from `-s`), or all of them if it is shorter. What is left is
   the key. If a line runs out of fields, the key is empty.
3. **Case.** With `-i`, the letters `A`-`Z` in the key are mapped to `a`-`z`
   before comparing.
4. **Selection.** Without `-d` and `-u`, every group is printed. With `-d`,
   only groups of size ≥ 2 are printed. With `-u`, only groups of size 1. With
   both, nothing is printed. Groups are printed in input order.
5. **Counts.** With `-c`, each printed line is preceded by the group size,
   right-aligned in a field of width 7 (padded on the left with spaces; a
   number with more than 7 digits is printed in full), and one space.
6. **Limits.** The input is at most 1000000 bytes.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.
In stdout blocks, a count field is padded to 7 characters, for example
`      2 a` is six spaces, `2`, a space and `a`.

### Example 1: plain and counted

stdin for both runs:
```
a
a
b
a
a
a
c
```

cmd: `uniqx` gives stdout:
```
a
b
a
c
```
exit: `0`

cmd: `uniqx -c` gives stdout:
```
      2 a
      1 b
      3 a
      1 c
```
exit: `0`

### Example 2: only repeated, only unique

stdin for all runs is the same as in Example 1.

- cmd: `uniqx -d` gives stdout `a\na\n` and exit `0`.
- cmd: `uniqx -u -c` gives stdout `      1 b\n      1 c\n` and exit `0`.
- cmd: `uniqx -d -u` gives stdout (empty) and exit `0`.

### Example 3: skipping a field, case-insensitive

cmd: `uniqx -c -i -f 1`

stdin (the third line has **two** spaces after `10:05`, and the last line
ends with `\r\n`):
```
10:01 Disk full
10:02 disk FULL
10:05  Disk full
10:07 Net down
10:09 net down
```
stdout:
```
      2 10:01 Disk full
      1 10:05  Disk full
      2 10:07 Net down
```
exit: `0`

(The keys are ` disk full`, ` disk full`, `  disk full`, ` net down`,
` net down`. The skipped field's following blanks stay in the key.)

### Example 4: skipping characters, empty lines

- cmd: `uniqx -s 2 -c` with stdin `x-apple\ny-apple\nz-pear\nApear` (no
  final newline) gives stdout `      2 x-apple\n      1 z-pear\n      1 Apear\n`
  and exit `0`. (The keys are `apple`, `apple`, `pear`, `ear`.)
- cmd: `uniqx -c` with stdin `\n\nx\n\n` gives stdout
  `      2 \n      1 x\n      1 \n` and exit `0`.
- cmd: `uniqx -f 3` with stdin `a b\nc d\n` gives stdout `a b\n` and exit
  `0` (both keys are empty).

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `uniqx -f`
- cmd: `uniqx -f x`
- cmd: `uniqx -s 12345`
- cmd: `uniqx -ci`
- cmd: `uniqx input.txt`

## Not required

- Reading from or writing to files given as arguments.
- Long options (`--count` and so on), `-w`, `-D`, `-z`.
- Locale-aware comparison or non-ASCII case folding.
- Any particular stderr wording.
