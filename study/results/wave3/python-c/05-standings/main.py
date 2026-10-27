"""standings: league table from match results."""
import re
import sys
from dataclasses import dataclass, field

POINTS = re.compile(r"([0-9]{1,2}),([0-9]{1,2}),([0-9]{1,2})")
SCORE = re.compile(r"([0-9]{1,2})-([0-9]{1,2})")
NAME_TOKEN = re.compile(r"[A-Za-z0-9.&']+")


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


@dataclass
class Team:
    name: str
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    results: list = field(default_factory=list)

    @property
    def played(self):
        return self.won + self.drawn + self.lost

    @property
    def goal_diff(self):
        return self.goals_for - self.goals_against

    def record(self, scored, conceded):
        self.goals_for += scored
        self.goals_against += conceded
        if scored > conceded:
            self.won += 1
            self.results.append("W")
        elif scored == conceded:
            self.drawn += 1
            self.results.append("D")
        else:
            self.lost += 1
            self.results.append("L")


def parse_args(argv):
    if not argv:
        return (3, 1, 0)
    if len(argv) == 2 and argv[0] == "-p":
        m = POINTS.fullmatch(argv[1])
        if m:
            return tuple(int(g) for g in m.groups())
        raise UsageError(f"bad point values {argv[1]!r}")
    raise UsageError("usage: standings [-p W,D,L]")


def parse_result(line):
    tokens = line.split(" ")
    scores = [k for k, t in enumerate(tokens) if SCORE.fullmatch(t)]
    if len(scores) != 1:
        raise InputError("expected exactly one score token")
    k = scores[0]
    home_tokens, away_tokens = tokens[:k], tokens[k + 1:]
    if not home_tokens or not away_tokens:
        raise InputError("missing team name")
    for t in home_tokens + away_tokens:
        if not NAME_TOKEN.fullmatch(t):
            raise InputError(f"invalid name token {t!r}")
    home, away = " ".join(home_tokens), " ".join(away_tokens)
    if home == away:
        raise InputError(f"{home} cannot play itself")
    hg, ag = (int(g) for g in SCORE.fullmatch(tokens[k]).groups())
    return home, hg, ag, away


def read_results(data):
    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()
    results = []
    for number, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip(" ") or line.startswith("#"):
            continue
        try:
            results.append(parse_result(line))
        except InputError as e:
            raise InputError(f"line {number}: {e}") from None
    return results


def build_table(results, points):
    teams = {}

    def team(name):
        if name not in teams:
            teams[name] = Team(name)
        return teams[name]

    for home, hg, ag, away in results:
        team(home).record(hg, ag)
        team(away).record(ag, hg)

    win, draw, loss = points

    def pts(t):
        return t.won * win + t.drawn * draw + t.lost * loss

    def rank_key(t):
        return (pts(t), t.goal_diff, t.goals_for, t.won)

    ordered = sorted(teams.values(), key=lambda t: t.name.encode())
    ordered.sort(key=rank_key, reverse=True)

    width = max((len(t.name) for t in ordered), default=0)
    lines = []
    position = 0
    previous = None
    for index, t in enumerate(ordered):
        key = rank_key(t)
        if key != previous:
            position = index + 1
            previous = key
        gd = f"{t.goal_diff:+d}" if t.goal_diff else "0"
        lines.append(
            f"{position:>2}. {t.name:<{width}}"
            f"{t.played:>3}{t.won:>3}{t.drawn:>3}{t.lost:>3}"
            f"{f'{t.goals_for}:{t.goals_against}':>7}{gd:>4}{pts(t):>4}"
            f" {''.join(t.results[-5:])}"
        )
    return lines


def main():
    try:
        points = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"standings: {e}", file=sys.stderr)
        return 2
    try:
        results = read_results(sys.stdin.buffer.read().decode("latin-1"))
    except InputError as e:
        print(f"standings: {e}", file=sys.stderr)
        return 1
    sys.stdout.write("".join(line + "\n" for line in build_table(results, points)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
