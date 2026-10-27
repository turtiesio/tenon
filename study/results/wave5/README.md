# Study wave 5

- Tasks: study/tasks5; hidden tests: study/hidden5 (Codex, 250/250 against its
  references). Compiler frozen at COMPILER_COMMIT (48f8391: byte I/O, raw strings,
  build cache, fixed regex example, `!`/`&&`/`||` hints). Same Latin square.
- Protocol change from this wave: Tenon authors write NOTES.md only after
  `--done` for each task (study/README.md), so notes are off the clock.

Results (medians over authors): hidden tests 100% in all three languages;
lines without closer-only lines Tenon 801 / Python 920 / TypeScript 803;
minutes 4.4 / 3.0 / 3.6; compile errors 0 / 0 / 0 (median).

Time split, median per task: writing until the first run 16 s Tenon / 13 s
Python / 15 s TypeScript; iterating until the examples pass 6 s / 4 s / 5 s;
a run costs the same in every language now (median gap between runs 0.09 /
0.10 / 0.14 s). Per author totals: Tenon 6.2 / 4.3 / 3.5 min (Opus / Sonnet /
Codex), Python 3.2 / 3.1 / 2.5 (Opus / Sonnet / Codex). The Opus Tenon total includes 2.5 min on
02-trx where, per its notes, its own test harness hung (not a language issue);
its other nine tasks took 0.3-0.6 min each vs Python's 0.2-0.4.
Its 16 compile errors on 10-robots are one error, rerun by its test loop.
