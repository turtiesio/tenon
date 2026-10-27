# Task 07: linebuf (line-editor service with undo and redo)

## Goal

Write an in-memory text buffer service driven by a line protocol on stdin and
stdout. The buffer is a list of text lines. Commands append, insert, delete,
replace, print and search lines, and every change can be undone and redone
any number of steps, like in a text editor. Each input line is one command and
gets exactly one response line.

## Interface

```
linebuf
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. Lines are split on `\n`. The last line may
  lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.** Tests may wait for each
  response before sending the next command.
- **Exit code.** `0` at end of input. The buffer starts empty and is discarded
  at exit.

## Commands

Command names are upper case and case-sensitive. `<n>`, `<a>` and `<b>` are
line numbers: they must match `[0-9]{1,9}` (leading zeros allowed). The
buffer's lines are numbered from 1. `<text>` is the **rest of the line**
after the stated prefix: it may contain spaces and may be empty.

| Command | Exact form | Effect and response |
|---|---|---|
| APPEND | `APPEND <text>` | Add `<text>` as a new last line. `OK <count>` |
| INSERT | `INSERT <n> <text>` | Insert `<text>` as a new line before line n, so it becomes line n. Valid n: 1 .. count+1. `OK <count>` |
| DELETE | `DELETE <n>` | Delete line n. Valid n: 1 .. count. `OK <count>` |
| DELETE | `DELETE <a> <b>` | Delete lines a through b inclusive. Valid if 1 ≤ a ≤ b ≤ count. `OK <count>` |
| REPLACE | `REPLACE <n> <text>` | Replace the text of line n. Valid n: 1 .. count. `OK <count>` |
| PRINT | `PRINT <n>` | `<n>\|<text of line n>`, with n written without leading zeros. Valid n: 1 .. count. |
| FIND | `FIND <text>` | The numbers of all lines that contain `<text>` as a substring (case-sensitive), ascending, separated by single spaces; `NONE` if there are none. `<text>` must not be empty. |
| COUNT | `COUNT` | The number of lines. |
| UNDO | `UNDO` | See rule 3. `OK <count>` |
| REDO | `REDO` | See rule 3. `OK <count>` |

`<count>` is the number of lines in the buffer **after** the command.
The PRINT response separates the number and the text with a single `|`
character (the `\|` in the table is only Markdown escaping), for example
`3|second`.

In the forms above, every single space shown is exactly one space character.
So `APPEND x` adds `x`, `APPEND  x` (two spaces) adds ` x`, and `APPEND ` (with
one trailing space) adds an empty line. `INSERT 2 ` inserts an empty line, and
`REPLACE 1 ` makes line 1 empty.

## Rules

1. **Malformed commands.** A line that does not have exactly one of the forms
   above gets `ERR bad command` and changes nothing. That includes an unknown
   or lower-case command, `APPEND` without the space, `INSERT 1` or
   `REPLACE 1` without the space after the number, `FIND` or `FIND ` with
   empty text, a number that does not match `[0-9]{1,9}`, extra tokens after
   `DELETE`, `PRINT`, `COUNT`, `UNDO` or `REDO`, and an empty line.
2. **Bad line numbers.** A well-formed command whose line number(s) are not
   valid for the current buffer (see the table) gets `ERR bad line` and
   changes nothing. Line `0` is never valid.
3. **Undo and redo.** Each **successful** APPEND, INSERT, DELETE or REPLACE is
   one *change*. The program keeps an undo history and a redo history.
   - A change is pushed onto the undo history, and the redo history is
     cleared.
   - `UNDO` takes the most recent change off the undo history, restores the
     buffer exactly as it was before that change, and pushes the change onto
     the redo history. If the undo history is empty, the response is
     `ERR nothing to undo`.
   - `REDO` takes the most recent change off the redo history, applies it
     again (the buffer becomes exactly as it was right after that change),
     and pushes it back onto the undo history. If the redo history is empty,
     the response is `ERR nothing to redo`.
   - The histories are unlimited. PRINT, FIND, COUNT and every command that
     gets an `ERR` response leave both histories unchanged. A REPLACE that
     sets the same text is still a change.
4. **Responses are exact strings.** The only error responses are
   `ERR bad command`, `ERR bad line`, `ERR nothing to undo` and
   `ERR nothing to redo`.
5. **Limits.** At most 100000 commands. Each line of text is at most 1000
   bytes of printable ASCII and spaces. The buffer never holds more than
   10000 lines.

## Examples

Each line shown ends with `\n`. For every example, cmd is `linebuf` and exit
is `0`, except where noted.

### Example 1: editing and searching

stdin:
```
APPEND hello world
APPEND second
INSERT 1 first line
PRINT 1
PRINT 3
COUNT
FIND o
REPLACE 2 HELLO
FIND o
FIND xyz
```
stdout:
```
OK 1
OK 2
OK 3
1|first line
3|second
3
2 3
OK 3
3
NONE
```

### Example 2: undo and redo

stdin:
```
APPEND a
APPEND b
APPEND c
APPEND d
DELETE 2 3
PRINT 2
UNDO
PRINT 3
UNDO
REDO
APPEND e
REDO
UNDO
COUNT
```
stdout:
```
OK 1
OK 2
OK 3
OK 4
OK 2
2|d
OK 4
3|c
OK 3
OK 4
OK 5
ERR nothing to redo
OK 4
4
```

(After the second `UNDO`, the redo history holds the `APPEND d` and the
`DELETE`. `REDO` re-applies `APPEND d`. The new `APPEND e` clears the redo
history, so the `DELETE` can no longer be redone.)

### Example 3: errors and empty lines

stdin, written with `\n` for each newline byte (the second command is
`APPEND` followed by one space):
```
DELETE 1\nAPPEND \nPRINT 1\nPRINT 2\nINSERT 3 x\nINSERT 2 x\ndelete 1\nREPLACE 1\nDELETE 2 1\nUNDO\nPRINT 02\nFIND \nUNDO\nUNDO\n
```
stdout:
```
ERR bad line
OK 1
1|
ERR bad line
ERR bad line
OK 2
ERR bad command
ERR bad command
ERR bad line
OK 1
ERR bad line
ERR bad command
OK 0
ERR nothing to undo
```

### Example 4: usage error

cmd: `linebuf extra`

stdout: (empty)

exit: `2`

## Not required

- Persistence, files, or multi-line responses.
- Non-ASCII text.
- Regular expressions in `FIND`.
- Any particular stderr wording.
