# Task 02: ldiff (line diff with a fixed LCS walk)

## Goal

Write a command-line tool that compares two text files line by line and
prints the whole of the first file transformed into the second: every line
is marked as common, deleted or inserted. The edit script is defined by a
specific longest-common-subsequence (LCS) walk, so there is exactly one
correct output. Options control case-insensitive and trailing-whitespace
insensitive comparison, a summary-only mode and a quiet mode.

## Interface

```
ldiff [-i] [-b] [-q | -s] FILE1 FILE2
```

- **Arguments.** Options may appear anywhere among the arguments. Every
  argument that starts with `-` is an option. Each option may be repeated
  (same effect as once). Exactly two non-option arguments are required.

| Option | Meaning |
|---|---|
| `-i` | Compare lines ignoring ASCII case (`A`–`Z` equal `a`–`z`). |
| `-b` | Compare lines ignoring trailing spaces and tabs. |
| `-q` | Print nothing. Only the exit code reports the result. |
| `-s` | Print only the summary line (format below). |

- `-q` and `-s` together are a usage error.
- **stdout.** The diff listing, or the summary line, or nothing (see below).
- **stderr.** Error messages. Not tested.
- **Exit codes.**
  - `0`: the files are equal under the chosen comparison (no inserted or
    deleted lines).
  - `1`: the files differ.
  - `2`: usage error (unknown option, `-q` with `-s`, wrong number of file
    arguments), or a file cannot be read. Nothing is printed on stdout.

## Rules

1. **Lines.** Each file is split on `\n`. A final line without `\n` is still a
   line, and a file that ends with `\n` has no extra empty line after it. An
   empty file has zero lines. `\r` is an ordinary character (`-b` does **not**
   remove it). Files are UTF-8, and lines are compared as byte strings.
2. **Comparison key.** Two lines are equal if their keys are equal. The key of
   a line is the line itself, with trailing spaces and tabs removed if `-b` is
   given, and then ASCII-lowercased if `-i` is given.
3. **LCS table.** Let `A` (length `n`) and `B` (length `m`) be the line lists
   of FILE1 and FILE2, indexed from 0. Define `L[i][j]` as the length of the
   longest common subsequence of the suffixes `A[i..]` and `B[j..]` (using the
   comparison keys), with `L[n][j] = L[i][m] = 0`.
4. **The walk.** Start with `i = 0`, `j = 0` and repeat:
   - If `i == n` and `j == m`: stop.
   - If `i == n`: **insert** `B[j]`, then `j += 1`.
   - If `j == m`: **delete** `A[i]`, then `i += 1`.
   - If `A[i]` equals `B[j]`: **common** `A[i]`, then `i += 1` and `j += 1`.
   - Else if `L[i+1][j] >= L[i][j+1]`: **delete** `A[i]`, then `i += 1`.
   - Else: **insert** `B[j]`, then `j += 1`.
5. **Listing (default output).** One output line per step of the walk, in
   order:
   - common: two spaces, then the line **as it appears in FILE1**;
   - delete: `- ` (minus, space), then the FILE1 line;
   - insert: `+ ` (plus, space), then the FILE2 line.

   Each output line ends with `\n`. The original line text is printed, not the
   comparison key. If both files have zero lines, nothing is printed.
6. **Summary (`-s`).** A single line `+<I> -<D> =<C>`: the number of inserted,
   deleted and common lines.
7. **Exit code** is `1` if `I + D > 0`, else `0`, in all three output modes.
8. **Limits.** Each file has at most 2000 lines, and each line is at most 1000
   bytes.

## Examples

Every line shown ends with `\n`, unless stated otherwise. In `cmd`, arguments
are separated by spaces.

### Example 1: a replaced line and an appended line

`a.txt`:
```
apple
banana
cherry
date
```
`b.txt`:
```
apple
blueberry
cherry
date
elder
```
cmd: `ldiff a.txt b.txt`

stdout:
```
  apple
- banana
+ blueberry
  cherry
  date
+ elder
```
exit: `1`

(At `banana`/`blueberry`, `L[2][1] = 2` and `L[1][2] = 2`, so the delete
comes first.)

### Example 2: case-insensitive summary

`x.txt`:
```
Hello
World
```
`y.txt`:
```
hello
world
!
```
cmd: `ldiff -i -s x.txt y.txt`

stdout:
```
+1 -0 =2
```
exit: `1`

### Example 3: trailing whitespace and a missing final newline

`p.txt` contains the 6 bytes `a␣␣\nb\n`, where `␣` is a space (the first
line is `a` followed by two spaces). `q.txt` contains the 3 bytes `a\nb` (no
final newline).

- cmd: `ldiff -b -q p.txt q.txt` gives stdout (empty) and exit `0`.
- cmd: `ldiff -s p.txt q.txt` gives stdout `+1 -1 =1` (one line) and exit `1`.

### Example 4: an empty file

`empty.txt` is zero bytes. `one.txt` contains `x\n`.

cmd: `ldiff empty.txt one.txt`

stdout:
```
+ x
```
exit: `1`

### Example 5: usage errors

The working directory contains `a.txt` and `b.txt` from Example 1.

- cmd: `ldiff a.txt` gives stdout (empty) and exit `2`.
- cmd: `ldiff -q -s a.txt b.txt` gives stdout (empty) and exit `2`.
- cmd: `ldiff -u a.txt b.txt` gives stdout (empty) and exit `2`.
- cmd: `ldiff a.txt missing.txt` gives stdout (empty) and exit `2`.

## Not required

- Unified or context diff formats, hunks, line numbers.
- Reading from standard input (`-`), directories, binary-file detection.
- Case folding beyond ASCII.
- Any particular stderr wording.
