# Task 05: gradebook (join students with scores)

## Goal

Write a program that joins a student roster with a file of assignment
scores, computes each student's total and percentage with exact integer
rounding, assigns a letter grade, and prints a report grouped by section with
per-section letter counts. Malformed lines, duplicate students, re-graded
assignments and scores for unknown students all have defined handling.

## Interface

```
gradebook STUDENTS SCORES
```

- **Arguments.** Exactly two file paths. Any other number of arguments is a
  usage error (exit 2).
- **Files.** ASCII text. Lines are split on `\n`. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line. Fields are
  separated by `,`, with no quoting and no trimming: spaces are part of a
  field.
- **stdout.** The report (below). Every line ends with `\n`.
- **stderr.** Error messages. Not tested.
- **Exit codes.**
  - `0`: success (malformed data lines do not change this).
  - `1`: a file cannot be read, or its first line is not exactly the required
    header. Nothing is printed on stdout.
  - `2`: usage error. Nothing is printed on stdout.

## Input files

**STUDENTS.** The first line must be exactly `id,name,section`. Each further
line is `ID,NAME,SECTION`:

- `ID` matches `[A-Za-z0-9]{1,16}`;
- `NAME` is 1 to 40 characters and contains no comma;
- `SECTION` is one uppercase letter `[A-Z]`.

**SCORES.** The first line must be exactly `id,assignment,points,max`. Each
further line is `ID,ASSIGNMENT,POINTS,MAX`:

- `ID` matches `[A-Za-z0-9]{1,16}`;
- `ASSIGNMENT` matches `[A-Za-z0-9_-]{1,32}`;
- `POINTS` and `MAX` match `[0-9]{1,6}` (leading zeros allowed), with
  `1 ≤ MAX` and `POINTS ≤ MAX`.

An empty file (no header line) is an error with exit `1`. After the header,
empty lines are ignored and not counted anywhere.

## Rules

1. **Malformed lines.** A data line with the wrong number of fields, or any
   field that breaks the rules above, is malformed. It is skipped and counted
   in `bad_students` or `bad_scores`.
2. **Duplicate students.** If a well-formed student line repeats an earlier
   ID, it is ignored and counted in `bad_students`. The first one is used.
3. **Orphans.** A well-formed score line whose ID is not a (kept) student is
   counted in `orphans`, once per line, and otherwise ignored.
4. **Re-grades.** If a student has several well-formed score lines for the
   same assignment, the **last** one in the file replaces the earlier ones.
5. **Totals.** For each student, `P` is the sum of points and `M` the sum of
   max over the student's (deduplicated) assignments. With no assignments,
   `P = M = 0`.
6. **Percentage.** If `M > 0`, the percentage is `100 * P / M` rounded to
   **one decimal place, half up** (all values are non-negative), printed with
   exactly one digit after the point, for example `96.7`, `90.0`, `0.0`,
   `100.0`.
7. **Letter.** Computed from the **exact** ratio `P / M`, not the rounded
   percentage: `A` if `100*P ≥ 90*M`, else `B` if `100*P ≥ 80*M`, else `C` if
   `100*P ≥ 70*M`, else `D` if `100*P ≥ 60*M`, else `F`. A student with
   `M = 0` has no letter.

## Output

1. One line per kept student:

   ```
   <SECTION> <ID> <NAME> <P>/<M> <PCT>% <LETTER>
   ```

   For a student with `M = 0`: `<SECTION> <ID> <NAME> 0/0 - -`.

   Order: by SECTION ascending; within a section, by exact ratio `P/M`
   **descending** (compare `P1*M2` with `P2*M1`); students with `M = 0` come
   after all others in their section; ties are broken by ID ascending
   (byte-wise).
2. One summary line per section that has at least one kept student, in
   section order:

   ```
   section <S>: students=<n> A=<a> B=<b> C=<c> D=<d> F=<f> none=<z>
   ```

   where `none` counts students with `M = 0`.
3. A final line: `bad_students=<x> bad_scores=<y> orphans=<o>`.

Limits: at most 10000 students and 200000 score lines.

## Examples

Every line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: a join with a re-grade, an orphan and a malformed line

`students.csv`:
```
id,name,section
s1,Ada Lovelace,A
s2,Alan Turing,A
s3,Grace Hopper,B
s4,Edsger Dijkstra,A
```
`scores.csv`:
```
id,assignment,points,max
s1,hw1,9,10
s1,hw2,18,20
s2,hw1,10,10
s2,hw2,15,20
s3,hw1,7,10
s9,hw1,5,10
s1,hw2,20,20
s3,hw2,12,x
```
cmd: `gradebook students.csv scores.csv`

stdout:
```
A s1 Ada Lovelace 29/30 96.7% A
A s2 Alan Turing 25/30 83.3% B
A s4 Edsger Dijkstra 0/0 - -
B s3 Grace Hopper 7/10 70.0% C
section A: students=3 A=1 B=1 C=0 D=0 F=0 none=1
section B: students=1 A=0 B=0 C=1 D=0 F=0 none=0
bad_students=0 bad_scores=1 orphans=1
```
exit: `0`

(s1's `hw2` is re-graded from 18 to 20. `s9` is an orphan. `12,x` is
malformed, so s3 has only `hw1`.)

### Example 2: rounding versus letter, ties, duplicate students

`students.csv`:
```
id,name,section
b,Bo,C
a,Al,C
c,Cy,C
c,Cy Again,D
d,Di,E,extra
```
`scores.csv`:
```
id,assignment,points,max
a,final,1799,2000
b,final,1799,2000
c,final,11,10
c,quiz,0,5
```
cmd: `gradebook students.csv scores.csv`

stdout:
```
C a Al 1799/2000 90.0% B
C b Bo 1799/2000 90.0% B
C c Cy 0/5 0.0% F
section C: students=3 A=0 B=2 C=0 D=0 F=1 none=0
bad_students=2 bad_scores=1 orphans=0
```
exit: `0`

(89.95 rounds half up to 90.0, but the exact ratio is below 90%, so the
letter is B. `a` and `b` tie and are ordered by ID. The second `c` is a
duplicate and `d,Di,E,extra` has four fields, so `bad_students=2`.
`11,10` has points above max, so it is malformed.)

### Example 3: header-only files

`students.csv` contains only `id,name,section\n`, and `scores.csv` contains
only `id,assignment,points,max\n`.

cmd: `gradebook students.csv scores.csv`

stdout:
```
bad_students=0 bad_scores=0 orphans=0
```
exit: `0`

### Example 4: errors

- `students.csv` is from Example 1, and `wrong.csv` contains
  `id,points\ns1,5\n`. cmd: `gradebook students.csv wrong.csv` gives stdout
  (empty) and exit `1`.
- cmd: `gradebook students.csv missing.csv` (no such file) gives stdout
  (empty) and exit `1`.
- cmd: `gradebook students.csv` gives stdout (empty) and exit `2`.

## Not required

- CSV quoting, escaped commas, other delimiters.
- Weighted assignments or categories.
- Non-ASCII names.
- Any particular stderr wording.
