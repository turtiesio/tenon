# Task 01: wrap (paragraph filler and justifier)

## Goal

Write a command-line text formatter that reads plain ASCII text on stdin,
splits it into paragraphs, and refills every paragraph into lines no wider
than a given width. It can indent the first line of each paragraph and can
fully justify lines by spreading extra spaces between words. It never
hyphenates or breaks words. Bad options and bad input are told apart by exit
code.

## Interface

```
wrap [-w WIDTH] [-i INDENT] [-j]
```

- **Options.** There are no positional arguments. Each option is a separate
  argument:
  - `-w WIDTH` (two arguments): the maximum line width. WIDTH must match
    `[0-9]{1,4}` and have a value from 1 to 1000. Default: `72`.
  - `-i INDENT` (two arguments): the number of spaces put before the first
    line of every paragraph. INDENT must match `[0-9]{1,4}` and its value must
    be smaller than WIDTH. Default: `0`.
  - `-j`: justify (rule 4).

  The argument after `-w` or `-i` is always taken as its value, even if it
  starts with `-`. Options may appear in any order.
- **Usage errors (exit 2).** Any argument that is not one of the options
  above (including `-w20`, `--width`, `-ij` and any positional argument); an
  option given more than once; `-w` or `-i` without a following argument; a
  malformed or out-of-range WIDTH or INDENT, including INDENT ≥ WIDTH. On a
  usage error, print a message to stderr, print nothing on stdout, and do not
  read stdin.
- **stdin.** Text. Lines are split on `\n`. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line.
- **Invalid input (exit 1).** After `\r` removal, every line may contain only
  the space character and the printable characters `!` .. `~` (bytes 0x20 and
  0x21-0x7E). If any line contains any other byte (for example a tab), print a
  message to stderr, print **nothing** on stdout, and exit `1`. The whole
  input is checked before any output is written.
- **stdout.** The filled text. Every output line ends with `\n`.
- **Exit codes.** `0` success, `1` invalid input, `2` usage error.

## Rules

1. **Paragraphs.** A *blank* line is a line that is empty or contains only
   spaces. A paragraph is a maximal run of consecutive non-blank lines.
   Blank lines only separate paragraphs. Leading and trailing blank lines,
   and runs of several blank lines, have no other effect.
2. **Words.** The words of a paragraph are the maximal runs of non-space
   characters in all of its lines, in order. Line breaks and runs of spaces
   inside the paragraph are not kept.
3. **Filling (greedy).** Build the output lines of a paragraph one at a time.
   - The *length* of a line counts every character in it, including the
     indent.
   - A new line always takes the next word, even if the word (plus the
     indent, on a first line) is longer than WIDTH. Such a line is printed as
     it is; words are never split.
   - Then, while words remain, the next word is added to the current line,
     after one space, if the resulting length is ≤ WIDTH. Otherwise the line
     is finished and the next line starts.
   - The first line of every paragraph starts with INDENT spaces. Other lines
     have no indent.
4. **Justification (`-j`).** Every line of a paragraph **except its last
   line** that has **two or more words** is widened to exactly WIDTH
   characters by adding spaces between words. Let `s` = WIDTH − (indent on
   this line) − (sum of the word lengths), and `g` = number of gaps (words
   − 1). Every gap gets `s / g` spaces (integer division), and the **leftmost**
   `s mod g` gaps get one more. Lines with one word, and the last line of every
   paragraph, are not changed (one space between words).
5. **Output.** Paragraphs are printed in order, separated by exactly one
   empty line. No output line has trailing spaces. If the input has no
   paragraphs (it is empty or all blank), the output is empty.
6. **Limits.** At most 1 MB of input.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: greedy filling, then justified

cmd: `wrap -w 16`

stdin:
```
The quick brown fox jumps over the lazy dog.
```
stdout:
```
The quick brown
fox jumps over
the lazy dog.
```
exit: `0`

With cmd `wrap -w 16 -j` and the same stdin, stdout is:
```
The  quick brown
fox  jumps  over
the lazy dog.
```
exit: `0`

(Line 1 has 13 letters, so 3 spaces fill 2 gaps: the left gap gets 2, the
right gap 1. Line 2 has 12 letters, so each of the 2 gaps gets 2.)

### Example 2: paragraphs, indent, and an over-long word

cmd: `wrap -w 10 -i 2`

stdin, written with `\n` for each newline byte (line 3 is empty, line 4
consists of exactly three spaces):
```
  Hello   world, this is\nwrap.\n\n   \nSupercalifragilistic is long\n
```
stdout:
```
  Hello
world,
this is
wrap.

  Supercalifragilistic
is long
```
exit: `0`

(`  Hello world,` would be 14 characters. The 20-letter word plus the indent
is longer than 10, so it is printed alone on its line.)

### Example 3: justification with single-word lines

cmd: `wrap -j -w 12`

stdin:
```
a bb ccc dddd eeeee ffffff ggggggggggggg hi
```
stdout:
```
a   bb   ccc
dddd   eeeee
ffffff
ggggggggggggg
hi
```
exit: `0`

(`ffffff` and the 13-letter `ggggggggggggg` are alone on their lines, so they
are not padded. `hi` is the last line of the paragraph.)

### Example 4: blank input and the default width

- cmd: `wrap` with stdin `\n   \n\n` (only blank lines) gives stdout (empty)
  and exit `0`.
- cmd: `wrap` with stdin `one\ntwo  three` (no final newline) gives stdout
  `one two three\n` and exit `0`.

### Example 5: errors

- cmd: `wrap -w 0` gives stdout (empty) and exit `2`.
- cmd: `wrap -w 10 -i 10` gives stdout (empty) and exit `2`.
- cmd: `wrap -w 10 -w 12` gives stdout (empty) and exit `2`.
- cmd: `wrap -x` gives stdout (empty) and exit `2`.
- cmd: `wrap notes.txt` gives stdout (empty) and exit `2`.
- cmd: `wrap -w` gives stdout (empty) and exit `2`.
- cmd: `wrap` with stdin `ok line\nhas\ta tab\n` gives stdout (empty) and
  exit `1`.

## Not required

- Hyphenation, breaking long words, or any Unicode handling.
- Preserving indentation or spacing from the input.
- Reading from files given as arguments.
- Any particular stderr wording.
