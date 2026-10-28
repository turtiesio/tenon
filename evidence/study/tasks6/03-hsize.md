# Task 03: hsize (human-readable byte sizes)

## Goal

Write a command-line tool that turns byte counts into short human-readable
sizes such as `1.5 KiB` or `117.7 MiB`. It uses binary units (powers of
1024) by default and decimal units (powers of 1000) with `-s`, rounds to a
chosen number of decimal places with an exactly specified rule, and moves up
to the next unit when rounding reaches it. Sizes come from the command line
or, if none are given there, from stdin, one per line.

## Interface

```
hsize [-s] [-p N] [SIZE...]
```

- **Arguments** are examined left to right. Options and sizes may be mixed
  in any order.
  - `-s`: use decimal (SI) units. Repeating it changes nothing.
  - `-p N`: the number of decimal places. The value is the **next**
    argument and must be exactly `0`, `1` or `2`. Default `1`. If `-p`
    appears more than once, the last value wins.
  - An argument matching `[0-9]{1,16}` is a SIZE in bytes (leading zeros
    allowed; `007` is 7).
  - Anything else (including a negative number, `-p` without a following
    argument, a bad `-p` value, a size with 17 or more digits, and combined
    forms such as `-sp`) is a **usage error**: print a message to stderr,
    print **nothing** on stdout, do not read stdin, and exit `2`.
- **Sizes from stdin.** If no SIZE argument is given, read stdin. It is
  ASCII text. Lines are split on `\n`. If the input ends with `\n`, there is
  no extra empty line after it. A final line without `\n` is still a line.
  One trailing `\r` is removed from each line. Each line must match
  `[0-9]{1,16}` exactly (no spaces); otherwise it is a **bad line**. If SIZE
  arguments are given, stdin is not read.
- **stdout.** One line per size, in input order (rule 4).
- **Exit codes.** `0` success, `1` if stdin had at least one bad line, `2`
  usage error.

## Rules

1. **Units.** The base B is 1024 by default and 1000 with `-s`. The units
   are, for k = 1 to 5:

   | k | binary (B = 1024) | decimal (B = 1000) |
   |---|---|---|
   | 1 | `KiB` | `kB` |
   | 2 | `MiB` | `MB` |
   | 3 | `GiB` | `GB` |
   | 4 | `TiB` | `TB` |
   | 5 | `PiB` | `PB` |

   There is no unit above k = 5.
2. **Small sizes.** A size V < B is printed as the plain integer, a space
   and `B`, with no decimal places, for example `1023 B` or `0 B`.
3. **Larger sizes.** For V ≥ B:
   1. Let k be the largest value from 1 to 5 with V ≥ B^k.
   2. Let S = 10^P (P is the number of decimal places). Let R be V × S / B^k
      rounded to the nearest integer, with an exact half rounded **up**. In
      integer arithmetic: R = (2 × V × S + B^k) div (2 × B^k).
   3. If R ≥ B × S and k < 5, increase k by 1 and go back to step 2 (so
      rounding that reaches 1024.0 KiB is printed as 1.0 MiB instead).
   4. Print R div S, then, if P > 0, a `.` and R mod S written with exactly
      P digits (with leading zeros), then a space and the unit for k.
4. **Output lines.** Each size gives one line ending with `\n`. A bad stdin
   line gives the line `?` and the run continues with the next line.
5. **Limits.** Sizes are below 10^16, so 2 × V × S fits in a signed 64-bit
   integer. At most 10000 stdin lines.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: binary units

cmd: `hsize 0 1023 1024 1536 1048575 123456789 9999999999999999`

stdout:
```
0 B
1023 B
1.0 KiB
1.5 KiB
1.0 MiB
117.7 MiB
8.9 PiB
```
exit: `0`

(1048575 / 1024 = 1023.999..., which rounds to 1024.0 KiB, so it moves up
to MiB: 1048575 / 1048576 rounds to 1.0.)

### Example 2: decimal units, two places

cmd: `hsize -s -p 2 999 1000 999499 999995 1234567 9999999999999999`

stdout:
```
999 B
1.00 kB
999.50 kB
1.00 MB
1.23 MB
10.00 PB
```
exit: `0`

(999499 / 1000 = 999.499, and 99949.9 rounds to 99950. There is no unit
above PB, so the last size stays at `10.00 PB`.)

### Example 3: no decimal places, halves round up

cmd: `hsize 1535 -p 0 1536 2560`

stdout:
```
1 KiB
2 KiB
3 KiB
```
exit: `0`

(The options apply to every size, wherever they appear.)

### Example 4: sizes from stdin

cmd: `hsize -s`

stdin: `4096\nabc\n\n0012\r\n-5` (no final newline)

stdout:
```
4.1 kB
?
?
12 B
?
```
exit: `1`

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `hsize -p 3 10`
- cmd: `hsize -p`
- cmd: `hsize -5`
- cmd: `hsize 10000000000000000` (17 digits)
- cmd: `hsize 1.5`

## Not required

- Parsing human-readable sizes back into bytes.
- Units above PB/PiB, more than 2 decimal places, negative sizes.
- Any particular stderr wording.
