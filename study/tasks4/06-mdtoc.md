# Task 06: mdtoc (table of contents for a Markdown document)

## Goal

Write a program that reads a Markdown document and prints a table of
contents: a nested bullet list with one link per heading. Each link points
to the heading's anchor (a "slug" made from the heading text), and repeated
slugs get numbered suffixes so that every anchor is unique. Headings inside
fenced code blocks are ignored. An option limits the table to headings up to
a given level.

## Interface

```
mdtoc [-l LEVEL]
```

- **Arguments.** Either none, or exactly the two arguments `-l` and LEVEL,
  where LEVEL is one digit `1`-`6`. Default LEVEL: `6`. Anything else is a
  usage error: print a message to stderr, print nothing on stdout, exit `2`,
  and do not read stdin.
- **stdin.** An ASCII Markdown document. Lines are split on `\n`. A final
  line without `\n` is still a line. One trailing `\r` is removed from each
  line.
- **stdout.** The table of contents (rule 5). Every line ends with `\n`. If
  there are no listed headings, stdout is empty.
- **Exit codes.** `0` success (also with no headings), `2` usage error.

## Rules

1. **Code fences.** A line that **starts with** three backticks
   (```` ``` ````, at the very beginning of the line, possibly followed by
   anything) is a fence line. The first fence line opens a code block, the
   next one closes it, and so on. Fence lines and all lines inside a code
   block are never headings. A code block that is never closed lasts to the
   end of the input.
2. **Headings.** Outside code blocks, a line is a heading if it starts with
   1 to 6 `#` characters followed by a space, at the very beginning of the
   line. The number of `#` is the heading's **level**. The heading **text**
   is the rest of the line after that space, with leading and trailing
   spaces removed. If the text is empty, the line is not a heading. So
   `#Tag`, ` # x` (leading space), `####### x` (seven `#`) and `## ` are not
   headings.
3. **Slugs.** The base slug of a heading is made from its text:
   - map `A`-`Z` to `a`-`z`;
   - replace every space with `-`;
   - keep `a`-`z`, `0`-`9`, `-` and `_`;
   - drop every other character.

   If the result is empty, the base slug is `section`. Spaces are not merged:
   `a  b` (two spaces) gives `a--b`.
4. **Unique slugs.** Headings get slugs in document order, and a set of used
   slugs starts empty. If the base slug s is not used yet, the slug is s.
   Otherwise it is the first of `s-1`, `s-2`, `s-3`, ... that is not used
   yet. The chosen slug is added to the used set. **Every** heading gets a
   slug this way, including headings that are not listed because of `-l`.
5. **Output.** The listed headings are those with level ≤ LEVEL, in document
   order. Let `min` be the smallest level among them. Each is printed as:

   ```
   <indent>- [<text>](#<slug>)
   ```

   where `<indent>` is `2 × (level − min)` spaces and `<text>` is the
   heading text exactly as defined in rule 2.
6. **Limits.** The input is at most 1000000 bytes.

## Examples

Each line shown ends with `\n`.

### Example 1: a nested outline

cmd: `mdtoc`

stdin:
```
# Project Tenon

Intro text.

## Getting Started
### Install
### First steps
## FAQ
```
stdout:
```
- [Project Tenon](#project-tenon)
  - [Getting Started](#getting-started)
    - [Install](#install)
    - [First steps](#first-steps)
  - [FAQ](#faq)
```
exit: `0`

### Example 2: fences, non-headings and duplicate slugs

In the stdin below, the line `##  Spaced   out  ` has two spaces after
`##`, three spaces between the words, and two trailing spaces. The fence
lines are exactly three backticks each.

cmd: `mdtoc`

stdin:
````
## Usage
```
# not a heading
## also not
```
## Usage
#Hashtag
#### Notes & Tips!
##  Spaced   out  
## Usage-1
## Usage
## ???
####### Seven
````
stdout:
```
- [Usage](#usage)
- [Usage](#usage-1)
    - [Notes & Tips!](#notes--tips)
- [Spaced   out](#spaced---out)
- [Usage-1](#usage-1-1)
- [Usage](#usage-2)
- [???](#section)
```
exit: `0`

(`Usage-1` has the base slug `usage-1`, which is already used by the second
`Usage`, so it becomes `usage-1-1`. The last `Usage` then skips `usage` and
`usage-1` and gets `usage-2`.)

### Example 3: limiting the level

- cmd: `mdtoc -l 2` with the stdin of Example 2 gives the stdout of Example 2
  without the line `    - [Notes & Tips!](#notes--tips)`, and exit `0`.
- cmd: `mdtoc -l 1` with stdin `# A\n## A\n# A\n` gives stdout
  `- [A](#a)\n- [A](#a-2)\n` and exit `0` (the unlisted `## A` still takes
  the slug `a-1`).
- cmd: `mdtoc` with stdin `### Deep\n#### Deeper\n` gives stdout
  `- [Deep](#deep)\n  - [Deeper](#deeper)\n` and exit `0`.

### Example 4: no headings, unclosed fence

- cmd: `mdtoc` with stdin `text\n#\n# \n` gives stdout (empty) and exit
  `0`.
- cmd: `mdtoc` with stdin ```` ## A\n```\n# B\n ```` gives stdout
  `- [A](#a)\n` and exit `0`.

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `mdtoc -l 7`
- cmd: `mdtoc -l`
- cmd: `mdtoc -l 0`
- cmd: `mdtoc README.md`

## Not required

- Setext headings (underlined with `===` or `---`), closing `#` sequences,
  headings indented by spaces, `~~~` fences, or fences indented by spaces.
- Inline Markdown in heading text: it is kept as is in the link text, and
  the slug is made from it by rule 3 like from any other text.
- Escaping `[`, `]` or `)` in the link text.
- Non-ASCII input.
- Any particular stderr wording.
