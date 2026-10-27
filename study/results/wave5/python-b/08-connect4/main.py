import re
import sys


class Game:
    def __init__(self):
        self.columns = [[] for _ in range(7)]
        self.history = []
        self.result = None

    def cell(self, column, row):
        if 0 <= column < 7 and 0 <= row < len(self.columns[column]):
            return self.columns[column][row]
        return '.'

    def wins(self, column, row, player):
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            count = 1
            for direction in (-1, 1):
                x, y = column + direction * dx, row + direction * dy
                while self.cell(x, y) == player:
                    count += 1
                    x += direction * dx
                    y += direction * dy
            if count >= 4:
                return True
        return False

    def respond(self, command):
        if command == 'NEW':
            self.__init__()
            return 'OK'
        if command == 'BOARD':
            return '/'.join(''.join(self.cell(c, r) for c in range(7)) for r in range(5, -1, -1))
        if command == 'STATUS':
            return self.result or f"TURN {'X' if len(self.history) % 2 == 0 else 'O'}"
        if command == 'UNDO':
            if not self.history:
                return 'ERR nothing to undo'
            column = self.history.pop()
            self.columns[column].pop()
            self.result = None
            return f'UNDONE {column + 1}'
        if not re.fullmatch(r'DROP [1-7]', command):
            return 'ERR bad command'
        if self.result:
            return 'ERR game over'
        column = int(command[-1]) - 1
        row = len(self.columns[column])
        if row == 6:
            return 'ERR column full'
        player = 'X' if len(self.history) % 2 == 0 else 'O'
        self.columns[column].append(player)
        self.history.append(column)
        suffix = ''
        if self.wins(column, row, player):
            self.result = f'WIN {player}'
            suffix = ' WIN'
        elif len(self.history) == 42:
            self.result = 'DRAW'
            suffix = ' DRAW'
        return f'PLAYED {player} {row + 1}{suffix}'


if __name__ == '__main__':
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        sys.exit(2)
    game = Game()
    for raw in sys.stdin.buffer:
        command = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
        print(game.respond(command), flush=True)
