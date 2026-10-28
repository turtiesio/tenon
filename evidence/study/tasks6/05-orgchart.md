# Task 05: orgchart (reporting tree with team costs)

## Goal

Write a program that reads an employee list in a simple comma-separated
format and prints the organization as an indented tree. Every employee line
shows how many people report to them directly or indirectly and the total
salary cost of their whole subtree. Optionally only one employee's subtree is
printed. Input that does not form a proper forest of trees (unknown
managers, duplicate ids, cycles) is rejected.

## Interface

```
orgchart [ID]
```

- **Arguments.** None, or exactly one `ID`. Two or more arguments are a
  usage error: print a message to stderr, print **nothing** on stdout, do not
  read stdin, and exit `2`.
- **stdin.** UTF-8 text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line.
- **stdout.** The tree (see "Output").
- **Errors (exit 1).** Invalid input (rules 1-3), or an `ID` argument that is
  not the id of an employee: print a message to stderr, print **nothing** on
  stdout, and exit `1`.
- **Exit codes.** `0` success, `1` invalid input or unknown `ID`, `2` usage
  error.

## Rules

1. **Header.** The first line must be exactly `id,name,manager,salary`.
   Empty input, or any other first line, is invalid.
2. **Employee lines.** Every later line that is empty is ignored. Every other
   line must have exactly four fields separated by commas (so exactly three
   commas; there is no quoting):
   - `id` matches `[a-z0-9]{1,8}`; ids are unique;
   - `name` is non-empty and does not start or end with a space (it may
     contain inner spaces and any non-ASCII characters, but no comma);
   - `manager` is empty (the employee is a **root**) or matches
     `[a-z0-9]{1,8}`;
   - `salary` matches `[0-9]{1,9}`.

   Anything else is invalid.
3. **Structure.** Every non-empty `manager` must be the id of an employee in
   the input (employees may appear before or after their manager). Following
   managers upward from any employee must reach a root; if it does not (the
   employee is on or below a cycle, including an employee who is their own
   manager), the input is invalid.
4. **Order.** The roots, and the direct reports of each employee, are sorted
   by name (comparing the UTF-8 bytes) and, for equal names, by id (byte
   order).
5. **Counts.** For each employee, `reports` is the number of employees below
   them at any depth (not counting themselves), and `cost` is the sum of the
   salaries of the employee and everyone below them.
6. **Limits.** At most 10000 employees; the tree is at most 500 levels
   deep.

## Output

Print the tree depth-first: an employee's line, then the subtrees of their
direct reports in the order of rule 4. Without `ID`, print every root's tree
in the order of rule 4. With `ID`, print only that employee's subtree, with
that employee at depth 0. Each line is:

```
<indent><name> [<id>] reports=<r> cost=<c>
```

- `<indent>` is two spaces per depth level (none at depth 0).
- `<c>` is written with a comma between each group of three digits counted
  from the right, for example `0`, `500`, `1,000`, `901,700`, `12,345,678`.

Every line ends with `\n`. An input with only the header prints nothing.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

In Examples 1 and 2, stdin is (UTF-8; `ë` and `É` are non-ASCII):
```
id,name,manager,salary
e1,Grace Hopper,,250000
e2,Alan Turing,e1,180000
e7,Ada Lovelace,e1,190000
e3,Zoë Weiss,e7,95000
e4,Ben Ng,e7,98000
e9,Ben Ng,e2,1200
e5,Émile Roux,e7,87500
```

### Example 1: the whole tree

cmd: `orgchart`

stdout:
```
Grace Hopper [e1] reports=6 cost=901,700
  Ada Lovelace [e7] reports=3 cost=470,500
    Ben Ng [e4] reports=0 cost=98,000
    Zoë Weiss [e3] reports=0 cost=95,000
    Émile Roux [e5] reports=0 cost=87,500
  Alan Turing [e2] reports=1 cost=181,200
    Ben Ng [e9] reports=0 cost=1,200
```
exit: `0`

(`É` is the bytes 0xC3 0x89, which sort after `Z`.)

### Example 2: one subtree

cmd: `orgchart e7` with the same stdin gives stdout:
```
Ada Lovelace [e7] reports=3 cost=470,500
  Ben Ng [e4] reports=0 cost=98,000
  Zoë Weiss [e3] reports=0 cost=95,000
  Émile Roux [e5] reports=0 cost=87,500
```
exit: `0`

With the same stdin, cmd `orgchart e8` gives stdout (empty) and exit `1`.

### Example 3: several roots, equal names, an empty line

cmd: `orgchart`

stdin (there is an empty line after `b2`, and the `c3` line ends with
`\r\n`):
```
id,name,manager,salary
b2,Kim,,1000

a1,Kim,,2000
c3,Lee,a1,500
c4,Al,c3,0
```
stdout:
```
Kim [a1] reports=2 cost=2,500
  Lee [c3] reports=1 cost=500
    Al [c4] reports=0 cost=0
Kim [b2] reports=0 cost=1,000
```
exit: `0`

With stdin `id,name,manager,salary\n` the same cmd gives stdout (empty) and
exit `0`.

### Example 4: invalid input

Each of these, with cmd `orgchart`, gives stdout (empty) and exit `1`:

- stdin `id,name,manager,salary\na,A,b,1\nb,B,a,2\nc,C,,3\n` (a cycle)
- stdin `id,name,manager,salary\na,A,,1\nb,B,x,2\n` (unknown manager)
- stdin `id,name,manager,salary\na,A,,1\na,B,a,2\n` (duplicate id)
- stdin `id,name,manager,salary\na,Smith, Jo,,1\n` (five fields)
- stdin `id,name,mgr,salary\n` (wrong header)
- empty stdin

cmd `orgchart a b` gives stdout (empty) and exit `2`.

## Not required

- Quoted fields or commas inside names.
- Salaries with more than 9 digits, or depth limits.
- Any particular stderr wording.
