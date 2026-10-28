# Excluded ambiguous behavior

The suite derives only from `study/tasks2/*.md`. The following behaviors are
excluded; the questions are recorded for future clarification, not resolved by
an acceptance-test expectation.

## 03-datecalc — invalid format replaced by a later format

Quotes: “If `-F` is given more than once, the last one wins.” and “an invalid
FMT (rule 5), even for `weekday` and `diff`” is a usage error.

Question: Must an earlier invalid FMT still cause exit 2 when a later valid
`-F` replaces it, or is only the final effective FMT validated?

Exclusion: Repeated-format tests use valid earlier and final formats. No case
combines an invalid earlier FMT with a valid final one.

## 09-tally — compacting values wider than the log grammar

Quotes: “`<int>` matches `-?[0-9]{1,15}`”, log records use “`S <name> <int>`”,
“COMPACT writes one `S <name> <value>` record per existing counter”, and “All
values stay within ±10^17.”

Question: If ADD produces a value with 16–18 digits, must COMPACT write and
replay that value despite the 15-digit record grammar, or is compaction at
such values outside the intended input domain?

Exclusion: Wide accumulated values are tested with ADD, GET, and replay of
valid ADD records. All counters have at most 15 digits whenever COMPACT is
used. No planted SET record exceeds the log grammar except deliberately
invalid records, which test the unambiguous valid-prefix rule.

## 09-tally — empty DIR argument

Quotes: “Exactly one argument, `DIR`” and “If `DIR` does not exist, create it.
Only the last path component is created.”

Question: Does an empty-string DIR name the working directory or represent an
unusable path that must give exit 1?

Exclusion: No empty DIR argument is tested. Missing parents and a regular file
in place of a directory are tested instead.

## 09-tally — storage failures inside an existing directory

Quotes: “`1` if `DIR` is unusable” and “delete `DIR/tally.log.tmp` if it exists.
It may be left over from a crash and may contain anything.”

Question: What exit/output behavior is required if `tally.log` or
`tally.log.tmp` is a directory, a link, or is unreadable/unwritable, or if an
append, truncation, or rename fails after command processing has started?

Exclusion: Planted log and temporary artifacts are regular files. Permission,
link, and injected I/O failure behavior is not tested. Temporary-file
contents may be arbitrary bytes, as explicitly permitted.

No other unresolved ambiguity affected the chosen cases. Stderr wording,
power loss, concurrency, and other explicitly excluded features are not
asserted.
