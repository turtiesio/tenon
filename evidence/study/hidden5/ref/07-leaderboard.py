"""Private leaderboard reference, implemented from tasks5/07-leaderboard.md."""
import re
import sys
from common import fail, emit
if len(sys.argv) != 1: fail(2)
name = r'[a-z][a-z0-9_]{0,15}'
forms = [r'SCORE '+name+r' -?[0-9]{1,6}',r'RANK '+name,r'TOP [1-9][0-9]{0,2}',r'AROUND '+name+r' [0-9]{1,3}',r'REMOVE '+name,r'COUNT']
scores = {}
for raw in sys.stdin.buffer:
    line = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
    if not any(re.fullmatch(p,line) for p in forms):
        emit('ERR bad command')
        continue
    t = line.split(' ')
    command = t[0]
    if command == 'SCORE':
        scores[t[1]] = scores.get(t[1],0)+int(t[2])
        response = f'TOTAL {scores[t[1]]}'
    elif command == 'COUNT': response = f'COUNT {len(scores)}'
    elif command in ('RANK','REMOVE','AROUND') and t[1] not in scores: response = 'ERR unknown player'
    elif command == 'REMOVE':
        del scores[t[1]]
        response = 'OK'
    else:
        order = sorted(scores,key=lambda n:(-scores[n],n))
        ranks = {}
        rank = 0
        for i,n in enumerate(order):
            if i == 0 or scores[n] != scores[order[i-1]]: rank = i+1
            ranks[n] = rank
        if command == 'RANK': response = f'RANK {ranks[t[1]]} {scores[t[1]]}'
        else:
            if command == 'TOP': selected = order[:int(t[1])]
            else:
                pos,d = order.index(t[1]),int(t[2])
                selected = order[max(0,pos-d):pos+d+1]
            response = command+''.join(f' {ranks[n]}:{n}:{scores[n]}' for n in selected)
    emit(response)
