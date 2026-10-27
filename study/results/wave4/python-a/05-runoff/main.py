import re
import sys

NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,19}")


def significant_lines(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "" or line.startswith("#"):
            continue
        yield line


def parse_candidates(line):
    prefix = "candidates:"
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):]
    if not rest.startswith(" "):
        return None
    names = rest[1:].split(" ")
    if not 1 <= len(names) <= 20:
        return None
    if not all(NAME_RE.fullmatch(n) for n in names):
        return None
    if len(set(names)) != len(names):
        return None
    return names


def parse_ballot(line, candidates):
    items = line.split(">")
    if any(item not in candidates for item in items):
        return None
    if len(set(items)) != len(items):
        return None
    return items


def run_count(candidates, ballots):
    """Return the round-by-round report lines of the instant-runoff count."""
    out = []
    continuing = list(candidates)
    round_no = 0
    while True:
        round_no += 1
        votes = {c: 0 for c in continuing}
        exhausted = 0
        for ballot in ballots:
            choice = next((c for c in ballot if c in votes), None)
            if choice is None:
                exhausted += 1
            else:
                votes[choice] += 1
        active = len(ballots) - exhausted
        tally = " ".join(f"{c}={votes[c]}" for c in continuing)
        out.append(f"round {round_no}: {tally} exhausted={exhausted}")

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


def main():
    if len(sys.argv) > 1:
        print("runoff: no arguments expected", file=sys.stderr)
        sys.exit(2)

    text = sys.stdin.buffer.read().decode("latin-1")
    lines = significant_lines(text)
    header = next(lines, None)
    candidates = parse_candidates(header) if header is not None else None
    if candidates is None:
        print("runoff: missing or invalid candidates line", file=sys.stderr)
        sys.exit(1)

    ballots = []
    invalid = 0
    for line in lines:
        ballot = parse_ballot(line, candidates)
        if ballot is None:
            invalid += 1
        else:
            ballots.append(ballot)

    report = [f"ballots={len(ballots)} invalid={invalid}"]
    report += run_count(candidates, ballots)
    sys.stdout.write("\n".join(report) + "\n")


if __name__ == "__main__":
    main()
