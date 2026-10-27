# Study wave 4

- Tasks: study/tasks4 (separate agent, before any solution). Hidden tests:
  study/hidden4 (Codex, 250/250 against its references). Scored with
  `STUDY_ROOT=/tmp/tenon-study4 STUDY_RUNNER=study/hidden4/run.py tools/study.py eval`.
- Compiler frozen at COMPILER_COMMIT (3487dd2: if-let/while-let, radix and
  wave-3 library additions, user items hide prelude items). Tenon kits now
  include docs/quickstart.md.
- Authors: same Latin square as waves 2 and 3 (see ../wave3/README.md).
- Brief changes vs wave 3: try.sh keeps the caller's directory (all languages);
  the TypeScript brief says Node's type stripping rejects constructor parameter
  properties (two wave-3 TypeScript authors crashed on it).
- Each kit directory: every solution, attempts.jsonl, and NOTES.md for Tenon.

Findings:
- Two of three Tenon authors gave up 01-hexdump: Tenon had no byte-level
  input (Fs.read rejects invalid UTF-8; Console replaces it). Added after the
  wave (Fs.read_bytes, Console.read_all_bytes, Str.from_utf8, ...).
- Compile errors per Tenon author fell from a median of 11 (wave 3) to 2.
- Time split (median per task): writing until the first run 18 s Tenon /
  13 s Python / 14 s TypeScript; iterating until the examples pass 13 s / 4 s
  / 6 s with the same number of runs (median 11). A Tenon run costs ~0.33 s
  (try.sh rebuilds every time) against 0.1 s for Python; the rest is time
  spent between runs.

Results: SUMMARY.md (medians), rows.json (per solution).
