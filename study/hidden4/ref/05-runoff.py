"""Private specification reference: deterministic instant runoff."""
import re
import sys

def main():
    if len(sys.argv) != 1:
        print('usage error', file=sys.stderr); return 2
    rows = sys.stdin.buffer.read().decode('ascii').split('\n')
    if rows[-1] == '': rows.pop()
    lines = []
    for line in rows:
        if line.endswith('\r'): line = line[:-1]
        if not line.strip(' ') or line.startswith('#'): continue
        lines.append(line)
    if not lines or not re.fullmatch(r'candidates:( [A-Za-z][A-Za-z0-9_]{0,19}){1,20}', lines[0]):
        print('invalid header', file=sys.stderr); return 1
    names = lines[0].split(' ')[1:]
    if len(set(names)) != len(names):
        print('invalid header', file=sys.stderr); return 1
    ballots, invalid = [], 0
    for line in lines[1:]:
        items = line.split('>')
        if len(set(items)) != len(items) or any(x not in names for x in items): invalid += 1
        else: ballots.append(items)
    print(f'ballots={len(ballots)} invalid={invalid}')
    continuing = names[:]
    round_number = 0
    while True:
        round_number += 1
        votes = dict.fromkeys(continuing, 0)
        exhausted = 0
        for ballot in ballots:
            for x in ballot:
                if x in votes: votes[x] += 1; break
            else: exhausted += 1
        print(f'round {round_number}: '+ ' '.join(f'{x}={votes[x]}' for x in continuing) + f' exhausted={exhausted}')
        winners = [x for x in continuing if 2*votes[x] > len(ballots)-exhausted]
        if winners or len(continuing) == 1:
            print('winner: '+(winners[0] if winners else continuing[0])); break
        weakest = min(votes.values())
        eliminated = [x for x in continuing if votes[x] == weakest][-1]
        print('eliminated: '+eliminated)
        continuing.remove(eliminated)
    return 0
if __name__ == '__main__': sys.exit(main())
