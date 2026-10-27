import sys

COLS = 7
ROWS = 6
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.grid = [["."] * COLS for _ in range(ROWS)]  # grid[row][col], row 0 = bottom
        self.heights = [0] * COLS
        self.moves = []  # columns, in order
        self.outcome = None  # None, "WIN" or "DRAW"

    @property
    def player(self):
        return "X" if len(self.moves) % 2 == 0 else "O"

    def count_line(self, row, col, dr, dc, player):
        """Number of consecutive discs of player from (row, col) in direction (dr, dc), excluding it."""
        n = 0
        r, c = row + dr, col + dc
        while 0 <= r < ROWS and 0 <= c < COLS and self.grid[r][c] == player:
            n += 1
            r += dr
            c += dc
        return n

    def wins(self, row, col, player):
        for dc, dr in DIRECTIONS:
            length = (1 + self.count_line(row, col, dr, dc, player)
                      + self.count_line(row, col, -dr, -dc, player))
            if length >= 4:
                return True
        return False

    def drop(self, col):
        if self.outcome is not None:
            return "ERR game over"
        if self.heights[col] == ROWS:
            return "ERR column full"
        player = self.player
        row = self.heights[col]
        self.grid[row][col] = player
        self.heights[col] += 1
        self.moves.append(col)
        response = "PLAYED %s %d" % (player, row + 1)
        if self.wins(row, col, player):
            self.outcome = "WIN"
            response += " WIN"
        elif len(self.moves) == ROWS * COLS:
            self.outcome = "DRAW"
            response += " DRAW"
        return response

    def undo(self):
        if not self.moves:
            return "ERR nothing to undo"
        col = self.moves.pop()
        self.heights[col] -= 1
        self.grid[self.heights[col]][col] = "."
        self.outcome = None
        return "UNDONE %d" % (col + 1)

    def board(self):
        return "/".join("".join(self.grid[r]) for r in range(ROWS - 1, -1, -1))

    def status(self):
        if self.outcome == "WIN":
            # the winner is the player who made the last move
            return "WIN " + ("X" if len(self.moves) % 2 == 1 else "O")
        if self.outcome == "DRAW":
            return "DRAW"
        return "TURN " + self.player

    def execute(self, line):
        if line == "UNDO":
            return self.undo()
        if line == "BOARD":
            return self.board()
        if line == "STATUS":
            return self.status()
        if line == "NEW":
            self.reset()
            return "OK"
        if len(line) == 6 and line.startswith("DROP ") and line[5] in "1234567":
            return self.drop(int(line[5]) - 1)
        return "ERR bad command"


def main():
    if len(sys.argv) > 1:
        print("connect4: takes no arguments", file=sys.stderr)
        return 2
    game = Game()
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(game.execute(line) + "\n")
        sys.stdout.flush()
    return 0


sys.exit(main())
