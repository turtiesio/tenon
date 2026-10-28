# Task 05: runoff (instant-runoff vote count)

## Goal

Write a program that counts ranked ballots with instant-runoff voting. The
input names the candidates and then lists one ballot per line, each ranking
some of the candidates in order of preference. In each round every ballot
counts for its highest-ranked candidate still in the race. A candidate with
a strict majority of the counted ballots wins; otherwise the weakest
candidate is eliminated and the count is repeated. The program prints every
round, every elimination and the winner. Ties are broken by a fixed rule, so
the result is always unique.

## Interface

```
runoff
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print nothing on stdout, exit `2`, and do not read stdin.
- **stdin.** Lines are split on `\n`. A final line without `\n` is still a
  line. One trailing `\r` is removed from each line. Lines that are empty,
  contain only spaces, or start with `#` are ignored everywhere.
- **stdout.** The count report (rule 5). Every line ends with `\n`.
- **Invalid header (exit 1).** If the first non-ignored line is missing or
  is not a valid candidates line (rule 1), print a message to stderr, print
  **nothing** on stdout, and exit `1`.
- **Exit codes.** `0` success, `1` invalid header, `2` usage error.

## Rules

1. **Candidates line.** The first non-ignored line is exactly `candidates:`
   followed by 1 to 20 candidate names, each preceded by **one** space, with
   no trailing space. A name matches `[A-Za-z][A-Za-z0-9_]{0,19}`. Names are
   case-sensitive and must all be different. The order of this line is the
   **listing order**.
2. **Ballots.** Every later non-ignored line is a ballot: one or more items
   separated by `>`, with no spaces. The first item is the first preference.
   A ballot is **valid** if every item is exactly a listed candidate name and
   no name appears twice. Otherwise (unknown or wrongly cased name, empty
   item as in `A>>B` or `A>`, a repeated name, spaces) it is **invalid**: it
   is counted as invalid and takes no further part. A ballot need not rank
   every candidate.
3. **Rounds.** Initially every candidate is *continuing*. Round r = 1, 2, ...:
   - Each valid ballot counts for its highest-ranked continuing candidate. A
     ballot that ranks no continuing candidate is **exhausted**.
   - Let `active` = number of valid ballots − number of exhausted ballots.
   - If a continuing candidate has votes v with `2 × v > active`, that
     candidate is the **winner** and the count ends.
   - Otherwise, if only one candidate is continuing, that candidate is the
     winner (this happens only when `active` is 0).
   - Otherwise, the continuing candidate with the **fewest** votes is
     eliminated. If several are tied for fewest, the one that comes **latest**
     in the listing order is eliminated. The next round follows.
4. Zero valid ballots is not an error: every round has all counts 0, and
   candidates are eliminated one by one until one is left.
5. **Report.**
   - First line: `ballots=<valid> invalid=<k>`.
   - For each round, a line
     `round <r>: <name>=<votes> ... exhausted=<e>` listing every continuing
     candidate in listing order, separated by single spaces, then the number
     of exhausted ballots.
   - After a round that eliminates a candidate: `eliminated: <name>`.
   - After the last round: `winner: <name>`.
6. **Limits.** At most 100000 ballots.

## Examples

Each line shown ends with `\n`. For every example, cmd is `runoff`.

### Example 1: an elimination changes the winner

stdin:
```
candidates: Alice Bob Carol
Alice>Bob
Alice
Alice>Carol
Bob>Alice
Bob
Carol>Bob
Carol>Bob
```
stdout:
```
ballots=7 invalid=0
round 1: Alice=3 Bob=2 Carol=2 exhausted=0
eliminated: Carol
round 2: Alice=3 Bob=4 exhausted=0
winner: Bob
```
exit: `0`

(Bob and Carol tie for fewest; Carol is listed later and is eliminated.)

### Example 2: invalid ballots, ties and exhausted ballots

stdin (the line `Cho>Ana` ends with `\r\n`):
```
# club vote
candidates: Ana Ben Cho Dov
Ana>Ben
Ben>Ana
Cho
Dov>Cho

Ana>Zed
Ben>Ben
Ana>>Ben
ana
Cho>Ana
Ben>Cho>Dov
```
stdout:
```
ballots=6 invalid=4
round 1: Ana=1 Ben=2 Cho=2 Dov=1 exhausted=0
eliminated: Dov
round 2: Ana=1 Ben=2 Cho=3 exhausted=0
eliminated: Ana
round 3: Ben=3 Cho=3 exhausted=0
eliminated: Cho
round 4: Ben=3 exhausted=3
winner: Ben
```
exit: `0`

(In round 3, 3 votes out of 6 is not a strict majority. In round 4 the
ballots `Cho`, `Dov>Cho` and `Cho>Ana` are exhausted, so Ben has 3 of 3.)

### Example 3: an even split

stdin:
```
candidates: X Y
X
Y
```
stdout:
```
ballots=2 invalid=0
round 1: X=1 Y=1 exhausted=0
eliminated: Y
round 2: X=1 exhausted=1
winner: X
```
exit: `0`

### Example 4: no ballots

stdin:
```
candidates: P Q R
```
stdout:
```
ballots=0 invalid=0
round 1: P=0 Q=0 R=0 exhausted=0
eliminated: R
round 2: P=0 Q=0 exhausted=0
eliminated: Q
round 3: P=0 exhausted=0
winner: P
```
exit: `0`

### Example 5: errors

Each of these gives stdout (empty):

- stdin `candidates:\nA\n` gives exit `1` (no names).
- stdin `A>B\n` gives exit `1` (no candidates line).
- stdin `candidates: A B A\n` gives exit `1` (duplicate name).
- stdin `candidates:  A B\n` (two spaces) gives exit `1`.
- stdin empty gives exit `1`.
- cmd `runoff ballots.txt` gives exit `2`.

## Not required

- Other voting methods (Borda, Condorcet, single transferable vote with
  several seats).
- Batch elimination of several candidates in one round.
- Validation of the candidates line beyond rule 1.
- Any particular stderr wording.
