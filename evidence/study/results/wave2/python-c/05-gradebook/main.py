"""gradebook: join a student roster with assignment scores."""
import re
import sys
from fractions import Fraction

ID_RE = re.compile(r"[A-Za-z0-9]{1,16}")
SECTION_RE = re.compile(r"[A-Z]")
ASSIGNMENT_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")
POINTS_RE = re.compile(r"[0-9]{1,6}")
STUDENTS_HEADER = "id,name,section"
SCORES_HEADER = "id,assignment,points,max"
LETTERS = "ABCDF"


class InputError(Exception):
    pass


class Student:
    def __init__(self, sid, name, section):
        self.id = sid
        self.name = name
        self.section = section
        self.scores = {}  # assignment -> (points, max)

    def totals(self):
        points = sum(p for p, _ in self.scores.values())
        maximum = sum(m for _, m in self.scores.values())
        return points, maximum


def read_data_lines(path, header):
    """Return the non-empty data lines of PATH after checking its header."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("latin-1")
    except OSError as e:
        raise InputError(str(e)) from None
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if not lines or lines[0] != header:
        raise InputError(f"{path}: expected header {header!r}")
    return [line for line in lines[1:] if line != ""]


def parse_student(line):
    fields = line.split(",")
    if len(fields) != 3:
        return None
    sid, name, section = fields
    if not ID_RE.fullmatch(sid) or not 1 <= len(name) <= 40 or not SECTION_RE.fullmatch(section):
        return None
    return Student(sid, name, section)


def parse_score(line):
    fields = line.split(",")
    if len(fields) != 4:
        return None
    sid, assignment, points, maximum = fields
    if not (ID_RE.fullmatch(sid) and ASSIGNMENT_RE.fullmatch(assignment)
            and POINTS_RE.fullmatch(points) and POINTS_RE.fullmatch(maximum)):
        return None
    points, maximum = int(points), int(maximum)
    if maximum < 1 or points > maximum:
        return None
    return sid, assignment, points, maximum


def letter_for(points, maximum):
    for letter, threshold in zip(LETTERS, (90, 80, 70, 60)):
        if 100 * points >= threshold * maximum:
            return letter
    return "F"


def format_percent(points, maximum):
    tenths = (2000 * points + maximum) // (2 * maximum)  # 1000*P/M, half up
    return f"{tenths // 10}.{tenths % 10}"


def main(argv):
    if len(argv) != 2:
        print("usage: gradebook STUDENTS SCORES", file=sys.stderr)
        return 2
    try:
        student_lines = read_data_lines(argv[0], STUDENTS_HEADER)
        score_lines = read_data_lines(argv[1], SCORES_HEADER)
    except InputError as e:
        print(f"gradebook: {e}", file=sys.stderr)
        return 1

    students = {}
    bad_students = bad_scores = orphans = 0
    for line in student_lines:
        student = parse_student(line)
        if student is None or student.id in students:
            bad_students += 1
        else:
            students[student.id] = student

    for line in score_lines:
        score = parse_score(line)
        if score is None:
            bad_scores += 1
            continue
        sid, assignment, points, maximum = score
        student = students.get(sid)
        if student is None:
            orphans += 1
            continue
        student.scores[assignment] = (points, maximum)  # a re-grade replaces the old one

    rows = []
    for student in students.values():
        points, maximum = student.totals()
        ratio = Fraction(points, maximum) if maximum else None
        rows.append((student, points, maximum, ratio))
    rows.sort(key=lambda r: (r[0].section, r[3] is None, -(r[3] or 0), r[0].id))

    out = []
    sections = {}
    for student, points, maximum, ratio in rows:
        counts = sections.setdefault(student.section, dict.fromkeys(LETTERS + "-", 0))
        if ratio is None:
            counts["-"] += 1
            out.append(f"{student.section} {student.id} {student.name} 0/0 - -")
        else:
            letter = letter_for(points, maximum)
            counts[letter] += 1
            out.append(f"{student.section} {student.id} {student.name} "
                       f"{points}/{maximum} {format_percent(points, maximum)}% {letter}")
    for section, counts in sections.items():
        letters = " ".join(f"{letter}={counts[letter]}" for letter in LETTERS)
        out.append(f"section {section}: students={sum(counts.values())} {letters} none={counts['-']}")
    out.append(f"bad_students={bad_students} bad_scores={bad_scores} orphans={orphans}")
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
