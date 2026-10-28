import re
import sys
from collections import deque

RANKS = "23456789TJQKA"
MAX_RE = re.compile(r"[1-9][0-9]{0,5}")
DECK_RE = re.compile(r"[2-9TJQKA]{1,52}")
WAR_CARDS = 4


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


def parse_args(argv):
    max_rounds = 1000
    quiet = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-n":
            if i + 1 >= len(argv) or not MAX_RE.fullmatch(argv[i + 1]):
                raise UsageError("-n needs a round limit from 1 to 999999")
            max_rounds = int(argv[i + 1])
            i += 2
        elif arg == "-q":
            quiet = True
            i += 1
        else:
            raise UsageError(f"unknown argument: {arg}")
    return max_rounds, quiet


def read_decks():
    text = sys.stdin.buffer.read().decode("ascii", errors="replace")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if len(lines) != 2:
        raise InputError("expected exactly two lines")
    for line in lines:
        if not DECK_RE.fullmatch(line):
            raise InputError(f"invalid deck: {line!r}")
    return deque(lines[0]), deque(lines[1])


def play_round(number, a, b):
    """Play one round, mutating the decks.

    Returns (line, winner) where winner is 'A', 'B', or '-' when a war
    could not be completed.
    """
    card_a, card_b = a.popleft(), b.popleft()
    pile = [card_a, card_b]
    up_a, up_b = [card_a], [card_b]
    while card_a == card_b:
        if len(a) < WAR_CARDS or len(b) < WAR_CARDS:
            line = f"{number} {'/'.join(up_a)} {'/'.join(up_b)} - {len(a)} {len(b)}"
            return line, "-"
        drawn_a = [a.popleft() for _ in range(WAR_CARDS)]
        drawn_b = [b.popleft() for _ in range(WAR_CARDS)]
        pile += drawn_a + drawn_b
        card_a, card_b = drawn_a[-1], drawn_b[-1]
        up_a.append(card_a)
        up_b.append(card_b)

    if RANKS.index(card_a) > RANKS.index(card_b):
        winner = "A"
        a.extend(pile)
    else:
        winner = "B"
        b.extend(pile)
    line = f"{number} {'/'.join(up_a)} {'/'.join(up_b)} {winner} {len(a)} {len(b)}"
    return line, winner


def main():
    try:
        max_rounds, quiet = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"war: {e}", file=sys.stderr)
        return 2

    try:
        a, b = read_decks()
    except InputError as e:
        print(f"war: {e}", file=sys.stderr)
        return 1

    out = []
    played = 0
    while True:
        if played == max_rounds:
            result = f"stopped at round {max_rounds}"
            break
        played += 1
        line, winner = play_round(played, a, b)
        if not quiet:
            out.append(line)
        if winner == "-":
            if len(a) > len(b):
                result = f"A wins in round {played}"
            elif len(b) > len(a):
                result = f"B wins in round {played}"
            else:
                result = f"draw in round {played}"
            break
        if not a:
            result = f"B wins in round {played}"
            break
        if not b:
            result = f"A wins in round {played}"
            break
    out.append(result)
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
