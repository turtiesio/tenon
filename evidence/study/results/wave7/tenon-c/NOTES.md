# Study notes

## 01-numlines (done)
- No documentation gaps or compiler errors encountered. The documented distinction between `lines()` and `split("\n")` was essential for preserving carriage returns.
- Wish: a reusable command-line option parser would avoid repetitive validation and dispatch.

## 02-checkdigit (done)
- No missing documentation or confusing compiler errors encountered.
- Wish: byte iteration with offsets without materializing `bytes().enumerate()` would make validation more direct.

## 03-detab (done)
- No documentation gaps or compiler errors encountered. `chars()` and the documented code-point column semantics were sufficient.
- Wish: a streaming character iterator would avoid allocating a list of one-character strings for the whole input.

## 04-cidrmerge (done)
- No documentation gaps or confusing compiler errors encountered.
- Wish: bitwise integer operations would express network masks and alignment directly; arithmetic with powers of two worked correctly.

## 05-reconcile (done)
- No documentation gaps or confusing compiler errors encountered; regex captures and `fmt_fixed` made validation and exact cents straightforward.
- Wish: standard Gregorian date parsing and day arithmetic would remove handwritten calendar validation.

## 06-costbasis (done)
- No missing documentation or confusing compiler errors encountered. Deep mutation of map/list/struct entries worked as documented.
- Wish: a deque or queue type for FIFO lots, because removing the first list element is documented as O(n).

## 07-vending (done)
- No documentation gaps or confusing compiler errors encountered. Copy-on-write values made tentative coin deductions and rollback simple.
- Wish: reusable compiled command patterns as fields or a lightweight parser abstraction would keep protocol dispatch less repetitive. The current implementation recompiles its small patterns per command; limits are small enough for this task.

## 08-vfs (done)
- First compiler error: `error: '?' on Result[(Int, Int, Str), Str] needs the function to return Result[_, Str], but it returns Str`. This was clear and correct: I had used propagation in a function returning a response string. Replaced it with explicit matches; no confusing compiler error.
- Wish: a concise way to unwrap a Result and return its error as the function's plain response value. Explicit matches repeat the same dispatch boilerplate.
- No documentation gap encountered. Stable integer node IDs and value-semantic maps were sufficient for moves that preserve the current directory.

## 09-bookmarks (done)
- No documentation gaps or confusing compiler errors encountered. The library explicitly warned that the journal module cannot implement a task-defined record format; using Fs directly was well documented.
- `Fs.append` durability, `Fs.rename` replacement semantics, and `Fs.truncate` made crash recovery implementable without undocumented APIs. Verified SIGKILL after an acknowledged response, restart, overlap replay, and unchanged invalid files.
- Wish: a standard strict decimal validator/parser with configurable leading-zero policy; several tasks required handwritten lexical checks around `to_int()`.

## 10-war (done)
- No documentation gaps or confusing compiler errors encountered. Rank lookup, list removal, and explicit pile ordering were sufficient for the simulation.
- Wish: a dedicated character type or direct code-point iteration would avoid switching among bytes, integer code points, and one-character strings for rank parsing.
- The FIFO/deque wish from task 06 also applies here; decks are small enough that front removal is acceptable.

## Top 10 points
1. A reusable command-line option parser would reduce repeated validation and dispatch (01, 03, 05, 10).
2. Standard Gregorian date parsing and day arithmetic would remove handwritten calendar code (05).
3. A deque would express FIFO lots and card decks without O(n) front removal (06, 10).
4. Streaming character iteration would avoid allocating all one-character strings at once (03).
5. Bitwise integer operations would express IPv4 masks and alignment directly (04).
6. Strict decimal parsing with configurable lexical rules would remove repeated leading-zero and sign checks (09 and earlier tasks).
7. A concise Result-to-plain-response early return would simplify protocol handlers (08).
8. A lightweight reusable command parser would reduce protocol-validation boilerplate (07).
9. Byte iteration with offsets without materializing a byte list and enumerated pairs would help validation (02).
10. A character type or direct code-point iteration would make character-heavy code more consistent (10).

Across all ten tasks, I found no missing, unclear, or wrong documentation that blocked implementation. The one compiler error was accurate and actionable, quoted under task 08. Particularly useful documented details were carriage-return behavior, copy-on-write/deep mutation, exact integer money formatting, and filesystem durability/recovery semantics.
