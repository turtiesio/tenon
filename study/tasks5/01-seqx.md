# Task 01: seqx (print an arithmetic sequence of integers)

## Goal

Write a command-line tool in the style of `seq`. It prints the integers from
FIRST to LAST in steps of STEP, joined by a separator. Options choose the
separator, pad all numbers to equal width with zeros, and limit how many
numbers are printed. Malformed command lines are usage errors.

## Interface

```
seqx [-s SEP] [-w] [-n COUNT] FIRST [STEP] LAST
```

- **Arguments** are processed left to right. Options and numbers may be
  mixed in any order. Each option is a separate argument.
  - `-s SEP`: the **next** argument is the separator, used literally (it
    may be empty, contain spaces, or start with `-`). Default: a newline.
  - `-w`: pad numbers with zeros to equal width (rule 4).
  - `-n COUNT`: print at most COUNT numbers. The **next** argument must
    match `[0-9]{1,9}` (leading zeros allowed; `0` is allowed).
  - Options may be repeated. For `-s` and `-n`, the last value wins.
  - Every other argument is a **number argument**, even if it starts with
    `-` (so `-5` is the number minus five, and `-x` is a malformed number).
- **Number arguments.** There must be exactly 2 (FIRST LAST, with STEP = 1)
  or exactly 3 (FIRST STEP LAST). Each must match `-?[0-9]{1,18}` (leading
  zeros allowed; no `+`, no spaces). STEP must not be zero (`0`, `-0`,
  `000` are all zero).
- **Usage errors (exit 2).** Wrong number of number arguments, a malformed
  number, a zero STEP, `-s` or `-n` as the last argument (no value), or a
  malformed `-n` value. Print a message to stderr, print **nothing** on
  stdout.
- **stdin** is not read.
- **Exit codes.** `0` success (also when nothing is printed), `2` usage
  error.

## Rules

1. **The sequence.** The values are FIRST, FIRST+STEP, FIRST+2·STEP, ...
   With STEP > 0 the sequence contains every such value that is ≤ LAST;
   with STEP < 0 every such value that is ≥ LAST. So `seqx 5 1` and
   `seqx 1 -1 5` print nothing.
2. **Limit.** With `-n COUNT`, only the first COUNT values of the sequence
   are printed. `-n 0` prints nothing.
3. **Number format.** A value is written in decimal without leading zeros,
   with a leading `-` if it is negative. Zero is `0` (never `-0`).
4. **Width.** With `-w`, let W be the length of the longest formatted
   value among the values being printed (after the `-n` limit). Every value
   shorter than W is padded with zeros to length W: a non-negative value
   gets the zeros at the front, a negative value gets them right after the
   `-`. For example, with W = 3: `7` becomes `007`, `-4` becomes `-04`, and
   `-12` stays `-12`.
5. **Output.** If at least one value is printed, the output is the
   formatted values joined by SEP, followed by a single `\n`. (With the
   default separator this is one value per line.) If no value is printed,
   the output is empty.
6. **Limits.** Values stay within ±10^18 in tests, and at most 100000
   values are printed.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces;
`" "` stands for one argument consisting of a single space, and `""` for an
empty argument.

### Example 1: the default

cmd: `seqx 1 5`

stdout:
```
1
2
3
4
5
```
exit: `0`

### Example 2: a negative step and a separator

cmd: `seqx -s , 10 -3 1`

stdout:
```
10,7,4,1
```
exit: `0`

(The next value, -2, is below LAST, so it is not printed.)

### Example 3: equal width

- cmd: `seqx -w -s " " -10 4 3` gives stdout `-10 -06 -02 002\n` and exit
  `0`.
- cmd: `seqx 3 -1 -2 -w` gives stdout `03\n02\n01\n00\n-1\n-2\n` and exit
  `0`.

### Example 4: limit, empty separator, empty output

- cmd: `seqx -s "" -n 4 7 1000` gives stdout `78910\n` and exit `0`.
- cmd: `seqx 5 1` gives stdout (empty) and exit `0`.
- cmd: `seqx -n 0 1 5` gives stdout (empty) and exit `0`.

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `seqx 1`
- cmd: `seqx 1 0 5`
- cmd: `seqx 1 x`
- cmd: `seqx 1 +2`
- cmd: `seqx 1 2 3 4`
- cmd: `seqx -n -1 1 5`
- cmd: `seqx 1 5 -s`

## Not required

- Fractional numbers, `-f` format strings, or `--` handling.
- Values beyond ±10^18.
- Any particular stderr wording.
