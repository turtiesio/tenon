# Task 04: csvjoin (join two CSV files on a key column)

## Goal

Write a tool that reads two CSV files with header rows and joins them on a
named key column, like a database join. It supports an inner join (the
default) and a left outer join. The CSV parser must handle quoted fields,
including fields that contain commas, doubled quotes and line breaks, and the
output must be valid CSV again, quoted only where needed. Malformed input is
rejected before anything is printed.

## Interface

```
csvjoin [-l] [-k NAME] LEFT RIGHT
```

- **Arguments** are processed left to right:
  - `-l`: left join (rule 5). May be repeated.
  - `-k NAME` (two arguments): the key column name. The argument after `-k`
    is always NAME. If `-k` is repeated, the last one wins. Default: `id`.
  - any other argument that starts with `-` is a usage error;
  - every other argument is a file path. There must be exactly two: LEFT
    and RIGHT, in that order.
- **Usage errors (exit 2):** not exactly two paths, an unknown option, `-k`
  without a following argument, or an empty NAME.
- **Data errors (exit 1):** a file cannot be read; a file is not valid CSV
  (rule 1); a file has no header row (it has no records at all); a record has
  a different number of fields than its file's header; a header has two
  columns with the same name; NAME is not a column of **both** headers.
- On any error, print a message to stderr, print **nothing** on stdout, and
  exit with the code above. Both files are read and checked completely before
  any output is written.
- **stdout.** The joined CSV (rules 3-6). Every output record ends with `\n`.
- **Exit codes.** `0` success, `1` data error, `2` usage error.

## Rules

1. **CSV input.** The files are ASCII.
   - A file is a sequence of records. A record ends with `\n` or `\r\n`, or
     at the end of the file. A final record terminator is optional.
   - A record is a list of fields separated by `,`.
   - A field is either **unquoted**: any characters except `,`, `"`, `\r` and
     `\n` (possibly none); or **quoted**: it starts with `"` and ends with
     the next `"` that is not doubled. Inside a quoted field, `""` stands for
     one `"`, and `,`, `\r` and `\n` are ordinary characters. After the
     closing `"`, the next character must be `,`, a record terminator, or
     the end of the file.
   - Invalid CSV: a `"` inside an unquoted field (for example `ab"c`), a
     quoted field with no closing `"`, or any other character after a closing
     `"` (for example `"ab"c`).
   - **Empty lines** (a record terminator at the very start of a record) are
     skipped. A line that contains anything, even a single space or `""`, is a
     record.
2. **Header.** The first record of each file is its header. It gives the
   column names. The key column is the column whose name equals NAME exactly
   (case-sensitive). Fields are compared as exact strings.
3. **Output header.** All columns of LEFT in order, followed by all columns
   of RIGHT in order **except** its key column. A RIGHT column whose name is
   also a column name of LEFT is renamed to `r.` followed by its name. (Tests
   never create a further clash, such as RIGHT having both `x` and `r.x`.)
4. **Inner join (default).** For each data record of LEFT, in file order,
   and for each data record of RIGHT with the same key value, in file order,
   output the LEFT record's fields followed by the RIGHT record's non-key
   fields. LEFT records without a match produce no output.
5. **Left join (`-l`).** Like rule 4, but a LEFT record without any matching
   RIGHT record is output once, followed by one empty field for each RIGHT
   non-key column.
6. **CSV output.** Fields are separated by `,`, and records end with `\n`. A
   field is written quoted if and only if it contains `,`, `"`, `\r` or `\n`:
   it is wrapped in `"` and each `"` inside is doubled. All other fields,
   including empty ones, are written as they are. The header is always
   written, even if there are no data records.
7. **Limits.** Each file is at most 1 MB and at most 10000 records.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.
The files are in the working directory before the run.

### Example 1: inner join, quoted fields

`people.csv`:
```
id,name,city
1,Ann,Oslo
2,Bob,"Rome, IT"
3,Cy,Paris
```
`orders.csv`:
```
order,id,item
o1,2,pen
o2,1,"ink ""blue"""
o3,2,pad
o4,9,cup
```

cmd: `csvjoin people.csv orders.csv`

stdout:
```
id,name,city,order,item
1,Ann,Oslo,o2,"ink ""blue"""
2,Bob,"Rome, IT",o1,pen
2,Bob,"Rome, IT",o3,pad
```
exit: `0`

(Cy has no orders, and order `o4` has no person.)

### Example 2: left join, a named key, a name clash, a line break in a field

`a.csv`:
```
sku,name
A1,Widget
B2,"Gadget
XL"
C3,Gizmo
```
`b.csv` (its records end with `\r\n`; that is, its bytes are
`name,sku,qty\r\nWidget Co,A1,5\r\nGizmo Inc,C3,\r\n`):
```
name,sku,qty
Widget Co,A1,5
Gizmo Inc,C3,
```

cmd: `csvjoin -l -k sku a.csv b.csv`

stdout:
```
sku,name,r.name,qty
A1,Widget,Widget Co,5
B2,"Gadget
XL",,
C3,Gizmo,Gizmo Inc,
```
exit: `0`

### Example 3: no matches and an empty-line skip

`l.csv` is the bytes `id,v\n\n7,x\n`, and `r.csv` is the bytes
`id,w\n8,y` (no final newline).

- cmd: `csvjoin l.csv r.csv` gives stdout `id,v,w\n` and exit `0`.
- cmd: `csvjoin r.csv l.csv -l` gives stdout `id,w,v\n8,y,\n` and exit
  `0`.

### Example 4: data errors

Each of these gives stdout (empty) and exit `1`, with `people.csv` and
`orders.csv` as in Example 1:

- cmd: `csvjoin -k name people.csv orders.csv` (`orders.csv` has no `name`
  column).
- cmd: `csvjoin people.csv missing.csv` (the file does not exist).
- `bad.csv` is `id,x\n1,"open\n`. cmd: `csvjoin people.csv bad.csv`
  (unterminated quote).
- `short.csv` is `id,x\n1\n`. cmd: `csvjoin people.csv short.csv` (a record
  with 1 field under a 2-column header).
- `mid.csv` is `id,x\n1,a"b\n`. cmd: `csvjoin people.csv mid.csv` (a quote
  inside an unquoted field).

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `csvjoin people.csv`
- cmd: `csvjoin a.csv b.csv c.csv`
- cmd: `csvjoin -x people.csv orders.csv`
- cmd: `csvjoin people.csv orders.csv -k`

## Not required

- Separators other than `,`, or a lone `\r` that is not followed by `\n`
  outside a quoted field.
- Right joins, full outer joins, or joins on several columns.
- Non-ASCII input.
- Any particular stderr wording.
