import re
import sys

PLAYER = r'[a-z][a-z0-9_]{0,15}'
COMMAND = re.compile(
    rf'SCORE {PLAYER} -?[0-9]{{1,6}}|RANK {PLAYER}|TOP [1-9][0-9]{{0,2}}|'
    rf'AROUND {PLAYER} [0-9]{{1,3}}|REMOVE {PLAYER}|COUNT'
)


class Leaderboard:
    def __init__(self):
        self.scores = {}

    def respond(self, line):
        if not COMMAND.fullmatch(line):
            return 'ERR bad command'
        parts = line.split(' ')
        command = parts[0]
        if command == 'COUNT':
            return f'COUNT {len(self.scores)}'
        if command == 'SCORE':
            player = parts[1]
            self.scores[player] = self.scores.get(player, 0) + int(parts[2])
            return f'TOTAL {self.scores[player]}'
        if command != 'TOP' and parts[1] not in self.scores:
            return 'ERR unknown player'
        if command == 'REMOVE':
            del self.scores[parts[1]]
            return 'OK'
        if command == 'RANK':
            total = self.scores[parts[1]]
            rank = 1 + sum(score > total for score in self.scores.values())
            return f'RANK {rank} {total}'
        order = sorted(self.scores, key=lambda player: (-self.scores[player], player))
        entries = []
        rank = 0
        previous = None
        for index, player in enumerate(order):
            total = self.scores[player]
            if total != previous:
                rank = index + 1
            entries.append(f'{rank}:{player}:{total}')
            previous = total
        if command == 'TOP':
            selected = entries[:int(parts[1])]
        else:
            index = order.index(parts[1])
            distance = int(parts[2])
            selected = entries[max(0, index - distance):index + distance + 1]
        return ' '.join([command, *selected])


if __name__ == '__main__':
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        sys.exit(2)
    board = Leaderboard()
    for raw in sys.stdin.buffer:
        line = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
        print(board.respond(line), flush=True)
