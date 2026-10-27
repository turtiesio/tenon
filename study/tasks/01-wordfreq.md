# Task 01: wordfreq (word-frequency CLI)

## Goal

Write a command-line tool that counts how often each word occurs in one or
more text inputs and prints the most frequent words. It must handle a small
set of GNU-style options, report usage errors with exit code 2, skip
unreadable files with exit code 1, and produce fully deterministic output.

## Interface

```
wordfreq [OPTIONS] [FILE...]
```

In the examples, `wordfreq` stands for however your program is launched. Only
the arguments after it matter.

- **Inputs.** Each `FILE` is read in the order given. The argument `-` means
  standard input. If no `FILE` is given, standard input is read. All inputs
  are valid UTF-8.
- **Options.** Options may appear before, between or after file names. The
  argument `--` ends option parsing: every argument after it is a file name,
  even if it starts with `-`. Before `--`, any argument that starts with `-`
  and is not exactly `-` is an option.

| Option | Meaning |
|---|---|
| `-n N`, `--top N`, `--top=N` | Print at most N lines. N is a decimal integer from 0 to 1000000000, digits only (leading zeros allowed). **N = 0 means print all words.** Default: 10. |
| `-i`, `--ignore-case` | Fold ASCII letters `A`-`Z` to lowercase before counting. |
| `-m L`, `--min-length L`, `--min-length=L` | Ignore words shorter than L characters. L is a decimal integer from 1 to 1000, digits only. Default: 1. |

  - When an option is given more than once, the last one wins.
  - Short options cannot be combined: `-in` is an unknown option.
  - For `-n`, `--top`, `-m` and `--min-length`, the separate-argument form
    always takes the next argument as the value, even if it starts with `-`
    (and then fails validation if it is not a valid number).

- **stdout.** One line per word: `<count> <word>\n`. The count is a decimal
  integer, followed by exactly one space and the word. There is no header, no
  trailer and no other output.
- **stderr.** Free-form error messages. Not tested.
- **Exit codes.**
  - `0`: success.
  - `1`: at least one input file could not be opened or read. The other inputs
    are still processed and their results printed.
  - `2`: usage error. Nothing is printed to stdout, and no input is read.

## Rules

1. **Words.** A word is a maximal run of ASCII letters and digits
   (`[A-Za-z0-9]+`). Every other byte separates words, including punctuation,
   whitespace, apostrophes, hyphens, underscores and all non-ASCII bytes. So
   `Don't` is the two words `Don` and `t`, and `42` is a word.
2. **Case.** Without `-i`, words are case-sensitive (`The` and `the` differ).
   With `-i`, `A`-`Z` are lowercased first, and the printed word is the
   lowercased form.
3. **Minimum length.** A word's length is its number of characters. Words with
   length < L are dropped. They are not counted and not printed.
4. **Totals.** Counts are summed over all inputs. If the same file is named
   twice, it is counted twice.
5. **Order.** Sort by count, descending. Break ties by word in ascending byte
   order (ASCII order, so uppercase letters sort before lowercase, and digits
   sort before letters).
6. **Truncation.** Print the first N lines of that order, or all lines if
   N = 0 or there are fewer than N words. Words tied at the cut-off are simply
   cut.
7. **Empty input.** If there are no words (including empty input), print
   nothing and exit 0, or exit 1 if a file failed.
8. **Usage errors (exit 2).** These are: an unknown option; an option missing
   its value (for example `-n` as the last argument); a value that is not all
   digits or is out of range; `--top=` with an empty value; and `-i=x` or
   `--ignore-case=x` (flags take no value).
9. **Missing or unreadable file.** Write a message to stderr, skip the file,
   continue with the remaining inputs, print the results, and exit 1.
10. **Limits.** Total input is at most 10 MB. Counts fit easily in a 32-bit
    integer.

## Examples

Notation: `cmd` shows the arguments, `stdin` the standard input, and `stdout`
the exact expected output. Every line shown ends with `\n`.

### Example 1: default options, stdin

cmd: `wordfreq`

stdin:
```
the cat and the hat
The end
```
stdout:
```
2 the
1 The
1 and
1 cat
1 end
1 hat
```
exit: `0`

### Example 2: ignore case, top 2

cmd: `wordfreq -i -n 2`

stdin: the same as Example 1.

stdout:
```
3 the
1 and
```
exit: `0`

### Example 3: min length, a missing file, punctuation and digits

Working directory contains `notes.txt`:
```
Don't panic: 42 towels, 42 TOWELS.
```
`missing.txt` does not exist.

cmd: `wordfreq --min-length=4 notes.txt missing.txt`

stdout:
```
1 TOWELS
1 panic
1 towels
```
exit: `1` (an error message about `missing.txt` goes to stderr)

### Example 4: all words, digits inside words

cmd: `wordfreq -n 0`

stdin:
```
a1 b2 a1
```
stdout:
```
2 a1
1 b2
```
exit: `0`

### Example 5: usage error

cmd: `wordfreq -n abc`

stdout: (empty)

exit: `2`

## Not required

- `--help`, `--version` or any other option not listed above. They are usage
  errors, but tests will not use them.
- Unicode word rules. Non-ASCII bytes are only separators.
- Reading stdin twice (`-` given more than once).
- Directories given as `FILE`.
- Any particular stderr wording.
