import re
import sys

PLAYER = r"[a-z][a-z0-9_]{0,15}"
COMMANDS = [
    ("SCORE", re.compile(r"SCORE (%s) (-?[0-9]{1,6})" % PLAYER)),
    ("RANK", re.compile(r"RANK (%s)" % PLAYER)),
    ("TOP", re.compile(r"TOP ([1-9][0-9]{0,2})")),
    ("AROUND", re.compile(r"AROUND (%s) ([0-9]{1,3})" % PLAYER)),
    ("REMOVE", re.compile(r"REMOVE (%s)" % PLAYER)),
    ("COUNT", re.compile(r"COUNT")),
]


class Leaderboard:
    def __init__(self):
        self.totals = {}

    def ranked(self):
        """Players in leaderboard order as (rank, name, total) tuples."""
        order = sorted(self.totals.items(), key=lambda item: (-item[1], item[0]))
        entries = []
        rank = 0
        prev_total = None
        for position, (name, total) in enumerate(order):
            if total != prev_total:
                rank = position + 1
                prev_total = total
            entries.append((rank, name, total))
        return entries

    @staticmethod
    def format_entries(entries):
        return "".join(" %d:%s:%d" % entry for entry in entries)

    def score(self, player, points):
        self.totals[player] = self.totals.get(player, 0) + int(points)
        return "TOTAL %d" % self.totals[player]

    def rank(self, player):
        for rank, name, total in self.ranked():
            if name == player:
                return "RANK %d %d" % (rank, total)
        return "ERR unknown player"

    def top(self, k):
        return "TOP" + self.format_entries(self.ranked()[: int(k)])

    def around(self, player, d):
        entries = self.ranked()
        for i, entry in enumerate(entries):
            if entry[1] == player:
                d = int(d)
                return "AROUND" + self.format_entries(entries[max(0, i - d): i + d + 1])
        return "ERR unknown player"

    def remove(self, player):
        if player in self.totals:
            del self.totals[player]
            return "OK"
        return "ERR unknown player"

    def count(self):
        return "COUNT %d" % len(self.totals)

    def execute(self, line):
        for name, pattern in COMMANDS:
            m = pattern.fullmatch(line)
            if m:
                return getattr(self, name.lower())(*m.groups())
        return "ERR bad command"


def main():
    if len(sys.argv) > 1:
        print("leaderboard: takes no arguments", file=sys.stderr)
        return 2
    board = Leaderboard()
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(board.execute(line) + "\n")
        sys.stdout.flush()
    return 0


sys.exit(main())
