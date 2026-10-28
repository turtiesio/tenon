# Study wave 6

- Tasks: study/tasks6; hidden tests: study/hidden6 (Codex, 250/250 against its
  references). Compiler frozen at COMPILER_COMMIT (03a418d: format specifiers in
  interpolation, max_by/min_by/group_by, Str.all_bytes, wave-5 fixes). Same
  Latin square and briefs as wave 5 (Tenon notes off the clock).
- Rerun: the six Claude authors of the first launch were stopped by an API rate
  limit mid-task; their kits (with clocks that included the outage) were set
  aside unscored and those six authors were rerun on fresh kits with the same
  frozen compiler. The three Codex authors finished in the first launch.
- Caveat: TypeScript author B's log includes a few runs from a shell quoting
  mistake on 02-b64 that did not execute the solution.

Results (medians over authors): hidden tests 100% in all three languages;
lines without closer-only lines Tenon 910 / Python 978 / TypeScript 950; minutes
5.0 / 3.4 / 3.7 (Tenon 1.47x Python); compile errors 0 / 0 / 0. Per task medians:
writing until the first run 18 s / 13 s / 14 s, iterating 10 s / 4 s / 4 s.
Per author totals: Tenon 5.6 / 5.1 / 3.9 min (Opus / Sonnet / Codex), Python
11.3 / 3.4 / 2.7 (Opus / Sonnet / Codex; the Opus Python total is an outlier).
