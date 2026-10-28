# Task 01: hexdump (canonical hex and ASCII dump of a file)

## Goal

Write a command-line tool that prints the bytes of a file (or of stdin) as a
hex dump: each output line shows the offset of its first byte, the bytes in
hexadecimal, and the same bytes as ASCII text with non-printable bytes shown
as `.`. Options select a starting offset, a maximum number of bytes and the
number of bytes per line. The dump ends with a line holding the offset just
past the last byte dumped.

## Interface

```
hexdump [-s SKIP] [-n LENGTH] [-w WIDTH] [FILE]
```

- **Arguments** are processed left to right. An argument that is exactly
  `-s`, `-n` or `-w` is an option, and the **next** argument is its value,
  whatever it looks like. If an option is given more than once, the last one
  wins. The argument `-` alone is a FILE (it means stdin). Any other argument
  that starts with `-` is a usage error. The first remaining argument is
  FILE; a second one is a usage error.
  - `-s SKIP`: start at byte offset SKIP of the input. Default `0`.
  - `-n LENGTH`: dump at most LENGTH bytes. Default: no limit.
  - `-w WIDTH`: bytes per line. Default `16`.
- **Option values.** SKIP and LENGTH must match `[0-9]{1,9}` (leading zeros
  allowed; `0` is allowed). WIDTH must match `[0-9]{1,2}` with a value from 1
  to 32.
- **Input.** The bytes of FILE, or of stdin if FILE is absent or `-`. The
  input is binary: any byte value may occur, and there is no line handling.
- **Usage errors (exit 2).** An unknown option, an option without a following
  argument, a malformed or out-of-range value, or more than one FILE. Print a
  message to stderr, print **nothing** on stdout, and do not read any input.
- **Unreadable file (exit 1).** If FILE does not exist or cannot be read (for
  example, it is a directory), print a message to stderr, print **nothing** on
  stdout, and exit `1`.
- **Exit codes.** `0` success, `1` unreadable file, `2` usage error.

## Rules

1. **Selected bytes.** The dumped bytes are the input bytes at offsets
   SKIP, SKIP+1, ..., up to the end of the input, but at most LENGTH of them.
   If SKIP is at or beyond the end of the input, no bytes are dumped (this is
   not an error).
2. **Lines.** The dumped bytes are split into consecutive chunks of WIDTH
   bytes; the last chunk may be shorter. Each chunk gives one line:

   ```
   <offset>  <hex area>  |<ascii>|
   ```

   - `<offset>` is the input offset of the chunk's first byte (counting from
     the start of the input, so it includes SKIP), written as exactly 8
     lower-case hexadecimal digits with leading zeros.
   - Then **two** spaces.
   - `<hex area>` is WIDTH fields joined by single spaces. Field k is the
     k-th byte of the chunk as two lower-case hex digits, or two spaces if the
     chunk has fewer than k bytes. So the hex area always has exactly
     `3 × WIDTH − 1` characters, and a short last line is padded with spaces.
   - Then **two** spaces, `|`, the ASCII column, and `|`.
   - The ASCII column has one character per byte of the chunk (it is **not**
     padded): the byte itself if it is in 0x20-0x7E, otherwise `.`.
3. **Final line.** After the chunk lines, print one more line with the offset
   `SKIP + (number of bytes dumped)`, as 8 lower-case hex digits. This line is
   printed even when no bytes were dumped.
4. Every output line ends with `\n`.
5. **Limits.** The input is at most 1 MiB.

## Examples

Each output line shown ends with `\n`. In `cmd`, arguments are separated by
spaces. The file `hello.txt` contains the 14 bytes `Hello, world!\n` (the
last byte is a newline, 0x0a). Trailing spaces never occur at the end of an
output line; the spaces inside a padded hex area are significant.

### Example 1: a file, 8 bytes per line

The working directory contains `hello.txt`.

cmd: `hexdump -w 8 hello.txt`

stdout:
```
00000000  48 65 6c 6c 6f 2c 20 77  |Hello, w|
00000008  6f 72 6c 64 21 0a        |orld!.|
0000000e
```
exit: `0`

(The second hex area is `6f 72 6c 64 21 0a` followed by 6 spaces: two
padding fields of two spaces, each preceded by a separating space.)

### Example 2: stdin with the default width and non-printable bytes

cmd: `hexdump`

stdin: the 21 bytes `id\tname\r\n1\tAl\x00\xff\n2\tBo\n` (`\t` is 0x09,
`\r` is 0x0d, `\n` is 0x0a, `\x00` is 0x00, `\xff` is 0xff).

stdout:
```
00000000  69 64 09 6e 61 6d 65 0d 0a 31 09 41 6c 00 ff 0a  |id.name..1.Al...|
00000010  32 09 42 6f 0a                                   |2.Bo.|
00000015
```
exit: `0`

### Example 3: skip and length

The working directory contains `hello.txt`.

cmd: `hexdump -s 4 -n 6 -w 4 hello.txt`

stdout:
```
00000004  6f 2c 20 77  |o, w|
00000008  6f 72        |or|
0000000a
```
exit: `0`

### Example 4: nothing to dump

- cmd: `hexdump` with empty stdin gives stdout `00000000\n` and exit `0`.
- The working directory contains `hello.txt`. cmd: `hexdump -s 100 hello.txt`
  gives stdout `00000064\n` and exit `0`.
- cmd: `hexdump -n 0 -` with stdin `abc` gives stdout `00000000\n` and exit
  `0`.

### Example 5: errors

Each of these gives stdout (empty):

- cmd: `hexdump -w 0` gives exit `2`.
- cmd: `hexdump -w 33` gives exit `2`.
- cmd: `hexdump -s` gives exit `2`.
- cmd: `hexdump -n -1` gives exit `2`.
- cmd: `hexdump -x` gives exit `2`.
- cmd: `hexdump a.bin b.bin` gives exit `2`.
- cmd: `hexdump missing.bin` (no such file) gives exit `1`.

## Not required

- Squeezing repeated lines (`*`), as some `hexdump` versions do.
- Other output formats (octal, decimal, grouped words, upper-case hex).
- Reading more than one file.
- Seeking efficiently: reading the whole input into memory is fine.
- Any particular stderr wording.
