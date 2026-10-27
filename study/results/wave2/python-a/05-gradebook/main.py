#!/usr/bin/env python3
"""gradebook: join a student roster with assignment scores and report grades."""

import re
import sys
from dataclasses import dataclass, field
from fractions import Fraction

ID_RE = re.compile(r"[A-Za-z0-9]{1,16}")
SECTION_RE = re.compile(r"[A-Z]")
ASSIGNMENT_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")
POINTS_RE = re.compile(r"[0-9]{1,6}")

STUDENTS_HEADER = "id,name,section"
SCORES_HEADER = "id,assignment,points,max"

# (letter, minimum percentage) in descending order.
LETTER_CUTOFFS = [("A", 90), ("B", 80), ("C", 70), ("D", 60)]
LETTERS = "ABCDF"


@dataclass
class Student:
    id: str
    name: str
    section: str
    scores: dict = field(default_factory=dict)  # assignment -> (points, max)

    @property
    def points(self):
        return sum(p for p, _ in self.scores.values())

    @property
    def max_points(self):
        return sum(m for _, m in self.scores.values())

    @property
    def letter(self):
        """Letter grade from the exact ratio, or None without assignments."""
        p, m = self.points, self.max_points
        if m == 0:
            return None
        for letter, cutoff in LETTER_CUTOFFS:
            if 100 * p >= cutoff * m:
                return letter
        return "F"

    @property
    def percent_text(self):
        """100 * P / M, rounded half up to one decimal place."""
        p, m = self.points, self.max_points
        tenths = (2000 * p + m) // (2 * m)
        return f"{tenths // 10}.{tenths % 10}"


def read_lines(path, header):
    """Return the data lines of a file; raise ValueError on a bad header."""
    with open(path, "rb") as f:
        text = f.read().decode("latin-1")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    lines = [l[:-1] if l.endswith("\r") else l for l in lines]
    if not lines or lines[0] != header:
        raise ValueError(f"{path}: missing header {header!r}")
    return [l for l in lines[1:] if l != ""]


def parse_student(line):
    fields = line.split(",")
    if len(fields) != 3:
        return None
    sid, name, section = fields
    if not (ID_RE.fullmatch(sid) and 1 <= len(name) <= 40 and SECTION_RE.fullmatch(section)):
        return None
    return Student(sid, name, section)


def parse_score(line):
    """Return (id, assignment, points, max) or None if malformed."""
    fields = line.split(",")
    if len(fields) != 4:
        return None
    sid, assignment, points, maximum = fields
    if not (
        ID_RE.fullmatch(sid)
        and ASSIGNMENT_RE.fullmatch(assignment)
        and POINTS_RE.fullmatch(points)
        and POINTS_RE.fullmatch(maximum)
    ):
        return None
    points, maximum = int(points), int(maximum)
    if maximum < 1 or points > maximum:
        return None
    return sid, assignment, points, maximum


def rank_key(student):
    m = student.max_points
    if m == 0:
        return (student.section, 1, Fraction(0), student.id.encode())
    return (student.section, 0, -Fraction(student.points, m), student.id.encode())


def main(argv):
    if len(argv) != 2:
        print("usage: gradebook STUDENTS SCORES", file=sys.stderr)
        return 2
    try:
        student_lines = read_lines(argv[0], STUDENTS_HEADER)
        score_lines = read_lines(argv[1], SCORES_HEADER)
    except (OSError, ValueError) as e:
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
        parsed = parse_score(line)
        if parsed is None:
            bad_scores += 1
            continue
        sid, assignment, points, maximum = parsed
        student = students.get(sid)
        if student is None:
            orphans += 1
        else:
            student.scores[assignment] = (points, maximum)  # last one wins

    out = []
    ranked = sorted(students.values(), key=rank_key)
    for s in ranked:
        if s.max_points == 0:
            out.append(f"{s.section} {s.id} {s.name} 0/0 - -")
        else:
            out.append(
                f"{s.section} {s.id} {s.name} {s.points}/{s.max_points} "
                f"{s.percent_text}% {s.letter}"
            )

    sections = sorted({s.section for s in ranked})
    for section in sections:
        members = [s for s in ranked if s.section == section]
        counts = {letter: sum(1 for s in members if s.letter == letter) for letter in LETTERS}
        none = sum(1 for s in members if s.letter is None)
        out.append(
            f"section {section}: students={len(members)} "
            + " ".join(f"{letter}={counts[letter]}" for letter in LETTERS)
            + f" none={none}"
        )

    out.append(f"bad_students={bad_students} bad_scores={bad_scores} orphans={orphans}")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
