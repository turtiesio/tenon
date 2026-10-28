# Study wave 3

- Tasks: study/tasks3 (written by a separate agent before any solution existed).
- Hidden tests: study/hidden3 (Codex, from the specs alone; 250/250 against its
  private references). Scored with `STUDY_ROOT=/tmp/tenon-study3
  STUDY_RUNNER=study/hidden3/run.py tools/study.py eval`.
- Compiler frozen at the commit in COMPILER_COMMIT (copied into the kits).
- Authors (Latin square, same as wave 2):

  | Kit | Tenon | Python | TypeScript |
  |---|---|---|---|
  | a | Claude Opus 5.5 | Claude Sonnet 5.5 | Codex gpt-6.1-sol |
  | b | Claude Sonnet 5.5 | Codex gpt-6.1-sol | Claude Opus 5.5 |
  | c | Codex gpt-6.1-sol | Claude Opus 5.5 | Claude Sonnet 5.5 |

- Brief (identical across languages apart from the language paragraph and,
  for Tenon, the NOTES.md request): read only the kit; per task run
  `./try.sh --start`, write the solution, test the spec's examples through
  try.sh, `--done` (or `--give-up` at 30 minutes); "write code the way you would
  normally write good code in this language ... do not optimize for line
  count"; no questions. Tenon's documentation is the kit's docs/ only
  (reference.md, prelude.tn, std-*.tn).
- Each kit directory holds every solution, attempts.jsonl (the timestamped log
  of starts, runs, compile errors and crashes) and, for Tenon, NOTES.md.
- Caveats: try.sh changes into the kit directory, so several authors' first
  runs with relative scratch paths failed (logged as runs, not compile errors);
  some error counts include the same error re-run before it was fixed
  (Tenon b: 9 of 11 on 07-linebuf). Minutes are wall-clock from --start to
  --done for model authors, so they include model speed.

Results: SUMMARY.md (medians), rows.json (per solution).
