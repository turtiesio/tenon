# Wave 4: where the extra Tenon time went

Question: Tenon authors took a median 4.9 minutes against 2.9 for Python, with
the same number of runs. What filled the difference?

## Method

- Matched pairs with the same model: Tenon B vs Python A (Claude Sonnet) and
  Tenon A vs Python C (Claude Opus). Tenon C vs Python B (Codex) is left out of
  the estimates; see the caveats.
- `attempts.jsonl` gives four phases per task:
  - **write**: from start to the first run;
  - **exec**: run-to-run gaps under 1 s, which are back-to-back runs in a test batch, so they measure the cost per run;
  - **diagnose**: gaps of 1 s or more between runs;
  - **tail**: from the last run to done or give-up.
- In the T3 threads, every item's timestamp, command, code size and reasoning
  summary was read for all four authors (whole threads). The time each item
  took was matched to its phase.
- Code size is the number of characters in the solution files. Notes size is
  the length of the `cat >> NOTES.md` heredocs.

What did **not** happen, and so is not a cause:

- No Tenon author reopened the docs during a task. The only lookup was a single
  `grep -i "binary\|bytes"` by Tenon A in task 01. Reading the docs (about 15 s
  for 2,100 lines) happened before the first clock started.
- Compile errors were nearly absent. Tenon B had 0. Tenon A had 1: `!` instead
  of `not`.
- Apart from task 01, every task passed its examples on the first or second
  run in both languages.

## Causes

Totals are per author, over 10 tasks. Each pair's gap: Sonnet 292.7 s vs
177.3 s, so **+115 s**; Opus 365.3 s vs 227.8 s, so **+137 s**.

| # | Cause (evidence) | Sonnet pair | Opus pair | Frequency | Status |
|---|---|---|---|---|---|
| 1 | **NOTES.md written on the clock** (Tenon-only duty). The whole command `./try.sh --done X; cat >> NOTES.md <<EOF ...; ./try.sh --start Y` is generated before `--done` runs, so the notes count in X's time. Before it comes reasoning about what goes in the notes, e.g. 11 s in 04-timesheet: "the day-lookup index method and the DAYS list constant both work". The tail is 52.9 s vs 23.1 s (Sonnet) and 63.2 s vs 30.9 s (Opus), excluding task 01. | **30 s** | **32 s** | 10/10 tasks, about 3 s each | protocol asymmetry |
| 2 | **Build on every run.** A run costs 0.35 s vs 0.10 s, over about 140 runs per author with equal counts (114 vs 114 runs excluding 01). For example, the icalc batch of 31 runs took 12.3 s vs 3.6 s. | **25 s** | **28 s** | every run | fixed by cd59a7b (cache) if a cache hit costs about 0.1 s |
| 3 | **No byte input (01-hexdump).** Authors probed `Fs.read` and got `Err(Failed("...: invalid UTF-8"))`, probed stdin and got `ef bf bd`, grepped the docs, and wrote a U+FFFD-to-0xff workaround. Two of three gave up. Task 01 took 40.8 s vs 14.4 s and 52.5 s vs 22.5 s; the figure here subtracts the general overhead from causes 1 and 2. | **21 s** | **24 s** | 1 task | fixed by cd6097b |
| 4 | **More code to write.** Excluding 01, Tenon code is 17% / 13% longer (34.2k vs 29.2k and 34.6k vs 30.6k characters). Python used `re` in 10/10 tasks in every kit; **no Tenon author used `std regex` at all**. Instead they hand-wrote byte-loop validators (`valid_name`, `valid_plate`, `is_lower_alnum`, `two_digits`, `valid_url`, ...): 9 per author, 6-13% of all Tenon code. For example, Python's one `PUNCH_RE = re.compile(r"([a-z]{1,16}) (Mon|...) ([01][0-9]\|2[0-3]):([0-5][0-9]) (IN\|OUT)")` became about 25 lines of `parse_punch`, `two_digits` and `valid_name`. Tenon A: "compiling a regex for each felt heavy". The rest is general verbosity: 14-21 typed empty collections (`var x: List[Int] = []`), 10-16 `field: field` struct initialisers and 9-19 `let Some(..) = .. else {..}` per author. | **26 s** | **21 s** | every task, about 2.5 s | open |
| 5 | **Probing semantics between runs.** In uniqx, `printf '\n\nx\n\n' \| try.sh -c \| cat -e` (or `od -c`) was run to learn what `Str.lines()` does with trailing empty lines: 4 s and 6 s. There were separate edge-case batches after the examples passed. Tenon A's compile error `unexpected character '!'` cost 7 s (hint since added in 76c13ae). Tenon A also had an elevator logic bug of its own (14 s), which is not language-related. | 9 s | 26 s (12 s language-related) | 1-3 tasks | partly open |
| | **Sum of 1-5** | **111 of 115 s** | **131 of 137 s** | | |

