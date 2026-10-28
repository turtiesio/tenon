# Task 08: vfs (in-memory file system shell)

## Goal

Write a small in-memory file system driven by a line protocol on stdin and
stdout. It has directories and text files in a single tree, a current
directory, and relative and absolute paths with `.` and `..`. Commands
create directories, write and read files, list directories, remove and move
entries, change the current directory and report disk usage. Nothing is
stored on the real disk.

## Interface

```
vfs
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print **nothing** on stdout, do not read stdin, and exit `2`.
- **stdin.** One command per line, ASCII. Lines are split on `\n`. If the
  input ends with `\n`, there is no extra empty line after it. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. Flush stdout after every response.
- **Exit codes.** `0` at end of input, `2` usage error.

## The tree

1. At the start there is only the **root** directory, which is also the
   current directory. Every other entry is a directory or a file with a
   name and a parent directory; names are unique within a directory. A
   file holds a text of 1 to 100 characters.
2. **Names** match `[A-Za-z0-9._-]{1,32}` and are not `.` or `..` (so
   `...` and `.hidden` are names).
3. **Paths.** A path is either `/` (the root), or an optional leading `/`
   followed by one or more *components* separated by single `/`. Each
   component is a name, `.` or `..`. There are no empty components: a
   trailing `/` and `//` are not allowed. A path starting with `/` is
   absolute; any other path is relative to the current directory.
4. **Resolving** a path walks it from its start (the root for an absolute
   path, the current directory otherwise), one component at a time:
   - If the current node is a file, the walk fails with
     `ERR not a directory` (a file has no components below it, not even
     `.` or `..`).
   - `.` stays at the current directory; `..` goes to its parent (the
     parent of the root is the root).
   - A name goes to the entry of that name in the current directory. If
     there is none: for the **last** component the walk ends with the path
     *missing* (its parent directory and final name are known); for any
     earlier component the walk fails with `ERR not found`.
   The result is an existing node, or a missing final entry in an existing
   directory. A path ending in `.` or `..`, and the path `/`, always name an
   existing directory if they resolve.
5. **Absolute path of a directory**: `/` for the root, otherwise `/`
   followed by the names from the root down, joined with `/`, for example
   `/docs/notes`.

## Commands

Command names are upper case. Tokens are separated by exactly one space,
with no leading or trailing spaces, except inside a text.

| Command | Effect and response |
|---|---|
| `PWD` | The absolute path of the current directory. |
| `CD <path>` | Make the directory the current directory: `OK`. A missing path: `ERR not found`; a file: `ERR not a directory`. |
| `MKDIR <path>` | Create an empty directory at a missing path: `OK`. If the path exists (file or directory): `ERR exists`. |
| `WRITE <path> <text>` | `<text>` is everything after `WRITE <path> ` up to the end of the line: 1 to 100 characters from `0x20` (space) to `0x7E`, spaces included anywhere. A missing path creates a file; an existing file gets the new text. Both answer `OK`. A directory: `ERR is a directory`. |
| `CAT <path>` | The text of the file. A directory: `ERR is a directory`; a missing path: `ERR not found`. |
| `LS` or `LS <path>` | For a directory (the current one if no path is given): its entries sorted by name in byte order, each directory name followed by `/`, joined with single spaces, or `-` if it is empty. For a file: the file's own name. A missing path: `ERR not found`. |
| `RM <path>` | Remove a file or an **empty** directory: `OK`. A missing path: `ERR not found`. If the node is the root, the current directory or a directory that contains the current directory at any depth: `ERR busy`. A non-empty directory: `ERR not empty`. (`ERR busy` is checked before `ERR not empty`.) |
| `MV <src> <dst>` | See "Moving". |
| `DU` or `DU <path>` | `<bytes> <files> <dirs>` for the node (the current directory if no path is given): for a directory, the total length of the texts of all files anywhere below it, the number of those files, and the number of directories below it (not counting itself); for a file, its text length, `1` and `0`. A missing path: `ERR not found`. |

### Moving

`MV <src> <dst>` is checked in this order:

