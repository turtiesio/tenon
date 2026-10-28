from collections import deque
import re
import sys

RANKS = {card: rank for rank, card in enumerate('23456789TJQKA')}


def main():
    maximum, quiet = 1000, False
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-q':
                quiet = True
            elif arg == '-n':
                value = next(args)
                if not re.fullmatch(r'[1-9][0-9]{0,5}', value):
                    raise ValueError('invalid round limit')
                maximum = int(value)
            else:
                raise ValueError('unknown argument')
    except (ValueError, StopIteration) as exc:
        print('usage error:', exc, file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read().decode('ascii')
    lines = data.split('\n')
    if data.endswith('\n'):
        lines.pop()
    lines = [line.removesuffix('\r') for line in lines]
    if len(lines) != 2 or any(not re.fullmatch(r'[23456789TJQKA]{1,52}', line) for line in lines):
        print('invalid input', file=sys.stderr)
        return 1
    a, b = map(deque, lines)
    for round_number in range(1, maximum+1):
        face_a, face_b = [a.popleft()], [b.popleft()]
        pile = [face_a[0], face_b[0]]
        incomplete = False
        while face_a[-1] == face_b[-1]:
            if len(a) < 4 or len(b) < 4:
                incomplete = True
                break
            drawn_a = [a.popleft() for _ in range(4)]
            drawn_b = [b.popleft() for _ in range(4)]
            pile.extend(drawn_a)
            pile.extend(drawn_b)
            face_a.append(drawn_a[-1])
            face_b.append(drawn_b[-1])
        if incomplete:
            winner = '-'
        elif RANKS[face_a[-1]] > RANKS[face_b[-1]]:
            winner = 'A'
            a.extend(pile)
        else:
            winner = 'B'
            b.extend(pile)
        if not quiet:
            print(f'{round_number} {"/".join(face_a)} {"/".join(face_b)} {winner} {len(a)} {len(b)}')
        if incomplete or not a or not b:
            if incomplete:
                result = 'A' if len(a) > len(b) else 'B' if len(b) > len(a) else None
            else:
                result = 'A' if a else 'B'
            print(f'{result} wins in round {round_number}' if result else f'draw in round {round_number}')
            return 0
    print(f'stopped at round {maximum}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
