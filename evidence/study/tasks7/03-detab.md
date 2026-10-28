# Task 03: detab (expand tabs to spaces)

## Goal

Write a command-line tool that copies text to stdout and replaces tab
characters with the number of spaces that moves the text to the next tab
stop. Tab stops are either evenly spaced or given as an explicit list of
columns. Optionally only the tabs in a line's leading indentation are
replaced. The text comes from zero or more files, which are processed as
one concatenated stream, or from stdin.

## Interface

```
detab [-t STOPS] [-i] [FILE...]
```

- **Arguments** are examined left to right. Options and files may be mixed
  in any order.
  - `-t STOPS`: the tab stops. The value is the **next** argument. It must
    match `[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*` (one or more positive
    integers of at most 4 digits, separated by single commas) and, if it
    has more than one number, the numbers must be strictly increasing. If
    `-t` appears more than once, the last value wins. Default `8`.
  - `-i`: replace only *leading* tabs (rule 4). Repeating it changes
    nothing.
  - Any other argument starting with `-` (including `-` alone and combined
    forms such as `-it`) is a usage error, as are `-t` without a following
    argument and a STOPS value that breaks the rules above. Print a message
    to stderr, print **nothing** on stdout, do not read stdin, and exit
    `2`.
  - Every other argument is a FILE.
- **Input.** If no FILE is given, read stdin. Otherwise read the files in
  argument order and treat their contents as **one** stream, as if they
  had been concatenated (a file that does not end with `\n` continues its
  last line into the next file). A FILE that cannot be opened or read is
  skipped: print a message to stderr for it, go on with the remaining
  files, and exit `1` at the end. Stdin is not read when FILE arguments are
  given. The input is UTF-8 text.
- **stdout.** The input with tabs replaced (rules 1-4). Everything else is
  copied unchanged, including `\r` and a missing final `\n`.
- **Exit codes.** `0` success, `1` if at least one FILE could not be read,
  `2` usage error.

## Rules

1. **Columns.** Within each line, the column of a character is the number
   of characters printed before it on the same output line, starting at 0
   after each `\n`. Every character other than `\n` counts as one column,
   including `\r`, spaces and a multi-byte UTF-8 character such as `é`
   (one code point is one column).
2. **One stop value N.** If STOPS is a single number N, there is a tab stop
   at every multiple of N. A tab at column c is replaced by N − (c mod N)
   spaces (always at least 1).
3. **A list of stops.** If STOPS is a list s1 < s2 < ... < sk, a tab at
   column c is replaced by s − c spaces, where s is the smallest stop with
   s > c. If there is no such stop (c ≥ sk), the tab is replaced by
   exactly **one** space.
4. **Leading tabs only (`-i`).** With `-i`, a tab is replaced only if every
   character before it on its line is a space or a tab. A tab after the
   first other character of the line is copied unchanged, as a tab (it
   still counts as one column for any later tab, but such later tabs are
   not replaced either).
5. **Limits.** At most 100000 lines, each at most 10000 characters long
   after expansion. Stop values are at most 9999.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.
In escaped byte strings, `\t` is a tab and `\n` a newline.

### Example 1: default stops every 8 columns

cmd: `detab`

stdin: `a\tb\n\tc\nabcdefgh\ti\n`

stdout:
```
a       b
        c
abcdefgh        i
```
exit: `0`

(`a` is at column 0, so the tab at column 1 becomes 7 spaces. In the last
line the tab is at column 8, a stop, and becomes 8 spaces.)

### Example 2: every 4 columns, multi-byte characters

cmd: `detab -t 4`

stdin: `é\tx\nab\t\tc\n`

stdout:
```
é   x
ab      c
```
exit: `0`

(`é` is one column, so 3 spaces follow it. In `ab\t\tc` the first tab is
at column 2 (2 spaces), the second at column 4 (4 spaces).)

### Example 3: a list of stops

cmd: `detab -t 2,5,9`

stdin: `\tA\tB\tC\tD` (no final newline)

stdout, as escaped bytes: `  A  B   C D` (no final newline)

(Tabs at columns 0, 3, 6 and 10 become 2, 2, 3 and 1 spaces; column 10 is
past the last stop 9.)

### Example 4: leading tabs only

cmd: `detab -i -t 4`

stdin: `\t \tx\ty\n  a\tb\n`

stdout, as escaped bytes: `        x\ty\n  a\tb\n`

(The first tab, at column 0, becomes 4 spaces; then a space at column 4;
the second tab, at column 5, becomes 3 spaces. The tab after `x` is kept.)

### Example 5: several files, an unreadable file, usage errors

- The working directory contains `one.txt` with the bytes `x\ty` (no final
  newline) and `two.txt` with the bytes `\tz\n`, and no `missing.txt`.
  cmd: `detab -t 4 one.txt missing.txt two.txt` gives stdout `x   y   z\n`
  and exit `1`. (The tab from `two.txt` is at column 5 of the line that
  `one.txt` started, so it becomes 3 spaces.)
- Each of these gives stdout (empty) and exit `2`: `detab -t 0`,
  `detab -t 4,4`, `detab -t 5,3`, `detab -t 1,,2`, `detab -t`,
  `detab -x`, `detab -t 12345`.

## Not required

- Converting spaces back to tabs.
- Backspace handling, or display widths of wide or combining characters.
- Invalid UTF-8 input.
- Any particular stderr wording.
