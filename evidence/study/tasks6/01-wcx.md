# Task 01: wcx (count lines, words, characters and bytes)

## Goal

Write a command-line tool in the style of `wc`. It counts the lines, words,
characters and bytes of each file named on the command line (or of stdin if
no file is named), prints one row of counts per file, and a `total` row when
two or more files are named. Unreadable files are reported on stderr and
skipped, and the exit code says that something went wrong.

## Interface

```
wcx [-l] [-w] [-m] [-c] [FILE...]
```

- **Arguments.** Every argument is examined; options and file names may be
  mixed in any order.
  - An argument that is exactly `-l`, `-w`, `-m` or `-c` is an option.
    Repeating an option changes nothing.
  - Any other argument that starts with `-` (including a lone `-`, `--`,
    and combined forms such as `-lw`) is a **usage error**: print a message
    to stderr, print **nothing** on stdout, read no file and no stdin, and
    exit `2`.
  - Every other argument is a file name. File names may repeat; a repeated
    file is counted again each time.
- **Selected counts.** `-l` lines, `-w` words, `-m` characters, `-c` bytes.
  If none of the four options is given, the selection is `-l -w -c`.
- **Input.** With no file names, read stdin to its end and count it. With
  file names, read each file (stdin is not read). Content is read as bytes.
- **stdout.** The rows described under "Output".
- **Exit codes.** `0` if every named file could be read (or stdin was
  used), `1` if at least one named file could not be read, `2` for a usage
  error.

## Rules

1. **Lines** are the number of newline bytes (`\n`, 0x0A). A final line
   without `\n` does not count as a line. `\r` is an ordinary byte.
2. **Words** are maximal runs of bytes that are not ASCII whitespace. The
   ASCII whitespace bytes are space, `\t`, `\n`, `\v` (0x0B), `\f` (0x0C) and
   `\r`. Every other byte, including every byte of a non-ASCII UTF-8
   character, is part of a word.
3. **Characters** (`-m`) are Unicode code points of the content decoded as
   UTF-8. Every input counted with `-m` is valid UTF-8.
4. **Bytes** (`-c`) are the length of the content in bytes.
5. **Unreadable files.** If a named file does not exist, is a directory, or
   cannot be read for any other reason, print a message to stderr, print
   **no row** for it, and continue with the next file. The exit code is then
   `1`.

## Output

1. **Rows.** One row for each file that was read, in argument order, or
   exactly one row for stdin. If **two or more** file names were given (even
   if some of them could not be read), a final row named `total` holds the
   sum of each selected count over the files that were read (all zeros if
   none was read).
2. **Columns.** Each row holds the selected counts in this fixed order,
   whatever the order of the options: lines, words, characters, bytes.
   After the counts, a file row has one space and the file name exactly as
   given in the argument; the `total` row has one space and `total`; the
   stdin row has nothing after the counts.
3. **Width.** Let W be the number of decimal digits of the largest count
   printed anywhere in the output (W is at least 1). Every count is
   right-aligned in a field of width W (padded on the left with spaces), and
   the fields are separated by one space.
4. Every row ends with `\n`. If no row is printed (a single named file that
   cannot be read), stdout is empty.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: stdin, default counts

cmd: `wcx`

stdin (a tab between `bar` and `baz`; two spaces between `foo` and `bar`):
```
hello world
foo  bar	baz
```
stdout:
```
 2  5 25
```
exit: `0`

### Example 2: characters versus bytes

cmd: `wcx -m -l -c`

stdin is the UTF-8 text `héllo wörld\nnaïve café` (no final newline; `é`,
`ö` and `ï` are two bytes each).

stdout:
```
 1 22 26
```
exit: `0`

(1 newline, 22 code points, 26 bytes. The columns are lines, characters,
bytes, whatever the option order.)

### Example 3: several files and a total

The working directory contains `a.txt` with the bytes `one two\nthree\n`
and `b.txt` with the bytes
`\n\n  four five six seven eight nine ten eleven twelve\n`.

cmd: `wcx -w a.txt b.txt`

stdout:
```
 3 a.txt
 9 b.txt
12 total
```
exit: `0`

### Example 4: a missing file

The working directory contains only `a.txt` from Example 3.

cmd: `wcx a.txt nope.txt`

stdout:
```
 2  3 14 a.txt
 2  3 14 total
```
exit: `1`

With the same directory, cmd `wcx nope.txt` gives stdout (empty) and exit
`1`, and cmd `wcx` with empty stdin gives stdout `0 0 0\n` and exit `0`.

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `wcx -lw a.txt`
- cmd: `wcx -x`
- cmd: `wcx a.txt -`

## Not required

- Reading stdin when `-` is named (a lone `-` is a usage error here).
- Long options, `-L` (longest line), `--files0-from`.
- Invalid UTF-8 with `-m`.
- Any particular stderr wording.
