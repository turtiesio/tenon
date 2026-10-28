# Ambiguities and excluded behavior

These questions were identified from the frozen specs. The cases do not assert
an answer to any question below. No submitted solution or language-specific
implementation was inspected.

1. **06-kvtx — negative zero.** Quote (Integers): “matches
   `-?(0|[1-9][0-9]*)`” and “(`-0`, `+5`, `007` and
   `9999999999999999` are not integers.)”
   **Question:** Should `-0` follow the grammar, which accepts it, or the
   explicit exclusion? Neither stored `-0` values nor `-0` deltas are tested.
   The private reference follows the explicit exclusion.

2. **01-wordfreq, 03-fcut, 04-salesreport, 05-latency, 10-jobsched — repeated
   options with an invalid earlier value.** Quotes: “When an option is given
   more than once, the last one wins” (01, 03); “If an option is repeated,
   the last one wins” (04); “a repeated option's last value wins” (05);
   “If it is repeated, the last one wins” (10). Each also requires a usage
   error for invalid option values.
   **Question:** Does a later valid occurrence rescue an earlier invalid
   value, or must every occurrence validate? Repetition cases use only valid
   occurrences; invalid-value cases do not supply a later replacement.

3. **03-fcut — ASCII delimiters unavailable in argv fixtures.** Quote:
   “The input delimiter: exactly one ASCII character.” The protocol also
   says `cmd` has “one argument per line,” with “no quoting or escaping.”
   **Question:** Does the delimiter domain include NUL and LF? NUL cannot
   be passed through an OS argument, and LF cannot be expressed in this
   fixture format. Those delimiters are not tested. Ordinary CR in input
   fields is tested, as explicitly required.

4. **04-salesreport, 05-latency — dash-prefixed file names.** Quotes:
   “Exactly one `FILE` is required” (04), “If `FILE` is given, read it” (05),
   and “an unknown option” is a usage error in both.
   **Question:** Is a literal `-` a file name, an unknown option, or stdin;
   and how are other dash-prefixed file names distinguished from options?
   Neither task defines a stdin marker or end-of-options marker. Cases for
   these tasks use ordinary file names; latency's implicit stdin is tested.

## Layout reconciliation

The README shows `hidden/<task-id>/<case-name>/`; the task assignment explicitly
requests `hidden/<task-id>/cases/<case-name>/`. Fixtures use the assignment's
`cases/` directory and preserve the README's exact files and step semantics.
The runner accepts both layouts. This affects discovery only, not scoring.

## Explicit exclusions from the frozen specs

No tests require particular stderr text, repeated stdin reads in wordfreq,
Unicode word boundaries, non-ASCII fcut delimiters, multiline CSV fields,
calendar validation of latency timestamps, semantically invalid ledger logs,
modified/corrupt queue.snap files, power-loss durability, or concurrent access.
Queue recovery fixtures plant arbitrary bytes only in `queue.snap.tmp*` files,
whose content the spec explicitly allows to be arbitrary.
