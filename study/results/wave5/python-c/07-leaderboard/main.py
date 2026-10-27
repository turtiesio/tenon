import re
import sys

PLAYER = r"[a-z][a-z0-9_]{0,15}"
COMMANDS = {
    "SCORE": re.compile(rf"SCORE ({PLAYER}) (-?[0-9]{{1,6}})"),
    "RANK": re.compile(rf"RANK ({PLAYER})"),
    "TOP": re.compile(r"TOP ([1-9][0-9]{0,2})"),
    "AROUND": re.compile(rf"AROUND ({PLAYER}) ([0-9]{{1,3}})"),
    "REMOVE": re.compile(rf"REMOVE ({PLAYER})"),
    "COUNT": re.compile(r"COUNT"),
}
UNKNOWN = "ERR unknown player"


class Leaderboard:
    def __init__(self):
        self.totals = {}

    def ranked(self):
        """Return [(rank, player, total)] in leaderboard order."""
        order = sorted(self.totals.items(), key=lambda item: (-item[1], item[0]))
        entries = []
        for position, (player, total) in enumerate(order):
            if position > 0 and total == entries[-1][2]:
                rank = entries[-1][0]
            else:
                rank = position + 1
            entries.append((rank, player, total))
        return entries

    def handle(self, line):
        for name, pattern in COMMANDS.items():
            match = pattern.fullmatch(line)
            if match:
                return getattr(self, "cmd_" + name.lower())(*match.groups())
        return "ERR bad command"

    def cmd_score(self, player, points):
        self.totals[player] = self.totals.get(player, 0) + int(points)
        return f"TOTAL {self.totals[player]}"

    def cmd_rank(self, player):
        if player not in self.totals:
            return UNKNOWN
        total = self.totals[player]
        rank = 1 + sum(1 for t in self.totals.values() if t > total)
        return f"RANK {rank} {total}"

    def cmd_top(self, k):
        return " ".join(["TOP"] + [format_entry(e) for e in self.ranked()[: int(k)]])

    def cmd_around(self, player, d):
        if player not in self.totals:
            return UNKNOWN
        entries = self.ranked()
        i = next(pos for pos, e in enumerate(entries) if e[1] == player)
        d = int(d)
        window = entries[max(0, i - d): i + d + 1]
        return " ".join(["AROUND"] + [format_entry(e) for e in window])

    def cmd_remove(self, player):
        if self.totals.pop(player, None) is None:
            return UNKNOWN
        return "OK"

    def cmd_count(self):
        return f"COUNT {len(self.totals)}"


def format_entry(entry):
    rank, player, total = entry
    return f"{rank}:{player}:{total}"


def main():
    if len(sys.argv) > 1:
        print("usage: leaderboard  (commands on stdin)", file=sys.stderr)
        sys.exit(2)

    board = Leaderboard()
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(board.handle(line) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
