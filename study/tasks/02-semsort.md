# Task 02: semsort (semantic-version sorter)

## Goal

Write a command-line tool that reads version strings, one per line, validates
them against a precisely defined Semantic Versioning grammar, and prints the
valid versions sorted by SemVer precedence. Options select reverse order,
de-duplication by precedence, and exclusion of pre-releases. Invalid lines are
reported on stderr and skipped, and they make the exit code 1.

## Interface

```
semsort [-r] [-u] [--no-pre] [FILE]
```

- **Input.** If `FILE` is given, read it. Otherwise read standard input. At
  most one `FILE` may be given. The input is UTF-8 text with lines separated by
  `\n`, and the last line may lack a trailing `\n`.
- **Options.** Options may appear in any order, before or after `FILE`. Giving
  the same option twice is the same as giving it once.

| Option | Meaning |
|---|---|
| `-r` | Output in reverse order: exactly the reverse of the list that would otherwise be printed. |
| `-u` | Unique: among versions of **equal precedence**, keep only the one that appears first in the input. |
| `--no-pre` | Drop every valid version that has a pre-release part. |

- **stdout.** The selected versions, one per line, each followed by `\n`.
  Each version is printed exactly as it appeared in the input, after trimming
  (see rule 1).
- **stderr.** One message per invalid line, for example
  `invalid version at line 3: 1.2`. The wording is not tested.
- **Exit codes.**
  - `0`: success, with no invalid lines.
  - `1`: at least one invalid line (the valid lines are still printed), or
    `FILE` cannot be read (nothing printed).
  - `2`: usage error: an unknown option (any other argument starting with `-`,
    including `-` itself) or more than one `FILE`. Nothing printed.

## Rules

1. **Trimming and blank lines.** From each line, remove a trailing `\r` if
   present, then remove leading and trailing spaces and tabs. If the result is
   empty, the line is blank: it is skipped silently and is never an error.
   Line numbers in messages count every physical line, starting at 1.
2. **Grammar.** A valid version matches all of the following (and nothing else
   is valid, so for example a leading `v` makes the line invalid):

   ```
   version    := core [ "-" prerelease ] [ "+" build ]
   core       := num "." num "." num
   num        := "0" | [1-9][0-9]{0,8}            (no leading zeros, at most 9 digits)
   prerelease := pid ( "." pid )*
   pid        := num | alnum
   alnum      := [0-9A-Za-z-]+ containing at least one character that is not a digit
   build      := bid ( "." bid )*
   bid        := [0-9A-Za-z-]+                    (leading zeros allowed)
   ```

   A pre-release identifier made only of digits must be a valid `num`. So
   `rc.01` is invalid, and a 10-digit numeric identifier is invalid. Empty
   identifiers (`1.0.0-a..b`, `1.0.0-`, `1.0.0+`) are invalid.
3. **Precedence** (SemVer 2.0.0):
   - Compare MAJOR, MINOR and PATCH numerically, in that order.
   - If the cores are equal, a version **without** a pre-release has higher
     precedence than one with a pre-release.
   - Two pre-releases are compared identifier by identifier, from left to
     right:
     - numeric identifiers are compared numerically;
     - alphanumeric identifiers are compared in ASCII byte order;
     - a numeric identifier has lower precedence than an alphanumeric one.
   - If all compared identifiers are equal, the version with more identifiers
     has higher precedence.
   - Build metadata is **ignored** for precedence. So `1.0.0+a` and `1.0.0+b`
     have equal precedence.
4. **Ordering.** Sort the valid versions in ascending precedence with a
   **stable** sort: versions of equal precedence keep their input order. Then
   apply the options in this order:
   1. `--no-pre`
   2. `-u` (on the ascending list, keep the first of each equal-precedence
      group)
   3. `-r` (reverse the whole list)
5. **Empty result.** If there is nothing to print, stdout is empty. The exit
   code still follows the rules above.
6. **Limits.** Input is at most 100000 lines.

## Examples

Every line shown ends with `\n`.

### Example 1: SemVer precedence

cmd: `semsort`

stdin:
```
1.0.0
1.0.0-alpha
1.0.0-alpha.1
1.0.0-beta.11
1.0.0-beta.2
1.0.0-rc.1
0.9.12
1.0.0-alpha.beta
1.0.0-beta
```
stdout:
```
0.9.12
1.0.0-alpha
1.0.0-alpha.1
1.0.0-alpha.beta
1.0.0-beta
1.0.0-beta.2
1.0.0-beta.11
1.0.0-rc.1
1.0.0
```
exit: `0`

### Example 2: unique and reverse; build metadata ignored

cmd: `semsort -r -u`

stdin:
```
2.0.0+build.1
1.10.0
1.2.0
2.0.0+build.2
1.2.0
```
stdout:
```
2.0.0+build.1
1.10.0
1.2.0
```
exit: `0`

### Example 3: invalid lines are skipped

cmd: `semsort`

stdin (line 5 is empty):
```
1.2.3
01.2.3
1.2
v1.0.0

1.0.0-rc.01
1.0.0-rc.1+001
```
stdout:
```
1.0.0-rc.1+001
1.2.3
```
exit: `1` (stderr reports lines 2, 3, 4 and 6)

### Example 4: no pre-releases, from a file

Working directory contains `versions.txt`:
```
1.0.0-rc.1
  1.0.0
0.1.0+meta
```
cmd: `semsort --no-pre versions.txt`

stdout:
```
0.1.0+meta
1.0.0
```
exit: `0`

### Example 5: usage errors and a missing file

- cmd: `semsort a.txt b.txt` gives stdout (empty) and exit `2`.
- cmd: `semsort --sort` gives stdout (empty) and exit `2`.
- cmd: `semsort nope.txt` (the file does not exist) gives stdout (empty) and
  exit `1`.

## Not required

- Long forms (`--reverse` and so on), `--help` and `--version`.
- `--` as an end-of-options marker.
- Numeric parts longer than 9 digits. They are simply invalid.
- Any particular stderr wording.
