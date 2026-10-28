# Spec ambiguities and chosen boundaries

The behavioral sources are the frozen `evidence/study/tasks7/*.md` and the
protocol in `evidence/study/README.md`. Hidden6 supplied the deliverable layout
and validation workflow, not set-7 behavior. No specification was changed,
and no submitted solution or study result directory was inspected.

## Repeated options and an earlier invalid value

Numlines, Detab, Reconcile and War say the last repeated value wins, but also
say malformed values are usage errors. They do not expressly settle an
invalid value followed by a valid replacement.

The references validate each supplied value when encountered. Acceptance
cases only repeat valid settings; malformed settings are never followed by
a valid replacement of the same option. Thus the suite does not adjudicate
this ambiguity. Options consume the next argument even if it looks like an
option, as explicitly specified. Settings apply to the entire input after
argument processing, including files that precede an option.

## Empty DIR and filesystem failures (Bookmarks)

No meaning is specified for an empty-string DIR. The reference uses Python
`Path('')` semantics (the current directory), but acceptance cases omit this
spelling. Literal `-` and a directory name containing spaces are ordinary
DIR values. Creation covers only the last component; a missing parent is an
error. Directories in place of `snapshot` or `journal` are unusable data
files. Permissions, symlinks, disk exhaustion and injected write failures
are not tested.

## Torn suffix after an invalid complete prefix (Bookmarks)

Loading describes truncating torn suffixes, while startup failure must leave
all files unchanged. Chosen reading: validate the snapshot and all complete
journal records before truncating a torn suffix. An invalid complete prefix
is fatal regardless of a valid-looking or torn suffix. Such cases are
started twice with no intervening writes. A leftover `snapshot.tmp` may be
deleted on failure, as the spec expressly permits.

Valid torn recovery is tested separately: torn first records and torn TAG,
UNTAG and DEL records are discarded, a new mutation takes the available
sequence number, and later runs replay the resulting data. One new append
is acknowledged and then SIGKILLed before the subsequent restart.

## Journal syntax, overlap and sequence numbers (Bookmarks)

Commands remove one trailing CR; fixed-format files do not have that rule.
A journal record or snapshot row ending in CRLF therefore fails its exact
syntax, while commands received with CRLF produce valid replayable files.
Only the incomplete last journal fragment is ignored. An incomplete snapshot
is invalid.

The journal may start before the snapshot's number, at it, or at S+1,
provided its complete records are consecutive and its last number is at
least S. A missing or empty journal is allowed even when S is positive.
Records numbered at most S must have valid mutation syntax and consecutive
numbers, but their effects are skipped. They are not semantically replayed
against the snapshot. A planted overlap contains syntactically valid commands
that would fail if applied to the loaded snapshot, to distinguish skipping
from replaying. Sequence 0 is invalid for records (numbering starts at 1),
while snapshot number 0 is valid.

Successful ADD, DEL, TAG and UNTAG alone consume sequence numbers. Errors,
UNCHANGED, reads and COMPACT do not. COMPACT's response and later replay
observe this numbering. No assertion depends on a particular choice between
deleting and truncating the journal.

## Literal markers, spaces and names

Bookmark name `-` and URL `-` satisfy their grammars. FIND with the single
matching name `-` has the same bytes as its empty marker; the reference
prints those bytes without escaping. Tags cannot contain `-`.

Vfs WRITE text is everything after the path delimiter, so leading, trailing
and repeated spaces in the text are preserved. A one-space text is valid;
a zero-length text is not. Other command spacing is exact. Paths are walked
component by component: a missing intermediate component followed by `..`
does not disappear lexically, and `file/.` or `file/..` fails as not a
directory. These are explicit rules, recorded here because common path
normalization APIs can produce different behavior.

## LF splitting, CR handling and input limits

Only LF splits input. Empty input has no lines; a final LF creates no extra
empty line; interior empty lines remain lines. Exactly one final CR is
removed where specified. Numlines preserves CR as an ordinary input byte.
Detab preserves it and counts it as one column. UTF-8 code points, including
combining marks, each count as one Detab column; no display-width behavior
is assumed.

Limits are ceilings on valid inputs, not requirements to test unspecified
rejection beyond them. All command counts, journal counts, bookmark counts,
path lengths, expanded line lengths and successful arithmetic stay within
the stated ceilings. Deliberately malformed bounded fields (for example a
53-card War deck, a 101-character Vfs text, or a 20-digit Luhn check value) exercise
explicit invalid-input rules; no run exceeds a command, journal or input-line
count ceiling. Costbasis lots remain below 10^9 in both quantity and cost;
Numlines numbers remain within +/-10^12. War output remains below 1 MB.

Features in the specs' Not required sections are not required for success.
Where the frozen text itself explicitly requires syntax rejection (for
example lower-case ISBN `x`, malformed signed quantities or invalid flags),
that rejection is tested. There are no requirements to support extra
schemes, quoted CSV, headers, IPv6, display widths, optimal vending change,
recursive removal, power-loss durability or repeated-position detection.

## What the harness can observe

The unchanged harness compares stdout bytes and exit status only. Stderr is
captured but never compared. It cannot directly inspect final snapshot or
journal bytes, prove that stdin was not read, or prove byte-for-byte
preservation after invalid startup. Planted fixed-format data, COMPACT
sequence responses, repeated startups and later commands check observable
compatibility and recovery instead.

Every kill step supplies complete commands in lock-step, waits for the
acknowledged response, then sends SIGKILL without sending the trailing
mutation. Restarts check exactly the acknowledged state. No assertion
concerns an unacknowledged mutation or a particular crash timing inside
COMPACT; planted snapshot/journal overlap models the specified interrupted
rename/truncate window. Vending and Vfs each have one independent lock-step
case to test flushing, with fresh in-memory state on the next run.

The fixture format cannot encode LF inside a single argument, and operating
systems cannot encode NUL in argv. Neither is needed for this suite.
