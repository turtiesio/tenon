import re
import sys
from dataclasses import dataclass, field


@dataclass
class Team:
    name: str
    wins: int = 0
    draws: int = 0
    losses: int = 0
    gf: int = 0
    ga: int = 0
    form: list = field(default_factory=list)

    def ranking(self, points):
        return (sum(a * b for a, b in zip((self.wins, self.draws, self.losses), points)), self.gf - self.ga, self.gf, self.wins)


def main():
    args = sys.argv[1:]
    points = (3, 1, 0)
    if args:
        if len(args) != 2 or args[0] != '-p' or not re.fullmatch(r'[0-9]{1,2},[0-9]{1,2},[0-9]{1,2}', args[1]):
            print('invalid arguments', file=sys.stderr)
            return 2
        points = tuple(map(int, args[1].split(',')))
    teams = {}
    for line_number, raw in enumerate(sys.stdin.buffer.read().split(b'\n'), 1):
        raw = raw.removesuffix(b'\r')
        if not raw.strip(b' ') or raw.startswith(b'#'):
            continue
        try:
            tokens = raw.decode('ascii').split(' ')
            scores = [i for i, token in enumerate(tokens) if re.fullmatch('[0-9]{1,2}-[0-9]{1,2}', token)]
            if len(scores) != 1:
                raise ValueError()
            i = scores[0]
            if i == 0 or i == len(tokens) - 1 or any(not re.fullmatch("[A-Za-z0-9.&']+", t) for j, t in enumerate(tokens) if j != i):
                raise ValueError()
            home, away = ' '.join(tokens[:i]), ' '.join(tokens[i+1:])
            if home == away:
                raise ValueError()
            hg, ag = map(int, tokens[i].split('-'))
        except (ValueError, UnicodeError):
            print(f'invalid result on line {line_number}', file=sys.stderr)
            return 1
        for name, gf, ga in ((home, hg, ag), (away, ag, hg)):
            team = teams.setdefault(name, Team(name))
            team.gf += gf
            team.ga += ga
            if gf > ga:
                team.wins += 1
                result = 'W'
            elif gf == ga:
                team.draws += 1
                result = 'D'
            else:
                team.losses += 1
                result = 'L'
            team.form.append(result)
    if not teams:
        return 0
    width = max(map(len, teams))
    ordered = sorted(teams.values(), key=lambda t: (*(-v for v in t.ranking(points)), t.name))
    previous = None
    position = 0
    for index, team in enumerate(ordered, 1):
        ranking = team.ranking(points)
        if ranking != previous:
            position = index
        previous = ranking
        pts, gd, _, _ = ranking
        gd_text = f'{gd:+d}' if gd else '0'
        played = team.wins + team.draws + team.losses
        print(f'{position:2}. {team.name:<{width}}{played:3}{team.wins:3}{team.draws:3}{team.losses:3}{str(team.gf) + ":" + str(team.ga):>7}{gd_text:>4}{pts:4} {"".join(team.form[-5:])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
