"""war: deterministic simulation of the card game War."""
import re
import sys
from collections import deque

RANKS = "23456789TJQKA"
DECK = re.compile(rf"[{RANKS}]{{1,52}}")
MAX_RULE = re.compile(r"[1-9][0-9]{0,5}")
WAR_CARDS = 4


class UsageError(Exception):
    pass


def parse_args(args):
    max_rounds = 1000
    quiet = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-n":
            if i + 1 >= len(args) or not MAX_RULE.fullmatch(args[i + 1]):
                raise UsageError("-n needs a number from 1 to 999999")
            max_rounds = int(args[i + 1])
            i += 2
            continue
        if arg == "-q":
            quiet = True
        else:
            raise UsageError(f"unexpected argument: {arg}")
        i += 1
    return max_rounds, quiet


def read_decks(text):
    lines = text.split("\n") if text else []
    if text.endswith("\n"):
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if len(lines) != 2 or not all(DECK.fullmatch(line) for line in lines):
        return None
    return deque(lines[0]), deque(lines[1])


def play_round(a, b):
    """Play one round. Return (A face-up cards, B face-up cards, winner or None)."""
    pile = []
    a_up, b_up = [a.popleft()], [b.popleft()]
    pile += [a_up[-1], b_up[-1]]
    while a_up[-1] == b_up[-1]:
        if len(a) < WAR_CARDS or len(b) < WAR_CARDS:
            return a_up, b_up, None
        for deck, up in ((a, a_up), (b, b_up)):
            drawn = [deck.popleft() for _ in range(WAR_CARDS)]
            pile += drawn
            up.append(drawn[-1])
    if RANKS.index(a_up[-1]) > RANKS.index(b_up[-1]):
        winner, deck = "A", a
    else:
        winner, deck = "B", b
    deck.extend(pile)
    return a_up, b_up, winner


def play(a, b, max_rounds, out):
    """Play the game, appending round lines to out; return the result line."""
    for round_no in range(1, max_rounds + 1):
        a_up, b_up, winner = play_round(a, b)
        if out is not None:
            out.append(f"{round_no} {'/'.join(a_up)} {'/'.join(b_up)} "
                       f"{winner or '-'} {len(a)} {len(b)}")
        if winner is None:
            if len(a) == len(b):
                return f"draw in round {round_no}"
            return f"{'A' if len(a) > len(b) else 'B'} wins in round {round_no}"
        if not a:
            return f"B wins in round {round_no}"
        if not b:
            return f"A wins in round {round_no}"
    return f"stopped at round {max_rounds}"


def main(argv):
    try:
        max_rounds, quiet = parse_args(argv)
    except UsageError as e:
        print(f"war: {e}", file=sys.stderr)
        print("usage: war [-n MAX] [-q]", file=sys.stderr)
        return 2
    decks = read_decks(sys.stdin.buffer.read().decode("latin-1"))
    if decks is None:
        print("war: input must be two decks of 1 to 52 cards from 23456789TJQKA",
              file=sys.stderr)
        return 1
    out = None if quiet else []
    result = play(*decks, max_rounds, out)
    lines = (out or []) + [result]
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
