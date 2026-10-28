import re
import sys

COLUMNS, ROWS = 7, 6
DROP_RE = re.compile(r"DROP ([1-7])")
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


class Game:
    def __init__(self):
        self.new()

    def new(self):
        # columns[c] holds the discs of column c from the bottom up
        self.columns = [[] for _ in range(COLUMNS)]
        self.history = []
        self.result = None  # None while running, else "WIN X", "WIN O" or "DRAW"

    def to_move(self):
        return "X" if len(self.history) % 2 == 0 else "O"

    def cell(self, c, r):
        if 0 <= c < COLUMNS and 0 <= r < len(self.columns[c]):
            return self.columns[c][r]
        return None

    def wins(self, c, r):
        player = self.columns[c][r]
        for dc, dr in DIRECTIONS:
            length = 1
            for sign in (1, -1):
                k = 1
                while self.cell(c + sign * k * dc, r + sign * k * dr) == player:
                    length += 1
                    k += 1
            if length >= 4:
                return True
        return False

    def drop(self, c):
        if self.result:
            return "ERR game over"
        column = self.columns[c]
        if len(column) == ROWS:
            return "ERR column full"
        player = self.to_move()
        column.append(player)
        self.history.append(c)
        response = f"PLAYED {player} {len(column)}"
        if self.wins(c, len(column) - 1):
            self.result = f"WIN {player}"
            response += " WIN"
        elif len(self.history) == COLUMNS * ROWS:
            self.result = "DRAW"
            response += " DRAW"
        return response

    def undo(self):
        if not self.history:
            return "ERR nothing to undo"
        c = self.history.pop()
        self.columns[c].pop()
        self.result = None
        return f"UNDONE {c + 1}"

    def board(self):
        rows = []
        for r in range(ROWS - 1, -1, -1):
            rows.append("".join(self.cell(c, r) or "." for c in range(COLUMNS)))
        return "/".join(rows)

    def status(self):
        return self.result or f"TURN {self.to_move()}"

    def handle(self, line):
        match = DROP_RE.fullmatch(line)
        if match:
            return self.drop(int(match.group(1)) - 1)
        if line == "UNDO":
            return self.undo()
        if line == "BOARD":
            return self.board()
        if line == "STATUS":
            return self.status()
        if line == "NEW":
            self.new()
            return "OK"
        return "ERR bad command"


def main():
    if len(sys.argv) > 1:
        print("usage: connect4  (commands on stdin)", file=sys.stderr)
        sys.exit(2)

    game = Game()
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(game.handle(line) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
