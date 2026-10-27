"""Private connect4 reference, implemented from tasks5/08-connect4.md."""
import re
import sys
from common import fail, emit
if len(sys.argv) != 1: fail(2)
board = [['.']*7 for _ in range(6)]
history = []
finished = None
for raw in sys.stdin.buffer:
    line = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
    if line == 'NEW':
        board = [['.']*7 for _ in range(6)]
        history = []
        finished = None
        response = 'OK'
    elif line == 'BOARD': response = '/'.join(''.join(row) for row in reversed(board))
    elif line == 'STATUS': response = finished or ('TURN '+('X' if len(history)%2 == 0 else 'O'))
    elif line == 'UNDO':
        if not history: response = 'ERR nothing to undo'
        else:
            c,r = history.pop()
            board[r][c] = '.'
            finished = None
            response = f'UNDONE {c+1}'
    elif re.fullmatch(r'DROP [1-7]',line):
        c = int(line[-1])-1
        if finished: response = 'ERR game over'
        elif board[5][c] != '.': response = 'ERR column full'
        else:
            r = next(i for i in range(6) if board[i][c] == '.')
            player = 'X' if len(history)%2 == 0 else 'O'
            board[r][c] = player
            history.append((c,r))
            win = False
            for dx,dy in ((1,0),(0,1),(1,1),(1,-1)):
                count = 1
                for sign in (-1,1):
                    x,y = c+sign*dx,r+sign*dy
                    while 0 <= x < 7 and 0 <= y < 6 and board[y][x] == player:
                        count += 1
                        x,y = x+sign*dx,y+sign*dy
                win |= count >= 4
            suffix = ''
            if win:
                finished = 'WIN '+player
                suffix = ' WIN'
            elif len(history) == 42:
                finished = 'DRAW'
                suffix = ' DRAW'
            response = f'PLAYED {player} {r+1}'+suffix
    else: response = 'ERR bad command'
    emit(response)
