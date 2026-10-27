# Spec ambiguities and chosen boundaries

The suite derives only from `study/tasks3/*.md`. These questions are recorded
without changing the frozen specs. Where two readings could change scoring,
the disputed combination is excluded; the reading used by the private
reference is stated separately. No acceptance expectation depends on those
excluded combinations.

## 02-radix, 04-csvjoin and 10-cachesim — invalid option replaced later

Quotes:

- radix: “If an option is given more than once, the last one wins.” Its usage
  errors include “A malformed or out-of-range option value”.
- csvjoin: “If `-k` is repeated, the last one wins.” Its usage errors include
  “an empty NAME”.
- cachesim: “if an option is repeated, the last one wins”; usage errors
  include “a malformed or out-of-range value”.

Question: Does a malformed earlier value still cause a usage error if a
later valid occurrence replaces it?

Chosen reference reading: validate every supplied option value; repetition
changes which valid value is effective. Suite boundary: repeated-option
success cases use valid values throughout. Invalid option cases have no
later valid replacement. The suite also tests that an option consumes its
following argument even when it looks like another option.

## 09-todo — empty DIR argument

Quotes: “Exactly one argument, `DIR`” and “If `DIR` does not exist, create it.
Only the last path component is created.”

Question: Does an empty-string DIR refer to the working directory, or is it
an unusable path?

Chosen reference reading: an empty path is unusable (exit 1). Suite boundary:
no empty DIR argument is tested. No arguments and extra arguments are tested
as exit 2; missing parents and a regular file used as DIR are tested as exit
1. Paths with spaces and a path starting with `-` are valid DIR arguments.

## 09-todo — exhaustion of the nine-digit persisted counter

Quotes: “next ... starts at 1 and only ever increases”; state line 2 has
“n matching `[1-9][0-9]{0,8}`”; ids are assigned from `next`, and each stored
item id is “smaller than `n`”.

Question: What should ADD do when next is already 999999999? Assigning that
id would require writing the ten-digit next value 1000000000, which violates
the fixed snapshot grammar. No exhaustion response is specified.

Chosen suite reading: test operations that remain representable in the
fixed grammar. The boundary case starts at next=999999998, assigns that id,
and verifies next=999999999 across restart. It does not ADD again at that
point. The reference implements ordinary incrementing; behavior after
exhaustion is outside this suite's scoring domain.

## 09-todo — internal storage object conflicts and I/O failures

Quotes: exit 1 applies “if `DIR` or `todo.db` is unusable”; the temporary
“file ... may contain anything” and “is deleted and never affects the state”.

Question: What exact behavior is required if `todo.db.tmp` is a directory or
link, the database cannot be read, or writing/closing/renaming fails during a
command? Startup handling and command acknowledgement during such failures
are not fully defined.

Chosen reference reading: storage errors are exit 1 with no successful
acknowledgement for the failed write. Suite boundary: all planted database
and temporary artifacts are regular files. Permissions, symlinks, directory
objects at the two storage paths, and injected I/O failures are excluded.
Malformed regular database files, an unusable DIR, and arbitrary bytes in a
regular temporary file are tested. A deleted temporary-file path is later
used as a new DIR to observe its removal through the normal interface.

## 03-globgrep — adjacent stars versus the explicit exclusion

Quotes: “`*` matches any sequence of characters” and “Not required: `**`”.

Question: Does the exclusion mean only recursive-directory globstar syntax,
or does it also exclude two adjacent ordinary stars?

Chosen suite reading: avoid adjacent stars altogether. The performance case
uses 19 stars separated by literal `a` characters, so it exercises the
explicit polynomial-time requirement without depending on this question.
The reference treats every star as an ordinary sequence wildcard.

## Other explicit boundaries

“1 MB” can mean decimal or binary units. The largest wrap input and CSV file
are exactly 1000000 bytes, within both readings. The suite does not test
inputs above the stated limits, CSV lone CR outside quotes, non-ASCII glob
input, power loss, concurrency, stderr wording, or other expressly excluded
features. Malformed bytes are used only where invalid-input/invalid-command
behavior is explicitly specified (wrap and todo).
