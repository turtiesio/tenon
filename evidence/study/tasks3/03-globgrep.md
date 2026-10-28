# Task 03: globgrep (filter lines with a shell-style wildcard pattern)

## Goal

Write a command-line filter that reads lines from stdin and prints those
that match a shell-style wildcard pattern as a whole. The pattern language has
`*`, `?`, bracket classes with ranges and negation, and backslash escapes.
Options select case-insensitive matching, inverted selection, and printing
only a count. Like `grep`, the exit code tells whether anything was selected,
and a malformed pattern is a usage error.

## Interface

```
globgrep [-i] [-v] [-c] [--] PATTERN
```

- **Arguments** are processed left to right. Until PATTERN has been found:
  - `-i`, `-v` and `-c` are options (they may be repeated, with no extra
    effect);
  - `--` ends the options: the next argument is PATTERN, even if it starts
    with `-`;
  - any other argument that starts with `-` (including `-` alone and
    combined forms such as `-iv`) is a usage error;
  - the first other argument is PATTERN.

  Any argument after PATTERN is a usage error. A missing PATTERN is a usage
  error. PATTERN may be the empty string.
- **Options.**
  - `-i`: ASCII case-insensitive matching (rule 4).
  - `-v`: select the lines that do **not** match.
  - `-c`: instead of the selected lines, print only their number.
- **stdin.** ASCII text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line before matching.
  Empty lines are lines too.
- **stdout.** Without `-c`: every selected line (after `\r` removal), in input
  order, each followed by `\n`. With `-c`: one line with the decimal number of
  selected lines.
- **Exit codes.** `0` if at least one line was selected, `1` if none was
  (also with `-c`, which then prints `0`), `2` usage error or invalid pattern.
  On exit `2`, print a message to stderr, print nothing on stdout, and do not
  read stdin.

## Pattern rules

A pattern matches a line only if it matches the **whole** line. The pattern
is read left to right as a sequence of elements:

1. `*` matches any sequence of characters, including the empty sequence.
2. `?` matches exactly one character.
3. `\c`, where `c` is any character, matches the character `c` literally (so
   `\*` matches `*` and `\\` matches `\`). A `\` at the very end of the
   pattern is an invalid pattern.
4. `[` starts a **class**, which matches exactly one character:
   - If the next character is `!`, the class is negated: it matches one
     character that is **not** in the set.
   - Then come the class items, up to the closing `]`. A `]` that is the
     **first** item (right after `[` or `[!`) is a literal `]`, not the end.
   - Inside a class, a *class character* is either `\c` (the literal
     character `c`) or any single character other than `\`. A `*`, `?`, `[`
     or `!` inside a class is an ordinary character.
   - Each item starts with a class character x. If x is followed by a `-`
     and then by something other than `]`, the item is the range `x-y`,
     where y is the class character after the `-`; it matches every
     character whose byte value is from x to y inclusive. If x is greater
     than y, the pattern is invalid. Otherwise the item is just x.
   - A class with no closing `]` is an invalid pattern.
5. Every other character matches itself.
6. **Case-insensitive (`-i`).** Compare characters after mapping `A`-`Z` to
   `a`-`z`. A character matches a class if its lower-case **or** upper-case
   form is in the set; a negated class matches if **neither** form is in the
   set. (So with `-i`, `[A-Z]` matches `q`, and `[!a-z]` does not match `Q`.)
7. **Examples of classes.** `[]-]` matches `]` or `-`. `[!]]` matches any
   character except `]`. `[a\-z]` matches `a`, `-` or `z`. `[-a]` and `[a-]` both
   match `-` or `a`.

## Limits

PATTERN is at most 40 bytes. The input is at most 100000 bytes. Patterns may
contain many `*` (up to 20), and tests may use lines on which naive
backtracking takes exponential time, so the matcher must take time roughly
proportional to (pattern length × line length) per line or better.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.
No argument in these examples contains a space.

### Example 1: a simple filter

cmd: `globgrep b*.txt`

stdin:
```
a.txt
b.txt
bb.txt
b.txt.bak
B.TXT
```
stdout:
```
b.txt
bb.txt
```
exit: `0`

### Example 2: a class and `?`, case-insensitive

cmd: `globgrep -i [a-c]?.TXT`

stdin:
```
a1.txt
B2.TXT
d3.txt
c.txt
cc.txt
```
stdout:
```
a1.txt
B2.TXT
cc.txt
```
exit: `0`

### Example 3: escapes, negation, `-v` and `-c`

The pattern is the 9 characters `\*[!0-9]*` (a backslash, a star, a negated
class of digits, a star). stdin for both runs:
```
*note
*1st
note*
**
*
```

cmd: `globgrep \*[!0-9]*` gives stdout:
```
*note
**
```
exit: `0`

cmd: `globgrep -v -c \*[!0-9]*` gives stdout:
```
3
```
exit: `0`

### Example 4: nothing selected, special classes, `--`

- cmd: `globgrep x*` with stdin `abc\n` gives stdout (empty) and exit `1`.
- cmd: `globgrep -c x*` with stdin `abc\n` gives stdout `0\n` and exit `1`.
- cmd: `globgrep x[]-]` with stdin `x]\nx-\nxa\n` gives stdout `x]\nx-\n`
  and exit `0`.
- cmd: `globgrep -- -v` with stdin `-v\nv\n` gives stdout `-v\n` and exit
  `0`.
- cmd: `globgrep` with an empty-string PATTERN (the `cmd` file is a single
  empty line) and stdin `a\n\nb\n` gives stdout `\n` and exit `0`.

### Example 5: usage errors and invalid patterns

Each of these gives stdout (empty) and exit `2`:

- cmd: `globgrep`
- cmd: `globgrep [abc`
- cmd: `globgrep a\` (the pattern is `a` followed by a backslash)
- cmd: `globgrep [z-a]`
- cmd: `globgrep -x a`
- cmd: `globgrep -iv a`
- cmd: `globgrep a b`

## Not required

- `**`, brace expansion `{a,b}`, character classes such as `[:alpha:]`.
- Treating `/` or a leading `.` specially.
- Non-ASCII input.
- Reading from files given as arguments.
- Any particular stderr wording.
