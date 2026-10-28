# Task 02: trx (translate, delete and squeeze characters)

## Goal

Write a command-line filter in the style of `tr`. It copies stdin to stdout,
translating characters of one set into the corresponding characters of a
second set, or deleting characters, and optionally squeezing runs of a
repeated character into one. Sets are written with ranges such as `a-z` and
a few backslash escapes.

## Interface

```
trx [-d] [-s] [--] SET1 [SET2]
```

- **Options.** Arguments are examined from the left. While the current
  argument is exactly `-d` or `-s`, it is an option (repeats are allowed and
  change nothing). An argument that is exactly `--` ends the options and is
  skipped. Any other argument that starts with `-` and is at least 2
  characters long, met **before** the first set, is a usage error. The first
  argument that is not an option starts the sets; it and **all** later
  arguments are sets, whatever they look like (so in `trx a -d`, `-d` is
  SET2). A lone `-` is a set.
- **Number of sets.**

  | Options | Sets | Meaning |
  |---|---|---|
  | none | exactly 2 | translate SET1 to SET2 |
  | `-d` | exactly 1 | delete SET1 |
  | `-s` | exactly 1 | squeeze SET1 |
  | `-s` | exactly 2 | translate SET1 to SET2, then squeeze SET2 |
  | `-d` and `-s` | exactly 2 | delete SET1, then squeeze SET2 |

  Any other count is a usage error.
- **Usage errors (exit 2).** A wrong number of sets, an unknown option, a
  malformed set (rule 1), or an empty SET2 when translating (the first and
  fourth rows of the table). Print a message to stderr, print **nothing** on
  stdout, and do not read stdin.
- **stdin.** ASCII text (bytes 0x00-0x7F), at most 1000000 bytes. It is
  processed as one stream of characters; newlines are ordinary characters.
- **stdout.** The transformed stream.
- **Exit codes.** `0` success, `2` usage error.

## Rules

1. **Set syntax.** A set argument is read in two passes. Set arguments are
   ASCII.
   - **Tokens.** Read the argument left to right. `\n` (backslash, `n`)
     stands for a newline, `\t` for a tab, `\\` for one backslash, and `\-`
     for an *escaped* `-`. A backslash followed by any other character, or a
     backslash at the very end, makes the set malformed. Every other
     character stands for itself.
   - **Ranges.** Scan the tokens left to right. If the current token is
     followed by an **unescaped** `-` token and then by one more token, the
     three tokens form a range X-Y that stands for all characters from X to
     Y in ASCII order, and the scan continues after Y. If X comes after Y in
     ASCII order, the set is malformed. Otherwise the current token stands
     for itself and the scan moves on by one token. So a `-` at the very
     start or end of a set is a literal `-`, `\-` is always a literal `-`,
     and `a-c-e` means `a`, `b`, `c`, `-`, `e`.
   - The result is a **list** of characters in this order. It may contain
     repeats. An empty argument is an empty list.
2. **Translate.** Let SET1 be the list x1..xn and SET2 be y1..ym (m ≥ 1).
   Character xi maps to yi, or to ym if i > m (the last character of SET2
   is repeated as needed; extra characters of SET2 are ignored). If a
   character occurs several times in SET1, its **last** occurrence decides
   its mapping. Every input character that is in SET1 is replaced by its
   mapping; all other characters are copied unchanged.
3. **Delete.** With `-d`, every input character that is in SET1 is removed.
4. **Squeeze.** With `-s`, after translating or deleting, every run of two
   or more **identical** characters that are in the squeeze set is replaced
   by a single one of them. The squeeze set is SET1 when `-s` is used with
   one set, and SET2 when it is used with two. Runs of characters that are
   not in the squeeze set are kept.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.
`' \n'` stands for one argument consisting of a space, a backslash and the
letter `n` (three characters); `'\t'` and `' '` are likewise single
arguments.

### Example 1: translate

- cmd: `trx a-z A-Z` with stdin `hello, world\n` gives stdout
  `HELLO, WORLD\n` and exit `0`.
- cmd: `trx abc xy` with stdin `aabbcc-cab\n` gives stdout `xxyyyy-yxy\n`
  and exit `0` (`c` maps to `y`, the last character of SET2).
- cmd: `trx aa xy` with stdin `abcabc\n` gives stdout `ybcybc\n` and exit
  `0` (the last occurrence of `a` maps it to `y`).

### Example 2: delete and squeeze

- cmd: `trx -d aeiou` with stdin `programming language\n` gives stdout
  `prgrmmng lngg\n` and exit `0`.
- cmd: `trx -s ' \n'` with stdin `a   b\n\n\nc  d\n` gives stdout
  `a b\nc d\n` and exit `0`.
- cmd: `trx -s abc xy` with stdin `aabbcc-cab\n` gives stdout `xy-yxy\n`
  and exit `0` (translated to `xxyyyy-yxy`, then runs of `x` and `y` are
  squeezed).
- cmd: `trx -d -s 0-9 a-z` with stdin `aa1a2bb33b\n` gives stdout `ab\n`
  and exit `0`.

### Example 3: dashes and escapes

- cmd: `trx -- -d x` with stdin `a-d\n` gives stdout `axx\n` and exit `0`
  (SET1 is `-` and `d`).
- cmd: `trx a-c-e 0-4` with stdin `a-c-e!\n` gives stdout `03234!\n` and
  exit `0` (SET1 is `a b c - e`).
- cmd: `trx '\t' ' '` with stdin `x\ty\n` (a real tab) gives stdout
  `x y\n` and exit `0`.

### Example 4: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `trx a` (translate needs two sets)
- cmd: `trx -d` (no set)
- cmd: `trx -d a b`
- cmd: `trx z-a x` (reversed range)
- cmd: `trx -x a b` (unknown option)
- cmd: `trx 'a\q' b` (bad escape; the argument is `a`, backslash, `q`)
- cmd: `trx a ""` (empty SET2 when translating)

## Not required

- Complement (`-c`), character classes such as `[:alpha:]`, `[=e=]`,
  `[x*n]`, or octal escapes.
- Non-ASCII input or sets.
- Combined options such as `-ds` (they are usage errors by the rules above
  and are not tested).
- Any particular stderr wording.
