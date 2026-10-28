# Spec ambiguities and chosen boundaries

The behavioral sources are the frozen `study/tasks6/*.md` and
`study/README.md`. The hidden5 deliverable supplied the packaging and harness
workflow, not set-6 behavior. No specification was changed, and no submitted
solution or result directory was read.

## Repeated options with an earlier invalid value (02-b64, 03-hsize)

The last repeated width/precision wins, while malformed values are usage
errors. The text does not expressly resolve an invalid setting followed by
a valid setting.

Reference reading: validate every supplied value immediately; valid later
values replace valid earlier values. Acceptance boundary: repetition cases
use valid values throughout; malformed-value cases have no later valid
replacement. Values are always consumed from the next argument, even when
it looks like another option.

## Empty directory argument (09-helpdesk)

The spec gives no meaning for an empty-string DIR. The reference follows
Python `Path('')` semantics, using the current directory. Tests omit this
spelling. A literal `-` and paths containing spaces are ordinary directory
names. Missing parents are errors: creation covers only the last component.
A directory at `DIR/tickets.log` is an unusable journal and gives exit 1.
Permissions, symlinks, disk exhaustion, and injected write failures are not
tested.

## Invalid complete journal prefix followed by a torn suffix (09-helpdesk)

The loading rules describe both fatal invalid complete records, with the
file unchanged, and removal of incomplete final bytes. Chosen reading:
validate all complete records before truncating a suffix. An invalid complete
prefix remains fatal even if a later suffix looks like a valid record or
is torn. Tests repeat startup on these journals. Valid-prefix torn recovery
is tested separately, including an acknowledged append followed by SIGKILL
and another restart.

A complete journal line ending in CRLF is invalid: journal records are in
the exact fixed syntax, with LF after the record, and command CR removal
happens before recording. A command received with CRLF is valid and must
produce a replayable record without its CR. Both distinctions are covered.

## Forest depth and salaries (05-orgchart)

The input domain permits at most 10000 employees and 500 levels. The "Not
required" section excludes handling salaries with more than nine digits and
"depth limits". Reading: valid trees within the stated limits still need to
work; rejection behavior outside those limits is not scored. The suite
includes exactly 500 levels and 10000 employees, with no over-depth or
ten-digit-salary cases. Invalid salary spellings such as signs, decimal
points, and spaces remain invalid under the explicit grammar.

## Scaling and validation scope (04-shoplist)

All recipe and plan records must satisfy their syntax, even if a recipe is
not planned. The exception for unplanned recipes applies only to conflicts
between ingredient kinds. Scaling first converts to base units, then rounds
each plan line separately. The tests distinguish this from rounding before
conversion and from rounding only once after combining plan lines. These
are explicit rules, documented here to make the fixture readings clear.

## Line splitting and exact character comparisons

Only LF splits lines; exactly one trailing CR is removed where specified.
An empty input has no lines, and a final LF does not create an extra line.
An interior empty line is still a line. The service tasks must respond to
such a line with `ERR bad command`. Extra CR bytes are not all stripped.

Byte order, UTF-8 code-point counts, and ASCII whitespace follow the text
literally; there is no Unicode normalization, display-width calculation,
case folding, or Unicode whitespace splitting. Wcx binary inputs without
`-m` may contain invalid UTF-8; inputs selected with `-m` are valid UTF-8.
Base64 encoding/decoding uses bytes. Climate's 40-character station bound
is measured in code points. Fixed command tokens remain in their specified
ASCII domains.

## Observation limits and exclusions

The unchanged harness observes only stdout bytes and exit status; stderr
wording is not compared. It cannot inspect final journal bytes, filesystem
metadata, or prove that an input stream was never read. Usage tests assert
atomic empty stdout and the specified exit, while planted journals and
subsequent restarts assert replay compatibility and observable state.
Repeated invalid startups do not directly prove byte-for-byte preservation
of the journal. Read-only commands, errors and UNCHANGED are followed by
restarts to check that the written journal remains valid.

Every helpdesk kill step sends one complete command at a time, waits for the
specified acknowledged output, then sends SIGKILL. A trailing mutation is
present but never sent. Restarts check state, preserved assignment/title,
open/closed status, queue contents, missing unsent tickets, and next numbers.
No assertion concerns an unacknowledged command, power loss, fsync,
compaction, or concurrent processes. Rooms and Locks have separate lock-step
cases solely to verify their specified per-response flushing; no persistence
between their runs is expected.

Successful test inputs stay within the stated size/count domains. Sand's
31-row/column cases deliberately exercise its explicit invalid-grid rule,
and malformed numeric/name spellings exercise explicit rejection grammars.
The maximum-command Rooms case creates 100 rooms and 9899 simultaneous
bookings in 10000 commands; creating 10000 bookings would itself require
additional ROOM commands and exceed the per-run command limit. Helpdesk's
100000-record/100000-ticket journals are read without further mutations;
a separate 99999-record journal accepts ticket T100000 and is then read
again. No run crosses the journal-record or ticket limit.

The line-per-argument fixture format cannot express LF inside an argument,
and OS arguments cannot contain NUL; neither is needed. No explicitly
excluded feature is required: combined flags are tested only for specified
usage rejection, unsupported units/formats only for specified invalid-input
handling, and no extended task functionality is assumed.
