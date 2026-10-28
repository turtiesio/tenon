# Task 10: war (simulation of the card game War)

## Goal

Write a deterministic simulation of the two-player card game War. Each
player has a face-down deck. In every round both players turn up their top
card and the higher card takes all the cards played; equal cards start a
"war", in which each player adds four more cards and the last of them are
compared. The program reads both decks, plays rounds until one player has
no cards, a war cannot be completed, or a round limit is reached, and prints
a log line per round and the result.

## Interface

```
war [-n MAX] [-q]
```

- **Arguments** are examined left to right, in any order.
  - `-n MAX`: the round limit. The value is the **next** argument and must
    match `[1-9][0-9]{0,5}`. Default `1000`. If `-n` appears more than
    once, the last value wins.
  - `-q`: print only the result line, without the round lines. Repeating
    it changes nothing.
  - Anything else (also `-n` without a value or with a bad value) is a
    usage error: print a message to stderr, print **nothing** on stdout, do
    not read stdin, and exit `2`.
- **stdin.** ASCII text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line.
- **Input.** Exactly two lines: the first is player A's deck, the second
  player B's deck. Each deck is 1 to 52 characters, each one of
  `2 3 4 5 6 7 8 9 T J Q K A` (written without spaces, for example
  `K2T9`), listed from the **top** of the deck to the bottom. Ranks are
  ordered `2` (lowest) < `3` < ... < `9` < `T` < `J` < `Q` < `K` < `A`
  (highest). There are no suits; the same rank may appear any number of
  times. Anything else (a different number of lines, an empty deck, more
  than 52 cards, any other character, spaces) is **invalid input**: print a
  message to stderr, print **nothing** on stdout, and exit `1`.
- **Exit codes.** `0` success (whatever the result), `1` invalid input, `2`
  usage error.

## Rules

1. **Drawing.** A player draws from the top of their deck. Cards won are
   put at the **bottom** of the winner's deck.
2. **A round.** Rounds are numbered from 1. A round starts with an empty
   *pile*.
   1. Each player draws one card, A first; both go on the pile (A's card,
      then B's). These are the *face-up* cards of the round.
   2. If the two face-up cards have different ranks, go to step 4.
   3. **War.** The last face-up cards have equal ranks. If either player
      now has fewer than 4 cards in their deck, the game ends at once
      (rule 4). Otherwise A draws 4 cards and puts them on the pile in the
      order drawn, then B does the same. The 4th card each player drew is
      their new face-up card. Go back to step 2.
   4. The player whose last face-up card is higher wins the round and puts
      the whole pile, in pile order, at the bottom of their deck.
3. **End of the game.** After a round, if a player's deck is empty, the
   other player wins. Before a round, if MAX rounds have already been
   played, the game is stopped (with `-n 3`, at most 3 rounds are played).
4. **A war that cannot be completed** ends the game in that round: the
   pile is discarded (nobody gets it), and the player with **more** cards
   left in their deck wins; if both have the same number, the game is a
   draw.
5. **Round lines.** Unless `-q` is given, every round played prints one
   line: `<round> <A face-up cards> <B face-up cards> <winner> <a> <b>`,
   where the face-up cards of a player are all of that player's face-up
   cards of the round in order, joined with `/` (one card without a war,
   for example `K`; `5/K` after one war); `<winner>` is `A` or `B`, or `-`
   for a round that ended by rule 4; and `<a>` and `<b>` are the sizes of
   A's and B's decks at the end of the round.
6. **Result line**, always printed last:
   - `A wins in round <k>` or `B wins in round <k>`, where k is the round
     in which the game was decided,
   - `draw in round <k>`,
   - `stopped at round <MAX>` if the round limit was reached first.
7. **Output.** Every line ends with `\n`.
8. **Limits.** At most 52 cards per deck. MAX is at most 999999, and
   tests keep the output below 1 MB.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: a cycle stopped by the round limit

cmd: `war -n 6`

stdin:
```
K2
3Q
```
stdout:
```
1 K 3 A 3 1
2 2 Q B 2 2
3 K 2 A 3 1
4 3 Q B 2 2
5 K 3 A 3 1
6 2 Q B 2 2
stopped at round 6
```
exit: `0`

(After round 1 A's deck is `2K3` and B's is `Q`. After round 2 A has `K3`
and B has `2Q`; after round 4 both decks are as at the start again, so the
game would repeat forever.)

### Example 2: a war, and a double war

cmd: `war`

stdin:
```
5A79K
52348
```
stdout:
```
1 5/K 5/8 A 10 0
A wins in round 1
```
exit: `0`

cmd: `war`

stdin:
```
9234T6789Q
9876T5432J2
```
stdout:
```
1 9/T/9 9/T/2 A 19 2
2 Q J A 20 1
3 9 2 A 21 0
A wins in round 3
```
exit: `0`

(In round 1 the pile becomes `9 9 2 3 4 T 8 7 6 T 6 7 8 9 5 4 3 2`. A wins
it with 9 against 2; A's deck is then `Q` followed by the pile. In round 3,
A's top card is the first card of that pile, a 9.)

### Example 3: wars that cannot be completed

cmd: `war`

stdin:
```
77
7K3
```
stdout:
```
1 7 7 - 1 2
B wins in round 1
```
exit: `0`

(A has only 1 card left, fewer than 4. B has more cards left and wins.)

cmd: `war -q`

stdin: `8\n8` (no final newline)

stdout:
```
draw in round 1
```
exit: `0`

### Example 4: quiet mode, a longer game

cmd: `war -q -n 2 -n 1000`

stdin:
```
K2
3Q
```
stdout:
```
stopped at round 1000
```
exit: `0`

cmd: `war`

stdin:
```
9234T5
9876J4Q
```
stdout:
```
1 9/T 9/J B 1 12
2 5 4 A 2 11
3 5 Q B 1 12
4 4 9 B 0 13
B wins in round 4
```
exit: `0`

### Example 5: errors

- cmd: `war` with stdin `K2\n` (one line) gives stdout (empty) and exit
  `1`.
- cmd: `war` with stdin `K2\n3q\n` gives stdout (empty) and exit `1`.
- cmd: `war` with stdin `K2\n\n` (an empty deck) gives stdout (empty) and
  exit `1`.
- Each of these gives stdout (empty) and exit `2`: `war -n 0`,
  `war -n`, `war -x`, `war 5`, `war -qn 5`.

## Not required

- Suits, shuffling, or more than two players.
- Detecting repeated positions.
- Any particular stderr wording.