Causes 1-3 add up to about 75 s of the Sonnet pair's 115 s, and they are
already fixed or are a quirk of the study protocol. Without them the projected
median Tenon time is about 3.6 minutes against 2.9 for Python (about 1.2x). The
rest of the gap is cause 4, writing more characters, plus a little probing.

Other finding: the reference's own `regex` example is broken.
`regex.compile("(\\d{4})-(\\d{2})-(\\d{2})")` interpolates `{4}` as the value
4, which gives the pattern `(\d4)`. Running the documented snippet prints
`not a date`. Every regex quantifier must be written `\{m,n}`, and backslashes
must be doubled. This explains why no author reached for regex.

## The 5 changes that remove the most time

1. **Take the notes off the clock (study protocol).** Require
   `./try.sh --done NAME` as a command of its own before any NOTES.md edit.
   Alternatively, collect the notes after the last task, or give Python and
   TypeScript authors the same duty. Saves about 30 s per author (about 26% of
   the gap). Without this, the time comparison is biased against Tenon.
2. **Make a run cost no more than a Python run (tooling).** Check that the
   cd59a7b build cache brings the cost of an unchanged `try.sh` run, front end
   included, down to about 0.1 s. Also make the first build after an edit
   cheaper: skip `cc -O2` for study builds, or have try.sh use `tenon run` for
   short inputs. Saves about 25 s per author.
3. **Byte I/O (library, landed in cd6097b).** Saves about 20-25 s per author on
   any byte-oriented task. Wave 5 should confirm that authors find
   `Console.read_all_bytes` and `Fs.read_bytes` from the quickstart without
   probing.
4. **Make pattern validation one line (language and library).**
   - Add raw string literals (e.g. `r"[a-z]{1,16}"`: no interpolation, no
     escape doubling).
   - Add a prelude shortcut that needs no `import`, `compile` or `unwrap`
     (e.g. `s.matches(r"...") -> Bool`, `s.captures(r"...") -> Option[List[Str]]`).
     Python-style `fullmatch` would then translate directly.
   - Fix the broken `{4}` example in reference §std regex and in the quickstart
     row.
   - Cheaper alternative: ASCII class helpers (`Str.all_bytes(pred)`,
     `Str.is_ascii_lower_alnum()`).

   This targets about a third of cause 4: roughly 8-12 s per author, plus
   fewer validator bugs.
5. **Cut the remaining boilerplate and the semantic probes (language and
   docs).**
   - Struct field shorthand: `Opts { skip, width }`.
   - Infer the element type of `[]` and `[:]` from later use.
   - Give `Str.lines()` worked examples (`"\n\nx\n\n"` gives
     `["", "", "x", ""]`), plus a variant that strips one trailing `\r`.
     `strip_suffix("\r").unwrap_or(raw)` was written 8 times per author.
   - In the reference, state the points authors reasoned about or noted:
     string literals nested inside `{...}`, `return` as a match-arm value, and
     the precedence of `..` and `and`/`or`.

   Together these save about 10-15 s per author: the rest of cause 4 and the
   probes in cause 5.

## Caveats

- **Few samples.** Two matched pairs, one wave and 10 tasks. The Codex pair
  (Tenon C at 583 s vs Python B at 171 s) is dominated by Codex's own
  bookkeeping, not by Tenon:
  - It marked tasks done early, then gave up later: 01 has a 258 s gap.
  - It ran a final review pass at the end that re-ran icalc under that task's
    clock (gaps of 208 s and 40 s), along with a 49 s notes rewrite.
  - It did hit two confusing errors: `expected a name, found 'unique'` (a
    reserved word) and `unknown name 'List'` for `List[Bool].filled(...)`.
- **Model output speed.** Times are model generation plus tool latency, so
  "writing" time is roughly proportional to the characters emitted. The
  per-cause seconds are split from phase totals using the item timestamps;
  treat them as ±5 s.
- **Reasoning summaries.** The thread shows summarised reasoning, so the
  attribution within the tail (notes thinking vs verification) is inferred
  from content and timing, not measured.
- **Doc reading isn't counted.** Reading the docs before task 1 (about 15 s,
  and about 2,100 lines of context) is outside the per-task clocks. It may slow
  generation a little throughout, which this analysis cannot separate.
