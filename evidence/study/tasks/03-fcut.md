# Task 03: fcut (field selector CLI)

## Goal

Write a command-line tool, similar to `cut -f`, that splits each input line on
a one-character delimiter and prints selected fields. Unlike `cut`, fields are
printed **in the order the field list names them**, and repetition is allowed.
The tool must validate its options strictly, using exit code 2 for usage
errors, and must keep going past unreadable files, using exit code 1.

## Interface

```
fcut -f LIST [-d DELIM] [-s] [--output-delimiter=STR] [FILE...]
```

- **Inputs.** `FILE`s are read in order, and `-` means standard input. If no
  `FILE` is given, standard input is read. Input is UTF-8 text.
- **Options.** Options may appear anywhere among the file names. The argument
  `--` ends option parsing. Before `--`, any argument that starts with `-` and
  is not exactly `-` is an option. When an option is given more than once, the
  last one wins.

| Option | Meaning |
|---|---|
| `-f LIST` or `-fLIST` | **Required.** The fields to print (grammar below). In the separate form, the next argument is always taken as LIST, even if it starts with `-`. |
| `-d DELIM` or `-dDELIM` | The input delimiter: exactly one ASCII character. Default: TAB (`\t`). In the separate form, the next argument is always taken as DELIM. |
| `-s` or `--only-delimited` | Do not print lines that contain no delimiter character. |
| `--output-delimiter=STR` | The string placed between output fields. It may be empty or several characters long. Default: the input delimiter. |

- **LIST grammar.** One or more elements separated by commas, with no spaces
  and no empty elements:

  ```
  element := N | N "-" M | N "-" | "-" M
  N, M    := decimal integer 1..1000000, digits only
  ```

  - `N` is field N.
  - `N-M` is fields N to M inclusive, ascending. It requires N ≤ M.
  - `N-` is field N through the last field of the line.
  - `-M` is the same as `1-M`.
  - A lone `-` is invalid.

- **stdout.** One output line per printed input line, each terminated with
  `\n`.
- **stderr.** Error messages. Not tested.
- **Exit codes.**
  - `0`: success.
  - `1`: at least one `FILE` could not be read. It is skipped, the others are
    processed, and the output for them is printed.
  - `2`: usage error. Nothing is printed and no input is read.

## Rules

1. **Lines.** The input is split on `\n`. A final line without a trailing `\n`
   is still a line, and its output still ends with `\n`. An input that ends with
   `\n` has no extra empty line after it. `\r` has no special meaning: it is an
   ordinary character.
2. **Fields.** Split each line on every occurrence of the delimiter. N
   delimiters give N+1 fields, and fields may be empty. For example, with `,`
   the line `a,,b,` has the fields `a`, ``, `b`, ``. Fields are numbered from 1.
3. **Selection.** Go through the LIST elements in order. For each element,
   take the fields it names **that exist in this line**, in ascending order,
   and skip field numbers beyond the line's field count. Join all taken fields
   with the output delimiter. If no field is taken, the output line is empty
   (just `\n`).
4. **Lines without the delimiter.** A line that contains no delimiter
   character is printed **unchanged**, ignoring LIST, unless `-s` is given. With
   `-s` it is not printed at all. An empty line contains no delimiter.
5. **Usage errors (exit 2).** These are:
   - `-f` is missing;
   - LIST is empty or malformed: an empty element, `0`, a non-digit, `N-M` with
     N > M, a number > 1000000, or a lone `-`;
   - DELIM is not exactly one ASCII character (empty is an error too);
   - an option is missing its value;
   - `--output-delimiter` without `=`;
   - any unknown option.
6. **Unreadable file.** Write a message to stderr, continue with the next
   input, and exit 1 at the end.
7. **Limits.** Input is at most 10 MB, and a line is at most 100000 bytes.

## Examples

Every line shown ends with `\n`. `<TAB>` means a tab character. In `cmd`,
arguments are separated by spaces, and quoted arguments are shown with
shell-style double quotes.

### Example 1: field order, a missing field, a line without the delimiter

cmd: `fcut -f 3,1 -d ,`

stdin:
```
a,b,c
d,e
nodelim
```
stdout:
```
c,a
d
nodelim
```
exit: `0`

### Example 2: open range, default TAB delimiter, `-s`

cmd: `fcut -f2- -s`

stdin (the third line is empty):
```
x<TAB>y<TAB>z
plain

```
stdout:
```
y<TAB>z
```
exit: `0`

### Example 3: `-M` range, repetition, output delimiter

cmd: `fcut -f -2,2 -d : "--output-delimiter= | "`

(The argv is the five arguments `-f`, `-2,2`, `-d`, `:` and
`--output-delimiter= | `.)

stdin:
```
root:x:0:0
```
stdout:
```
root | x | x
```
exit: `0`

### Example 4: an unreadable file is skipped

Working directory contains `a.csv`:
```
1,2
```
cmd: `fcut -f1 -d , a.csv nope.csv`

stdout:
```
1
```
exit: `1`

### Example 5: usage errors

- cmd: `fcut -f 0` gives stdout (empty) and exit `2`.
- cmd: `fcut -d , a.csv` (no `-f`) gives stdout (empty) and exit `2`.
- cmd: `fcut -f 3-1` gives stdout (empty) and exit `2`.
- cmd: `fcut -f 1 -d ab` gives stdout (empty) and exit `2`.

## Not required

- Byte or character modes (`-b`, `-c`), `--complement`, `--help`.
- Long forms such as `--fields` and `--delimiter`.
- A non-ASCII delimiter.
- Any particular stderr wording.
