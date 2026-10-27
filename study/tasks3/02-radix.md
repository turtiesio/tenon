# Task 02: radix (integer base converter)

## Goal

Write a command-line tool that converts signed integers between number bases
2 to 36. Each value given on the command line is converted and printed on its
own line. Options select the input base, the output base, upper-case digits,
zero padding to a minimum number of digits, and digit grouping with `_`.
Usage errors stop the program before any output. Invalid values are reported
but do not stop the other values from being converted.

## Interface

```
radix [-f FROM] [-t TO] [-w WIDTH] [-g GROUP] [-u] VALUE...
```

- **Arguments** are processed left to right. An argument that is exactly
  `-f`, `-t`, `-w`, `-g` or `-u` is an option, wherever it appears. `-f`,
  `-t`, `-w` and `-g` take the **next** argument as their value, whatever it
  looks like. Every other argument is a VALUE (so `-ff`, `-5` and `--` are
  VALUEs). If an option is given more than once, the last one wins.
  - `-f FROM`: input base. Default `10`.
  - `-t TO`: output base. Default `10`.
  - `-w WIDTH`: minimum number of digits (rule 4). Default: no padding.
  - `-g GROUP`: group size (rule 5). Default: no grouping.
  - `-u`: print the digits `a`-`z` as upper case `A`-`Z`.
- **Option values.** FROM and TO must match `[0-9]{1,2}` with a value from 2
  to 36. WIDTH and GROUP must match `[0-9]{1,2}` with a value from 1 to 64.
- **Usage errors (exit 2).** A malformed or out-of-range option value; an
  option without a following argument; no VALUE at all. On a usage error,
  print a message to stderr and print **nothing** on stdout. All usage checks
  happen before any VALUE is converted.
- **stdout.** One line per **valid** VALUE, in argument order, ending with
  `\n`.
- **Exit codes.** `0` if every VALUE was valid, `1` if at least one VALUE was
  invalid (the valid ones are still printed), `2` usage error.

## Rules

1. **Digits.** The digit characters are `0`-`9` (values 0-9) and the letters
   `a`-`z` (values 10-35). On input, letters are case-insensitive: `F` and
   `f` are both 15.
2. **VALUE.** A VALUE is an optional `-` followed by **one or more** digit
   characters, each with a value smaller than FROM. Leading zeros are
   allowed. `+` is not allowed. Anything else is invalid: print a message to
   stderr, print nothing on stdout for this VALUE, and go on with the next.
3. **Range.** The absolute value of a VALUE must be at most
   9223372036854775807 (2^63 − 1). A VALUE outside this range is invalid
   (rule 2 applies). `-0` and `-000` have the value 0.
4. **Output digits.** The absolute value is written in base TO with lower-case
   letters (or upper case with `-u`), with no leading zeros; zero is written
   `0`. If WIDTH is given and the digit string is shorter than WIDTH, it is
   padded on the left with `0` to exactly WIDTH digits.
5. **Grouping.** If GROUP is given, the digit string (after padding) is split
   into groups of GROUP digits counted **from the right**, joined with `_`.
   The leftmost group may be shorter. A string of at most GROUP digits gets
   no `_`.
6. **Sign.** A negative value is printed with a leading `-` before the digits
   (and before any padding or groups). Zero is never negative.

## Examples

Each output line shown ends with `\n`. In `cmd`, arguments are separated by
spaces.

### Example 1: decimal to hexadecimal

cmd: `radix -t 16 255 -10 0`

stdout:
```
ff
-a
0
```
exit: `0`

### Example 2: grouping, padding and upper case

- cmd: `radix -f 2 -g 3 1111101000` gives stdout `1_000\n` and exit `0`.
- cmd: `radix -f 36 -t 16 -u zz` gives stdout `50F\n` and exit `0`.
- cmd: `radix -t 2 -w 8 -g 4 5 -3` gives stdout `0000_0101\n-0000_0011\n`
  and exit `0`.

### Example 3: options after values, last option wins

cmd: `radix 1000000 -g 3 -t 8 -t 10 9223372036854775807`

stdout:
```
1_000_000
9_223_372_036_854_775_807
```
exit: `0`

### Example 4: some invalid values

cmd: `radix -t 16 12 1x -0 9223372036854775807 9223372036854775808 - +5`

stdout:
```
c
0
7fffffffffffffff
```
exit: `1`

(`1x` has a digit that is not valid in base 10, `9223372036854775808` is out
of range, `-` has no digits, and `+5` has a `+`.)

### Example 5: usage errors

- cmd: `radix` gives stdout (empty) and exit `2`.
- cmd: `radix -t 37 5` gives stdout (empty) and exit `2`.
- cmd: `radix -t 1 5` gives stdout (empty) and exit `2`.
- cmd: `radix -g 0 5` gives stdout (empty) and exit `2`.
- cmd: `radix 5 -f` gives stdout (empty) and exit `2`.
- cmd: `radix -u` gives stdout (empty) and exit `2`.
- cmd: `radix 12 -t x` gives stdout (empty) and exit `2` (usage errors are
  found before `12` is converted).

## Not required

- Fractions, floating point, or prefixes such as `0x` and `0b`.
- Values beyond the stated range.
- Separators such as `_` in the input.
- Any particular stderr wording.