1. Resolve `<src>`. A walk failure gives its error; a missing path gives
   `ERR not found`. If the node is the root: `ERR invalid`.
2. Resolve `<dst>`. A walk failure gives its error.
   - If `<dst>` is an existing **directory**, the target is the entry named
     like the source node inside that directory. If that directory already
     has an entry of that name (even the source itself): `ERR exists`.
   - If `<dst>` is an existing file: `ERR exists`.
   - If `<dst>` is missing, the target is that missing entry (its parent
     directory and final name).
3. If the source is a directory and the target's parent directory is the
   source itself or lies anywhere below it: `ERR invalid`.
4. Otherwise move the node (with everything below it) to the target, under
   the target's name: `OK`. The current directory stays the same node, so
   if it was moved (or lies below a moved directory), `PWD` shows its new
   path.

### Errors

A line that is not exactly one of the forms above (unknown or lower-case
command, wrong token count, a malformed path, an empty or too long text,
extra spaces outside a text, an empty line) gets `ERR bad command`. For the
other commands, a walk failure gives its error (`ERR not found` or
`ERR not a directory`) before any other check. A command that gets an
`ERR` response changes nothing.

At most 10000 commands, and paths of at most 200 characters.

## Examples

Each line shown ends with `\n`. cmd is `vfs` in every example.

### Example 1: creating, reading and listing

stdin:
```
PWD
MKDIR docs
MKDIR docs/notes
WRITE docs/todo.txt buy  milk
CAT docs/todo.txt
LS
LS docs
CD docs/notes
PWD
WRITE ../a.md # Title
LS ..
DU /
CD ../..
LS docs/todo.txt
MKDIR /docs
MKDIR x/y
CAT docs
CAT nope
LS /docs/todo.txt/x
```
stdout:
```
/
OK
OK
OK
buy  milk
docs/
notes/ todo.txt
OK
/docs/notes
OK
a.md notes/ todo.txt
16 2 2
OK
todo.txt
ERR exists
ERR not found
ERR is a directory
ERR not found
ERR not a directory
```
exit: `0`

(The text `buy  milk` keeps both spaces. `DU /` counts 9 + 7 bytes in two
files and the directories `docs` and `docs/notes`. `x/y` fails because `x`
is not the last component.)

### Example 2: removing and moving

stdin:
```
MKDIR a
MKDIR a/b
WRITE a/b/f.txt hello
CD a/b
RM /a/b
RM /a
RM f.txt
CD /
RM a
MV a/b c
LS
MV a c
LS c
MV /c /c/a
MV / x
CD c/a
MV /c /z
PWD
WRITE g.txt hi
MV g.txt ../f.txt
MV g.txt ..
LS /z
DU /z
DU
RM ..
CD ../../..
PWD
```
stdout:
```
OK
OK
OK
OK
ERR busy
ERR busy
OK
OK
ERR not empty
OK
a/ c/
OK
a/
ERR invalid
ERR invalid
OK
OK
/z/a
OK
OK
ERR not found
a/ f.txt
2 1 1
0 0 0
ERR busy
OK
/
```
exit: `0`

(`MV a c` moves `/a` into the existing directory `/c`. `MV /c /c/a` would
put `c` below itself. After `MV /c /z` the current directory, formerly
`/c/a`, is `/z/a`. `MV g.txt ../f.txt` renames the file while moving it to
`/z`. `RM ..` would remove `/z`, which contains the current directory.)

### Example 3: malformed lines

stdin (the 8th line, `WRITE f `, ends with a space):
```
mkdir a
MKDIR a/
MKDIR /a//b
LS  /
PWD x
CD
WRITE f
WRITE f 
MKDIR ...
CD ...
CD ..
PWD
MV ... ..
LS
```
stdout:
```
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
OK
OK
OK
/
ERR exists
.../
```
exit: `0`

(`WRITE f ` has an empty text. `...` is a valid name. `CD ..` in `/...`
goes back to the root. `MV ... ..` targets `/...` itself, which exists.)

## Not required

- Links, permissions, timestamps, appending to files, or wildcards.
- Removing non-empty directories recursively.
- Any particular stderr wording.
