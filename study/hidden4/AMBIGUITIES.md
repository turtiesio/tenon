# Spec ambiguities and chosen boundaries

The suite derives from the frozen `study/tasks4/*.md` and the protocol in
`study/README.md`. No spec was changed. Disputed combinations below are
excluded from scoring; each private reference's reading is stated separately.

## 01-hexdump and 02-uniqx — invalid option superseded later

Both specs process arguments left to right and say that the last repeated
value wins. Their usage errors also include malformed option values.

Question: does a later valid value rescue an earlier malformed value?

Chosen reference reading: validate every supplied value; the last valid
occurrence controls the setting. Suite boundary: successful repetition cases
use valid values throughout. Malformed-value cases have no later valid
replacement. Option-looking arguments consumed as values are tested as
usage errors, as explicitly required. Icalc's repeated definitions also use
valid definitions throughout.

## 09-shorten — empty directory argument

The interface takes exactly one DIR argument and creates only its last path
component when absent. It does not explicitly assign a meaning to an empty
path.

Chosen reference reading: the empty path is unusable and exits 1. Suite
boundary: an empty-string DIR is not tested. No arguments and extra
arguments are exit 2; a regular file used as DIR, a missing parent, and a
regular file used as a parent are exit 1. Existing parent directories,
spaces in DIR, and a DIR spelled `-` are tested.

## 09-shorten — journal object conflicts and write failures

The specified exit-1 condition names an unusable DIR. The spec fixes the
journal format and recovery of malformed records, but does not specify
responses to an unreadable journal, a directory at `DIR/journal`, failed
appends, or a failed truncation after successful directory startup.

Chosen reference reading: an operating-system error exits 1 without
acknowledging a failed mutation. Suite boundary: planted journals are regular
files. Permission manipulation, symlinks, journal paths that are directories,
and injected I/O failures are excluded. Malformed contents of readable
regular journals are tested through prefix recovery, never as startup errors.

## Recovery observations and explicit exclusions

The reference truncates an invalid suffix on startup. The spec permits
waiting until the next append. The suite accepts either behavior: it checks
visible replay state, then appends and restarts to check that the suffix was
removed. The harness does not compare filesystem bytes, so exact record bytes
written by a program are observed indirectly through subsequent replay and
INFO. Tests plant journals in the fixed format to check compatibility.

Crash tests send one command at a time and kill only after its complete
response line. Trailing input remains unsent. There is no assumption about a
command whose input was received but whose response was not printed. No
power-loss, fsync, concurrency, or compaction behavior is tested.

Inputs use ASCII text where the specs require ASCII; hexdump exercises all
256 byte values. Malformed ASCII command/record fields are tested where
explicit rejection is required. Valid inputs stay within all stated byte,
line, request, command and journal limits. Malformed numerical spellings
exercise the explicitly specified validation rules. There are no tests of
out-of-domain successful computations. Stderr wording is never compared.
Mdtoc tests use the specified ATX/fence rules and do not require Setext,
indented headings/fences, tilde fences, or closing-hash normalization.
