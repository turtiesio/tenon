"""runoff: instant-runoff vote count with a round-by-round report."""
import re
import sys
from collections import Counter

NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,19}")
MAX_CANDIDATES = 20


class HeaderError(Exception):
    pass


def read_lines(data):
    text = data.decode("latin-1")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def is_ignored(line):
    return not line.strip(" ") or line.startswith("#")


def parse_candidates(line):
    prefix = "candidates:"
    if line is None or not line.startswith(prefix):
        raise HeaderError("missing candidates line")
    rest = line[len(prefix):]
    if not rest.startswith(" "):
        raise HeaderError("no candidate names")
    names = rest[1:].split(" ")
    if not 1 <= len(names) <= MAX_CANDIDATES:
        raise HeaderError("expected 1 to 20 candidates")
    if not all(NAME_RE.fullmatch(n) for n in names):
        raise HeaderError("malformed candidate name")
    if len(set(names)) != len(names):
        raise HeaderError("duplicate candidate name")
    return names


def parse_ballot(line, candidates):
    items = line.split(">")
    if any(item not in candidates for item in items) or len(set(items)) != len(items):
        return None
    return tuple(items)


def count(candidates, ballots, valid):
    """Run the rounds; return report lines. `ballots` maps ranking tuple -> multiplicity."""
    out = []
    continuing = list(candidates)
    rnd = 1
    while True:
        votes = dict.fromkeys(continuing, 0)
        exhausted = 0
        for ranking, n in ballots.items():
            choice = next((c for c in ranking if c in votes), None)
            if choice is None:
                exhausted += n
            else:
                votes[choice] += n
        active = valid - exhausted
        tally = " ".join(f"{c}={votes[c]}" for c in continuing)
        out.append(f"round {rnd}: {tally} exhausted={exhausted}")

        winner = next((c for c in continuing if 2 * votes[c] > active), None)
        if winner is None and len(continuing) == 1:
            winner = continuing[0]
        if winner is not None:
            out.append(f"winner: {winner}")
            return out

        fewest = min(votes.values())
        loser = [c for c in continuing if votes[c] == fewest][-1]
        continuing.remove(loser)
        out.append(f"eliminated: {loser}")
        rnd += 1


def main(argv):
    if argv:
        print("usage: runoff  (reads ballots from stdin)", file=sys.stderr)
        return 2

    lines = [l for l in read_lines(sys.stdin.buffer.read()) if not is_ignored(l)]
    try:
        candidates = parse_candidates(lines[0] if lines else None)
    except HeaderError as e:
        print(f"runoff: invalid header: {e}", file=sys.stderr)
        return 1

    known = set(candidates)
    ballots = Counter()
    valid = invalid = 0
    for line in lines[1:]:
        ranking = parse_ballot(line, known)
        if ranking is None:
            invalid += 1
        else:
            valid += 1
            ballots[ranking] += 1

    out = [f"ballots={valid} invalid={invalid}"] + count(candidates, ballots, valid)
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
