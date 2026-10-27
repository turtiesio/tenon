# TENON usability notes

## Initial documentation and task 01
- The reference's Sys definition in section 10 omits `net`, while the prelude includes it. The later networking section helps reconcile this, but the overview is stale.
- Standard-library source paths in the reference use `std/journal.tn` and `std/regex.tn`, whereas the kit uses `docs/std-*.tn`; the introductory prelude path guidance is clearer.
- Wish: a small option parsing helper would reduce repetitive command-line validation.
- Task 01: all published examples passed. No confusing compiler errors encountered.

## Task 02
- All published examples passed without compiler errors.
- Wish: builtin base-aware integer parsing and formatting. Checked arithmetic made correct overflow handling straightforward.

## Task 03
- All published examples passed without compiler errors.
- Wish: a byte iterator would avoid repeated indexed loops for ASCII algorithms; `chars()` returns strings rather than byte/code-point integers.

## Task 04
- All published examples passed without compiler errors.
- `Fs.list` has a signature but no description of whether entries are names or full paths, or their ordering (not needed yet, but an API documentation gap).
- Wish: a standard CSV module; quoted multiline records require substantial custom parsing.

## Task 05
- All published examples passed without compiler errors. Regex, stable sorting by tuples, and mutable map entries fit this task well.
- Wish: a formatting width/alignment syntax would make the table output expression much easier to read than repeated `to_str().pad_left(...)` calls.

## Task 06
- All published examples passed without compiler errors. Heap and Set APIs support an efficient deterministic topological sort.
- Wish: a map entry/default insertion API returning a mutable place, to avoid the recurring `contains` / insert-empty / mutate sequence for adjacency lists.

## Task 07
- All published examples passed without compiler errors. Undo/redo stores edit deltas rather than full snapshots.
- Wish: a list splice operation (replace a range with a list) for buffer editing; composing slices and concatenation is clear but allocates a new list on each edit.
- `read_line()` plus explicit `flush()` makes the request/response service straightforward.

## Task 08
- All published examples passed without compiler errors. Explicit `mut` cursor parameters worked well for a small recursive-descent parser.
- Wish: lightweight parser helpers (consume prefix/character, digit run) to reduce repeated bounds checks and cursor bookkeeping.
- Generic nested `Option` and mutable memoization maps worked as documented.

## Task 09
- All published examples passed, including a real process-group SIGKILL after three responses and a restart. No compiler errors.
- `Fs.mkdir` always creates parents, whereas the task needs only the last component created; implemented an explicit parent-directory check. Wish: a non-recursive mkdir variant and path parent/join helpers.
- `Fs.write` is documented as atomic and durable already; the task additionally requires a named `.tmp` followed by rename, which the APIs support.
- Startup state format bounds `next` to 9 digits, but does not define what ADD should do when a preloaded next is 999999999 and increments to 1000000000. This is a task-spec ambiguity, not a language issue; continued with ordinary increment.

## Task 10
- All published examples passed without compiler errors. Nested mutable list methods supported LRU updates cleanly.
- Wish: byte iteration and radix parsing would again simplify trace parsing.

## Overall observations
- No confusing compiler errors occurred: every submitted implementation compiled on its first try. Thus there are no compiler-error quotations to report.
- Value semantics, explicit mutability, algebraic error values, ordered maps, tuple sort keys, and the documented short-circuit guards were sufficient for all ten tasks.
- All solutions were built/run exclusively through try.sh. All test fixtures and helper scripts are under scratch/. No hidden specifications or external Tenon material were accessed.

## Top 10 points
1. The reference's section 10 Sys definition omits `net`, which is present in the prelude.
2. Standard-module source paths in the reference do not match the study kit's `docs/std-*.tn` paths.
3. Fs.list lacks documented entry shape (basename versus path) and ordering.
4. Wish: base-aware integer parsing and formatting, needed in both radix and cache trace parsing.
5. Wish: numeric width/alignment formatting to simplify table output.
6. Wish: a byte iterator; chars() produces strings, leaving ASCII parsers with indexed byte loops.
7. Wish: a mutable map entry/default insertion API for grouped rows and adjacency lists.
8. Wish: list splice to replace ranges directly in the undoable line buffer.
9. Wish: path parent/join helpers and non-recursive mkdir; Fs.mkdir always creates parents.
10. Wish: a standard CSV parser/writer for quoted multiline records.

No confusing compiler errors were encountered. All ten tasks are done; none reached its 30-minute time box.
