import re
import sys

SCORE = re.compile(r"([0-9]{1,2})-([0-9]{1,2})")
NAME_TOKEN = re.compile(r"[A-Za-z0-9.&']+")
POINTS_ARG = re.compile(r"[0-9]{1,2}(,[0-9]{1,2}){2}")
FORM_LENGTH = 5


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


class Team:
    def __init__(self, name):
        self.name = name
        self.won = self.drawn = self.lost = 0
        self.goals_for = self.goals_against = 0
        self.form = []

    def record(self, scored, conceded):
        self.goals_for += scored
        self.goals_against += conceded
        if scored > conceded:
            self.won += 1
            self.form.append("W")
        elif scored == conceded:
            self.drawn += 1
            self.form.append("D")
        else:
            self.lost += 1
            self.form.append("L")

    @property
    def played(self):
        return self.won + self.drawn + self.lost

    @property
    def goal_diff(self):
        return self.goals_for - self.goals_against

    def points(self, scheme):
        win, draw, loss = scheme
        return self.won * win + self.drawn * draw + self.lost * loss


def parse_args(argv):
    if not argv:
        return (3, 1, 0)
    if len(argv) == 2 and argv[0] == "-p" and POINTS_ARG.fullmatch(argv[1]):
        return tuple(int(x) for x in argv[1].split(","))
    raise UsageError("usage: standings [-p W,D,L]")


def parse_result(line):
    """Return (home, away, hg, ag) or raise ValueError."""
    tokens = line.split(" ")
    scores = [i for i, t in enumerate(tokens) if SCORE.fullmatch(t)]
    if len(scores) != 1:
        raise ValueError("expected exactly one score token")
    i = scores[0]
    home, away = tokens[:i], tokens[i + 1:]
    if not home or not away:
        raise ValueError("missing team name")
    if not all(NAME_TOKEN.fullmatch(t) for t in home + away):
        raise ValueError("bad team name")
    home_name, away_name = " ".join(home), " ".join(away)
    if home_name == away_name:
        raise ValueError("a team cannot play itself")
    hg, ag = (int(x) for x in SCORE.fullmatch(tokens[i]).groups())
    return home_name, away_name, hg, ag


def read_results(text):
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    teams = {}
    for number, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip(" ") or line.startswith("#"):
            continue
        try:
            home, away, hg, ag = parse_result(line)
        except ValueError as e:
            raise InputError(f"line {number}: {e}")
        teams.setdefault(home, Team(home)).record(hg, ag)
        teams.setdefault(away, Team(away)).record(ag, hg)
    return list(teams.values())


def render(teams, scheme):
    def key(t):
        return (-t.points(scheme), -t.goal_diff, -t.goals_for, -t.won)

    ordered = sorted(teams, key=lambda t: key(t) + (t.name,))
    width = max((len(t.name) for t in ordered), default=0)
    lines = []
    position = 0
    previous = None
    for index, t in enumerate(ordered, 1):
        if key(t) != previous:
            position = index
            previous = key(t)
        diff = f"{t.goal_diff:+d}" if t.goal_diff else "0"
        lines.append(
            f"{position:>2}. {t.name:<{width}}"
            f"{t.played:>3}{t.won:>3}{t.drawn:>3}{t.lost:>3}"
            f"{f'{t.goals_for}:{t.goals_against}':>7}"
            f"{diff:>4}{t.points(scheme):>4}"
            f" {''.join(t.form[-FORM_LENGTH:])}\n"
        )
    return "".join(lines)


def main():
    try:
        scheme = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"standings: {e}", file=sys.stderr)
        return 2
    try:
        teams = read_results(sys.stdin.buffer.read().decode("latin-1"))
    except InputError as e:
        print(f"standings: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(render(teams, scheme))
    return 0


sys.exit(main())
