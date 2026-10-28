# Tenon usability notes

- Initial documentation: reference links point to `src/prelude.tn` and `std/journal.tn`, but this kit supplies `docs/prelude.tn` and `docs/std-journal.tn` instead. The reference also mentions unavailable tests and docs/log.md.
- Task 01: wished for regular expressions or a small parsing API for lexical validation; implemented identifier and bounded decimal checks manually.
- Task 01: wished for trim with an explicit character set; the task permits only space/tab trimming, while builtin trim removes more whitespace.
- Task 02: accidentally left a standalone range expression; compiler said `error: expected ',', found '..'`. Reference demonstrates ranges only in `for`, but does not explicitly state they are not first-class expressions. A more direct diagnostic would help.
- Task 02: a list repetition/filled-list constructor would make the LCS zero matrix clearer; used nested push loops.
- Task 03: no standard date/calendar support in the kit; implemented Gregorian ordinal conversion and formatting manually. Integer padding via to_str().pad_left() was straightforward.
- Task 03: wished for a formatting builder or directive formatter; explicit byte scanning and repeated string concatenation are needed for custom formats.
- Task 04: no fixed-decimal formatting/rounding API is documented. Implemented quotient/remainder formatting to get exact half-away-from-zero rounding without floating-point error or sum*100 overflow.
- Task 04: read_line() conveniently handles CRLF and EOF as specified. Pattern unwrapping with let-else made parser failures easy to express.
- Task 05: wished for comparator-based sorting (sort_with / compare function). sort_by only accepts a key, but exact P/M ordering cannot safely use a Float key. Implemented merge sort.
- Task 05: Int cross multiplication can overflow for totals allowed by the limits; no wider integer/big-integer type exists in the documented API. Used continued-fraction comparison instead.
- Task 05: nested map/struct mutation worked as documented and made aggregate updates concise. No additional compiler errors in tasks 03–05.
- Task 06: wished for a deque/queue API. A list plus a moving head index works, but retains expired timestamps; removing index 0 repeatedly would shift elements.
- Task 06: the docs explain copy-on-write semantics but not cost guarantees for nested map/list mutation. Direct mutation performed well in a 200000-event try.sh run (~0.3 seconds including wrapper/build).
- Task 07: enum commands plus a separate parser made validation-before-mutation clear. Mut parameters worked on the policy map and logical clock without surprises.
- Task 07: wished for reusable bounded-decimal/name validators; similar lexical loops have now been written independently for several tasks because no regex or parser utility is supplied.
- Task 08: wished for a priority queue / heap. Expiring holds with different TTLs need time-ordered processing; implemented a binary heap over (expiry,id) tuples.
- Task 08: passing nested fields as mut arguments (mut state.expiry) worked, but the reference's mut-parameter example only shows a simple variable. More examples of nested places would improve confidence.
- Task 09 spec conflict: log `<int>` is limited to 15 digits, but accumulated values may reach ±10^17 and COMPACT must emit one S record per value. Chose to accept up to 18 digits (within ±10^17) for replayed S records so snapshots of legal counter values survive restart. Command integers and A records remain limited to 15 digits.
- Task 09: journal is not usable for the required fixed-format WAL: it adds checksums and discards individual bad lines rather than the entire invalid suffix. Implemented recovery using Fs primitives instead.
- Task 09: Fs.mkdir creates all missing parents, whereas the task requires only the final component. Had to derive and validate the parent path manually; wished for a path API and nonrecursive mkdir option.
- Task 09: docs promise durable append and atomic write/rename, which directly support acknowledgement-after-logging. Verified SIGKILL after three responses and restart, torn suffix recovery, and wide-value compaction/restart through try.sh.
- Task 10: heap implementation from task 08 was reusable within the kit. Two heaps (completion time/server number and idle server number) express deterministic ordering efficiently, but a standard heap would remove substantial infrastructure code.
- Task 10: no iterator/enumerate helper is documented; explicit index loops are needed where request/server indices matter. Wished for enumerate for list traversal.
- Task 10: all input can be validated before simulation using Option and let-else, with no output before success. No additional compiler errors in tasks 06–10.

## Top 10 findings

1. **Missing comparator sort.** Exact rational ordering in gradebook required a custom merge sort because sort_by accepts keys only.
2. **Missing heap/priority queue.** Inventory expiry and server simulation required a handwritten binary heap.
3. **Missing regex/lexical validators.** Repeated strict identifier and bounded-decimal grammars required manual byte loops throughout the tasks.
4. **Missing exact fixed-decimal formatting.** Numeric reports required manual quotient/remainder rounding and zero padding.
5. **Path and mkdir mismatch.** There is no documented path API or single-component mkdir; tally required manual parent-path extraction and validation.
6. **Range syntax diagnostic.** A standalone range produced `error: expected ',', found '..'`; the reference does not explicitly say ranges are restricted to for syntax.
7. **Stale documentation links.** The reference points to src/prelude.tn, std/journal.tn, tests/, and docs/log.md, which are not the supplied documentation paths/resources.
8. **Copy-on-write cost uncertainty.** Value semantics are explained, but nested mutation complexity is not. The 200000-event alert test was fast using direct nested mutation.
9. **Missing queue/deque.** FIFO work uses a list plus head index, retaining consumed entries; a standard queue would express intent and reclaim storage.
10. **Journal suitability needs care.** Its checksum format and per-line rejection do not implement tally's fixed-format valid-prefix recovery. Fs primitives were sufficient; a configurable WAL helper would be useful.

## Completion

All ten tasks were marked done after their specification examples matched. No task reached its 30-minute time box. All Tenon builds/runs went through try.sh; scratch data remained under scratch/. Only study-kit files were read, and .specs/ was not opened.

Task 09's 15-digit log integer versus ±10^17 snapshot conflict remains the documented interpretation choice above. This is a task-spec issue, separate from the language usability findings.
