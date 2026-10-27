# Hidden acceptance tests: task set 2

Final result: **250/250 cases passed; 0 failed**, across **428 process runs**.
All ten tasks have 25 cases, within the requested 15–25 range.

- `01-cfgcheck`: 25 cases, 25 passed; silent control fails 24/25.
- `02-ldiff`: 25 cases, 25 passed; silent control fails 23/25.
- `03-datecalc`: 25 cases, 25 passed; silent control fails 25/25.
- `04-lfagg`: 25 cases, 25 passed; silent control fails 25/25.
- `05-gradebook`: 25 cases, 25 passed; silent control fails 25/25.
- `06-alertwin`: 25 cases, 25 passed; silent control fails 25/25.
- `07-ratelimit`: 25 cases, 25 passed; silent control fails 24/25.
- `08-inventory`: 25 cases, 25 passed; silent control fails 24/25.
- `09-tally`: 25 cases, 25 passed; silent control fails 24/25.
- `10-servsim`: 25 cases, 25 passed; silent control fails 25/25.

From `/Users/hwang/.t3/projects/tenon`, validate everything against the private
references with this exact command:

```sh
python3 -B study/hidden2/run.py all --json study/hidden2/reference-results.json -- python3 -B 'study/hidden2/ref/{task}.py'
```

The command exits 0. Its final line is `250/250 passed; 0 failed`.
The captured output is in `reference-validation.log`; lossless per-run stdout,
stderr, exit codes, timing, and pass/fail details are in `reference-results.json`.
No stderr text is compared.

The original harness does not support `STUDY_HIDDEN`. `run.py` imports it with
bytecode writes disabled, sets only its in-memory ROOT to this directory,
and calls its original main function. `study/harness.py` is unchanged.

Fixture expectations are written independently in `build_cases.py`; that
script never imports or executes a reference. The ten standard-library-only
references are under `ref/NN-slug.py` and were written from the task specs.
They have not been used to inspect or score any submitted solution.

Every numbered worked example is present as `example-N`. Examples with
several invocations use one multi-run case with a separate step per invocation.
The additional cases cover each task's rules, applicable empty input,
malformed records/lines, duplicates, numeric and size boundaries, usage
errors, and the specified exit codes. Cases stay within stated input limits.

Tally has 16 multi-run cases. Five cases exercise acknowledged crash recovery
with six SIGKILL steps, including repeated crashes, deletion, reads/errors,
and compaction. Planted files cover a torn first record, a torn final record,
invalid records followed by otherwise valid records, stale temporary files,
all record types, and the 100000-record limit. Restart steps check state and
log record counts after new appends. One test also observes deletion of a
stale temporary file by subsequently using that path as a new data directory.
The rl and inventory suites each include an additional lock-step kill test
to verify response flushing; there are eight kill steps in total.

The trivially wrong control prints nothing and exits 0:

```sh
python3 -B study/hidden2/run.py all --json study/hidden2/wrong-results.json -- python3 -B study/hidden2/wrong.py
```

It passes **6/250** and fails **244/250 (97.6%)**, failing at least 23 cases in
every task. Exit status 1 is expected. Its six accidental passes are empty
input/output cases or quiet success cases. Details are in `wrong-results.json`
and `wrong-validation.log`.

The structure and input-limit audit is reproducible with:

```sh
python3 -B study/hidden2/audit.py
```

Final result: `AUDIT PASS: 250 cases; 428 process runs; 8 kill steps`.
All private Python sources also parse successfully.

Four excluded ambiguity questions, with exact spec quotations and exclusion
boundaries, are documented in `AMBIGUITIES.md`:

- datecalc: whether an invalid earlier FMT matters after a valid replacement.
- tally: how compaction handles values wider than the 15-digit log grammar.
- tally: what an empty DIR argument denotes.
- tally: behavior for storage-object type conflicts or failures inside DIR.

No expectation depends on resolving these questions. Only files under
`study/hidden2/` were created or modified. No Git state-changing command was run.
