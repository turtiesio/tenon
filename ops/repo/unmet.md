Only what ops/repo/status.py cannot compute; the verdicts above come from data.

- **Usability, time.** User decision: the time target stays as written and is
  reported unmet; no design change is made to chase it. Tenon's minutes over
  the waves: 1.7x, 1.46x, 1.69x, 1.47x and 1.47x Python (waves 2, 3, 4, 5, 6).
  The remaining gap is mostly writing more tokens (explicit types and braces),
  so library additions (wave 6: format specifiers, collection helpers) no
  longer move it. Lines: closing-brace lines are about a fifth of Tenon's
  lines; without them Tenon has fewer lines than Python. Per-wave notes:
  evidence/study/results/waveN/SUMMARY.md and docs/log.md.
- **Performance.** The real-program benchmarks (calc, mdhtml) match the
  structure of their C and Rust counterparts: one output buffer passed down
  (`mut out: Str`), call parameters in parallel lists. The earlier
  string-returning and Map-environment versions ran at 1.85x and 1.62x of C;
  docs/reference.md (performance model) explains why.
- **Concurrency.** A single-threaded event loop per thread (programs/chat) and
  isolated workers with channels on every core (not in the seed:
  docs/reference.md §18, programs/v2/scan, bench/v2).
- **Landing time** is printed by ops/repo/land.sh on each landing but not
  collected anywhere, so the "landing <= 5 min" goals are not measured here.

- Milestone 2 closed by the owner (2026-10-28) on wave 7: no regression against wave 6 (lines 0.89x of Python, was 0.93x; per-task writing 1.24x, was 1.38x; iterating 1.8x, was 2.5x; total minutes 1.51x, was 1.47x, inside the 1.46x-1.69x wave-to-wave spread). evidence/study/results/wave7/.
