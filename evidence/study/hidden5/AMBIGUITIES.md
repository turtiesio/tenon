# Spec ambiguities and chosen boundaries

The only behavioral sources are the frozen `study/tasks5/*.md` and
`study/README.md`. No spec was changed. Tests avoid disputed combinations
when the frozen text does not settle them. Reference implementation choices
are distinguished below from acceptance requirements.

## Repeated options with an earlier invalid value (01-seqx, 03-colalign)

These specs say the last repeated setting wins, while also making malformed
option values usage errors. They do not explicitly say whether a later valid
value rescues an earlier invalid value.

Chosen reference reading: validate every supplied option value immediately;
only valid repeated settings replace prior settings. Test boundary: successful
repetition cases supply valid values throughout. Malformed-value cases do not
supply a later valid replacement. Required next-argument consumption is tested,
including an option-looking literal separator.

## 02-trx — edge dashes versus the mechanical range scan

The range algorithm tests for an unescaped middle dash and otherwise does
not restrict range endpoints. The following explanation also calls a dash
at the very start/end literal and says an escaped dash is always literal.
Unusual combinations such as `--a` as a set, or an escaped dash used as a
range endpoint, can make those statements seem in tension.

Chosen reference reading: follow the specified two-pass token/range algorithm;
escaping marks whether a dash can serve as the range operator. Test boundary:
no leading consecutive unescaped dashes in a set and no escaped-dash range
endpoints. Ordinary start/end dashes, a lone dash, escaped literal dashes,
single-character ranges, range endpoints in ASCII order, reversed ranges,
and the explicit `a-c-e` example are covered. Combined option spellings such
as `-ds` are explicitly excluded by the spec and are not tested.

## 06-libfines — validation of an unmatched loan

The Join rule says unmatched loans are skipped and that all other rules
apply to matched loans. The earlier file-format section independently says
that a record breaking *any* field or day-order rule makes the file invalid.

Chosen reading: validate every record's syntax and day constraints before
the join; skip only a syntactically valid unknown-book loan. The suite includes
both valid skipped loans and an invalid unknown-book loan with due before
out. This follows the explicit file-invalid definition; it does not charge
fines or list members for skipped loans. A returned day after TODAY is valid
and is tested, as the spec explicitly allows it.

## 09-polls — empty DIR and journal filesystem failures

An empty-string DIR is not explicitly assigned a meaning. The private
reference uses Python path semantics (`Path('')` is the current directory),
but the suite excludes that spelling. No arguments and extra arguments are
usage errors; regular-file DIRs and missing/non-directory parents are exit-1
cases. Existing directories, a created last component, spaces, and `-` as a
literal directory name are tested.

The interface explicitly gives exit 1 for an unusable journal. A directory
at `DIR/polls.log` is tested as an unusable journal. Permissions, symlinks,
injected write failures, disk exhaustion and operating-system crashes are
excluded. The reference exits 1 on filesystem I/O errors.

## 09-polls — invalid complete prefix followed by a torn suffix

The startup contract says an invalid journal must be left unchanged, while
loading also describes truncating an incomplete final record. The chosen
reference reading validates all complete records before truncation: an
invalid complete prefix is fatal even when followed by a torn suffix.
The suite tests this exit-1 outcome, and tests valid-prefix torn recovery
separately. It makes no additional assertion about the timing of truncation
on a valid read-only startup; the suffix must be gone before any new append.

## Observation limits and exclusions

The unchanged harness compares only stdout bytes and exit status. It cannot
compare journal bytes or filesystem metadata directly. The suite plants
fixed-format journals and observes replay through RESULT. New mutations
followed by additional restarts verify that torn bytes cannot contaminate
later records. Invalid complete journals are checked on startup, including
a repeated startup of the same invalid journal; unchanged-file bytes are not
directly observable through this protocol.

SIGKILL steps send one complete command at a time and kill only after a
complete acknowledged response. An additional mutation is left unsent in
each killed poll run. No assertion is made about a command sent without an
acknowledgement. Recovery tests cover CREATE, first VOTE, CHANGED, CLOSE,
UNCHANGED, RESULT and errors, with multiple successive restarts and an append
after torn-tail recovery. fsync, power loss, compaction and concurrency are
not required or tested.

All successful computations remain in the stated domains. Malformed syntax
and argument spellings exercise the specified rejection rules. Input size
ceilings are respected. Trx input covers ASCII only, including NUL in stdin
but never in argv (an OS argv cannot contain NUL). The line-per-argument
fixture format cannot represent literal LF inside an argument; no case
requires it. Colalign measures code points, including wide/combining/astral
characters, without requiring display-cell widths. Srtfix does not test tags,
positions or BOMs. Robots use sequential alphabetic action order, with no
pushing or simultaneous-movement semantics. Stderr wording is never compared.
