import re
import sys


def main():
    if len(sys.argv) != 1:
        print('No arguments allowed', file=sys.stderr)
        return 2
    lines = []
    for line in sys.stdin.buffer.read().decode('utf-8', errors='replace').split('\n'):
        if line.endswith('\r'):
            line = line[:-1]
        if line.strip(' ') and not line.startswith('#'):
            lines.append(line)
    pattern = r'candidates:(?: [A-Za-z][A-Za-z0-9_]{0,19}){1,20}'
    if not lines or not re.fullmatch(pattern, lines[0]):
        print('Invalid candidates line', file=sys.stderr)
        return 1
    candidates = lines[0].split(' ')[1:]
    if len(set(candidates)) != len(candidates):
        print('Duplicate candidate', file=sys.stderr)
        return 1
    names = set(candidates)
    ballots = []
    invalid = 0
    for line in lines[1:]:
        ballot = line.split('>')
        if len(set(ballot)) != len(ballot) or any(name not in names for name in ballot):
            invalid += 1
        else:
            ballots.append(ballot)
    print(f'ballots={len(ballots)} invalid={invalid}')
    continuing = candidates.copy()
    round_number = 1
    while True:
        counts = dict.fromkeys(continuing, 0)
        exhausted = 0
        for ballot in ballots:
            for name in ballot:
                if name in counts:
                    counts[name] += 1
                    break
            else:
                exhausted += 1
        report = ' '.join(f'{name}={counts[name]}' for name in continuing)
        print(f'round {round_number}: {report} exhausted={exhausted}')
        active = len(ballots) - exhausted
        winner = next((name for name in continuing if counts[name] * 2 > active), None)
        if winner is not None or len(continuing) == 1:
            print('winner: ' + (winner or continuing[0]))
            break
        eliminated = min(reversed(continuing), key=counts.get)
        print('eliminated: ' + eliminated)
        continuing.remove(eliminated)
        round_number += 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
