# Task 03: datecalc (calendar date calculator)

## Goal

Write a command-line date calculator for the proleptic Gregorian calendar. It
has four subcommands (weekday, add days, difference in days, add months) and
an output-format option. All arithmetic is on whole days, with no time of day
and no time zones. Invalid dates and usage errors are told apart by exit code.

## Interface

```
datecalc [-F FMT] COMMAND ARG...
```

- **Options** come **before** COMMAND. Before COMMAND, every argument that
  starts with `-` is an option. The only option is `-F FMT`, given as two
  separate arguments. The argument after `-F` is always taken as FMT, even if
  it starts with `-` or is empty. If `-F` is given more than once, the last
  one wins.
- **COMMAND** is the first argument that is not an option or an option's
  value. All arguments after COMMAND are positional, so `-3` there is a
  number, not an option.

| Command | Output |
|---|---|
| `weekday DATE` | The English weekday name: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`, `Saturday` or `Sunday`. |
| `add DATE N` | The date N days after DATE (N may be negative), formatted with FMT. |
| `diff DATE1 DATE2` | The number of days from DATE1 to DATE2 (DATE2 minus DATE1), as a decimal integer with a leading `-` if negative. |
| `addmonths DATE N` | DATE moved by N calendar months (N may be negative), formatted with FMT. If the day does not exist in the target month, the last day of that month is used. |

- **stdout.** Exactly one line, ending with `\n`, on success. Nothing on
  error.
- **stderr.** Error messages. Not tested.
- **Exit codes.**
  - `0`: success.
  - `1`: a DATE argument is invalid, or the result is outside the supported
    range.
  - `2`: usage error.

## Rules

1. **DATE** must match `[0-9]{4}-[0-9]{2}-[0-9]{2}` exactly, be a real date
   in the proleptic Gregorian calendar, and lie in `0001-01-01` ..
   `9999-12-31`. Leap years: divisible by 4, except years divisible by 100,
   except years divisible by 400. `0000-01-01`, `2023-02-29`, `2024-13-01`,
   `2024-1-05` and ` 2024-01-05` are all invalid.
2. **N** must match `-?[0-9]{1,7}`. Otherwise it is a usage error. `+5` is a
   usage error.
3. **Range.** A result date outside `0001-01-01` .. `9999-12-31` is an error
   with exit `1`.
4. **addmonths.** Moving `Y-M-D` by N months gives the year and month that are
   N months away (for example, 2024-03 moved by -13 is 2023-02). The day is
   `min(D, number of days in that month)`.
5. **FMT.** It is used only by `add` and `addmonths`, and is accepted but
   ignored by `weekday` and `diff`. The default is `%Y-%m-%d`. FMT is copied
   to the output, except that these two-character directives are replaced:

   | Directive | Replacement |
   |---|---|
   | `%Y` | year, 4 digits, zero-padded |
   | `%m` | month, 2 digits, zero-padded |
   | `%d` | day of month, 2 digits, zero-padded |
   | `%j` | day of the year (1–366), 3 digits, zero-padded |
   | `%a` | weekday abbreviation: `Mon` `Tue` `Wed` `Thu` `Fri` `Sat` `Sun` |
   | `%b` | month abbreviation: `Jan` `Feb` `Mar` `Apr` `May` `Jun` `Jul` `Aug` `Sep` `Oct` `Nov` `Dec` |
   | `%%` | a single `%` |

   A `%` followed by any other character, or a `%` at the end of FMT, is a
   usage error. FMT is ASCII.
6. **Usage errors (exit 2).** No COMMAND; an unknown COMMAND (names are
   lowercase and case-sensitive); the wrong number of arguments for the
   command; a malformed N; an unknown option; `-F` without a following
   argument; an invalid FMT (rule 5), even for `weekday` and `diff`.
7. **Order of checks.** All usage checks come first. Only if there is no usage
   error are dates checked (exit 1), and then the result range (exit 1).

## Examples

Every output line shown ends with `\n`. In `cmd`, arguments are separated by
spaces, and an argument containing spaces is shown in double quotes (the
quotes are not part of it).

### Example 1: weekday

cmd: `datecalc weekday 2024-02-29`

stdout:
```
Thursday
```
exit: `0`

### Example 2: adding days, difference across a leap day

- cmd: `datecalc add 2023-12-25 10` gives stdout `2024-01-04` and exit `0`.
- cmd: `datecalc diff 2024-03-01 2023-03-01` gives stdout `-366` and exit
  `0`.
- cmd: `datecalc diff 0001-01-01 9999-12-31` gives stdout `3652058` and exit
  `0`.

### Example 3: adding months with clamping

- cmd: `datecalc addmonths 2024-01-31 1` gives stdout `2024-02-29` and exit
  `0`.
- cmd: `datecalc addmonths 2024-03-31 -13` gives stdout `2023-02-28` and exit
  `0`.

### Example 4: a custom format

cmd: `datecalc -F "%a %d %b %Y (day %j) 100%%" add 2024-12-31 1`

(The argv is the five arguments `-F`, `%a %d %b %Y (day %j) 100%%`, `add`,
`2024-12-31` and `1`.)

stdout:
```
Wed 01 Jan 2025 (day 001) 100%
```
exit: `0`

### Example 5: errors

- cmd: `datecalc weekday 2023-02-29` gives stdout (empty) and exit `1`.
- cmd: `datecalc add 9999-12-31 1` gives stdout (empty) and exit `1`.
- cmd: `datecalc add 2024-1-01 3` gives stdout (empty) and exit `1`.
- cmd: `datecalc add 2024-01-01` gives stdout (empty) and exit `2`.
- cmd: `datecalc add 2023-02-30 x` gives stdout (empty) and exit `2` (usage
  is checked before the date).
- cmd: `datecalc -F %q add 2024-01-01 1` gives stdout (empty) and exit `2`.
- cmd: `datecalc frobnicate 2024-01-01` gives stdout (empty) and exit `2`.

## Not required

- Times of day, time zones, the Julian calendar, years outside 1..9999.
- Locale-specific names.
- Options after COMMAND, long options, `--`.
- Any particular stderr wording.
