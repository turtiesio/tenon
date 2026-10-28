# Hidden acceptance-test report

All work is under `study/hidden/` and `study/harness.py`. Inputs were the frozen
study README and task specifications. No submitted solutions were inspected.

## Final results

| Task | Cases | Reference passed | Silent wrong solution failed |
|---|---:|---:|---:|
| 01-wordfreq | 25 | 25/25 | 24/25 |
| 02-semsort | 25 | 25/25 | 23/25 |
| 03-fcut | 25 | 25/25 | 24/25 |
| 04-salesreport | 25 | 25/25 | 25/25 |
| 05-latency | 25 | 25/25 | 25/25 |
| 06-kvtx | 25 | 25/25 | 24/25 |
| 07-orderbook | 25 | 25/25 | 24/25 |
| 08-ledger | 25 | 25/25 | 24/25 |
| 09-durable-queue | 25 | 25/25 | 24/25 |
| 10-jobsched | 25 | 25/25 | 25/25 |
| **Total** | **250** | **250/250** | **242/250 (96.8%)** |

The 250 cases contain 297 program invocations: 285 normal runs and 12 SIGKILL
runs. Every worked example is included as `example-1` through `example-5`;
compound examples have additional separately scored cases with descriptive
suffixes. Some additional cases group related normal invocations in `steps`,
keeping the task suites at 25 cases each. Every step must pass for its case to
pass.

## Reproduce

From the repository root, validate all private references:

```sh
python3 study/harness.py all --json study/hidden/reference-results.json -- python3 'study/hidden/ref/{task}.py'
```

Final result: `250/250 passed; 0 failed`, exit 0.
`{task}` is replaced by each task id in command arguments. Existing relative
solution paths are resolved before switching to the fresh working directory.
The harness also accepts an individual task id or task directory, for example:

```sh
python3 study/harness.py study/hidden/08-ledger -- python3 study/hidden/ref/08-ledger.py
```

Check the deliberately silent wrong solution:

```sh
python3 study/harness.py all --json study/hidden/negative-control-results.json -- python3 study/hidden/negative_control.py
```

Result: `8/250 passed; 242 failed`, exit 1. Only empty-output success cases
pass. The control does not implement any task or inspect fixture information.

Validate fixture structure and the runner contract:

```sh
python3 study/hidden/validate_fixtures.py
python3 study/hidden/test_harness.py
```

The structural check passes for all 250 cases. All 11 runner checks pass,
including literal/empty argv values, binary stdout, stderr capture without
comparison, EOF, exact exit codes, setup copying, case isolation, continued
steps after failure, lock-step kills, process-group cleanup, timeouts,
early exits and both supported directory layouts. The shorter timeouts in
runner self-checks are test-local; the production runner uses 10 seconds.

## Coverage

- **01-wordfreq:** five examples; ASCII separators and ordering; default top
  ten; case folding; file/stdin summation and repeated files; option placement,
  repetition and `--`; missing files; length/top boundaries and usage errors.
- **02-semsort:** all examples and error alternatives; stable build-metadata
  ties; reverse and unique ordering; prerelease identifier comparisons;
  trimming/CRLF/final lines; numeric and grammar boundaries; filtering and
  invalid lines; file and argument errors.
- **03-fcut:** all examples and error alternatives; empty/missing/repeated
  fields; closed and open ranges; Unicode field data; literal CR; delimiter
  defaults; empty/custom output separators; repeated options; file/stdin
  ordering and `--`; all stated LIST/option error categories.
- **04-salesreport:** all examples and error alternatives; strict single-line
  CSV parsing; quoting and significant spaces; UTF-8 fields; leap centuries
  and year boundaries; integer-cent arithmetic and half-up rounding; maximum
  values; duplicate rows; global product aggregation and ties; a region named
  TOTAL; validation before filtering; inclusive/reversed/repeated date bounds.
- **05-latency:** all examples and error alternatives; numeric path segments,
  query removal and empty segments; separate methods; 500/599 vs 499; percentage
  half-up rounding; nearest-rank percentiles including p99 distinct from max;
  sort ties; min-count totals; line grammar and numeric boundaries; blank,
  tabbed, CRLF and final unterminated lines.
- **06-kvtx:** all examples; syntax errors and spacing; byte-order key listing;
  exact value counts; nested commits and rollbacks; deletion/recreation;
  integer syntax, bounds and canonicalization; failed increments leave state
  unchanged; depth/token limits; EOF with open transactions; process isolation
  and response flushing.
- **07-orderbook:** all examples; buy and sell sweeps; maker prices; FIFO at a
  price and after partial fills; incoming remainders; cancellation and permanent
  id consumption; malformed orders leave ids available; strict spaces/tokens;
  numeric/id boundaries; large aggregated levels; numeric level ordering;
  response flushing and process isolation.
- **08-ledger:** all examples and error alternatives; parsing and semantic
  error order; failed request-id reuse; duplicate checks before semantics;
  maximum balances/amounts and identifiers; repeated replay; successful and
  failed requests around kills; transfer retries; empty logs; complete-line
  corruption; valid records separated by multiple spaces; torn tails, whole
  torn files, subsequent appends and a further restart; directory errors.
- **09-durable-queue:** all examples and usage alternatives; ready order,
  ACK/NACK validity, persistent attempts and ack totals; duplicate payloads;
  payload/id boundaries and strict command spacing; numeric ordering past id
  9; normal-exit and repeated-crash recovery; kills after PUT, GET, ACK and
  NACK acknowledgments; arbitrary leftover temporary files; directory errors.
- **10-jobsched:** all examples and error alternatives; simultaneous finishes
  before starts; priority/name ties; lowest-worker reuse; forward/repeated
  dependencies; name, duration, priority and worker boundaries; comments and
  CRLF/final lines; graph validation before output; duplicate jobs, cycles,
  missing dependencies, bad tokens and malformed dependency lists; options.

## Ambiguities and protocol limits

See [AMBIGUITIES.md](AMBIGUITIES.md) for quoted sources and the questions that
are deliberately untested: kvtx negative zero, invalid earlier repeated option
values, NUL/LF fcut delimiters, and dash-prefixed file arguments in salesreport
and latency. That file also documents the requested `cases/` layout and the
explicitly excluded behaviors.

The runner compares only stdout bytes and exit codes, as required. Persistence
is observed through restarts and retries. It does not add filesystem assertions
or inspect implementation-specific snapshots; atomic rename and WAL syscall
mechanics are not directly observable through this fixture format.

The explicit fixture builder is `generate_cases.py`; it does not import or run
references. Logs and lossless JSON diagnostics are saved beside this report.
