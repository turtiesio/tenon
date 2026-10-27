# Blind usability study: Tenon vs Python vs TypeScript

This directory holds the materials for a blind programming-language usability
study. It compares Tenon with Python and TypeScript on small, realistic
programs that can be tested as black boxes.

## Layout

```
study/
  README.md              this file (protocol and test format)
  tasks/NN-<slug>.md     task specifications (shown to authors)
  hidden/<task-id>/...   hidden acceptance tests (never shown to authors)
  solutions/<lang>/<author>/<task-id>/...   submitted solutions (published after the run)
  logs/<lang>/<author>/<task-id>.log        full session logs (published after the run)
```

`<task-id>` is the file name of the spec without `.md`, for example
`01-wordfreq`.

## Protocol

1. **Tasks are fixed before any solution exists.** The ten specs in `tasks/`
   are frozen (committed) before any author session starts. After that they
   are not changed. If a spec turns out to be ambiguous, the ambiguity is
   recorded in the report, and every language is scored against the same
   frozen text.
2. **Hidden tests.** A *different* agent writes the acceptance tests in
   `hidden/`, working from the frozen specs alone. That agent never sees a
   solution. The suite for each task includes the worked examples from its spec,
   plus further cases for edge cases and error handling. Authors never see
   `hidden/`.
3. **Authors.** Each language gets **3 independent authors**. An author is a
   fresh AI agent session with no memory of other sessions. Across the 3
   authors of a language, at least **two different model families** are used.
   Every model family used is used for all three languages.
   Each author solves **every** task in its assigned language. An author sees
   only:
   - the task spec (`tasks/NN-*.md`), and
   - the documentation of the assigned language: the standard language docs
     for Python and TypeScript, and `docs/` plus `tenon.md` for Tenon.
   An author does not see other solutions, `hidden/`, or any other study
   material. Authors may run their own program and write their own tests.
   Any extra duty an author has (Tenon authors keep NOTES.md on documentation
   gaps) is done **off the clock**: only after `./try.sh --done NAME` (or
   `--give-up`) for that task, so it never counts as task time (from wave 5 on;
   in waves 2-4 notes were written before `--done`, which added ~3 s per Tenon
   task, study/results/wave4/TIME_ANALYSIS.md).
4. **Time box.** Each task has a **30-minute wall-clock** limit per author. The
   solution is whatever is on disk when time runs out. A missing or non-running
   solution scores 0 on hidden tests.
5. **Allowed facilities.** Only the language's standard library and runtime.
   No third-party packages, networking, or subprocesses that run another
   language.
6. **Execution.** Each solution is run through a per-language launcher fixed
   by the harness, for example `python3 main.py`, `node main.js` (after `tsc`),
   or the Tenon launcher. In the specs and tests, "the program" means that
   launcher. Tests give only the arguments that follow it.

## Measurements (per author, per task)

| Metric | Definition |
|---|---|
| Hidden-test pass rate | passed cases / total cases in `hidden/<task-id>/` |
| Size: lines | non-blank, non-comment source lines in the solution, without lines that hold only closing brackets (user decision after wave 3; the raw count is reported too) |
| Size: tokens | lexical tokens in the solution, excluding comments and whitespace (counted with each language's lexer) |
| Time to visible green | wall-clock time from session start until the spec's worked examples first all pass |
| Attempts to visible green | number of program runs until the worked examples first all pass |
| Errors along the way | count of compile/type errors and runtime crashes (uncaught exception, panic, non-zero exit from the runtime itself) seen in the session log |
| Defects | hidden-test failures grouped by root cause (one defect may fail many cases), classified as: spec misread, edge case, error handling, output formatting, persistence/recovery, language/library pitfall |

## Reporting

- For each metric, task and language, report the **median of the 3 authors**.
  Per-author values are reported as well.
- **Publish everything**: all solutions, all session logs, the hidden tests
  and the harness, including failed and timed-out attempts.
- **Human review**: a human reviews a random sample (at least 20%) of the
  solutions, chosen uniformly across languages. Unfair solutions are flagged
  and scored 0 on that task, and the flag is reported. Unfair includes:
  hard-coding expected outputs, detecting the test harness, calling another
  language's interpreter, using non-standard-library code, or getting outside
  help beyond the allowed docs.
- **Milestones**: the study is rerun at each language milestone with a
  **new task set**. The new tasks are written and frozen before any solution
  exists, as above. Old task sets stay published, and a new set is never
  tuned against an old one.

## Hidden test format (black box)

The test-writing agent must follow this format exactly. Every test compares
**stdout bytes** and the **exit code**. Stderr is captured for logs but is
**never compared**.

### Directory layout

```
hidden/<task-id>/<case-name>/
```

`<case-name>` matches `[a-z0-9][a-z0-9_-]*`. A case is either a
**single-run case** or a **multi-run case**.

### Single-run case

| File | Required | Meaning |
|---|---|---|
| `cmd` | yes | The program's arguments (argv after the program), **one argument per line**. The file is UTF-8 text. Each line, without its terminating `\n`, is exactly one argument, with no quoting or escaping, and spaces are kept. An empty line is an empty-string argument. The final line must end with `\n`, so an argument list of N arguments is exactly N lines. A zero-byte `cmd` means no arguments. |
| `stdin` | no | Bytes written to the program's stdin, after which stdin is closed. If absent, stdin is empty: it is closed immediately. |
| `setup/` | no | A directory tree. Its *contents* (not the `setup` directory itself) are copied recursively into the working directory before the run. |
| `expected_stdout` | yes | The exact bytes expected on stdout. A zero-byte file means "no output". |
| `expected_exit` | yes | The expected exit code as a decimal integer, optionally followed by `\n`. |

Running a single-run case:

1. Create a fresh empty temporary directory and make it the working directory.
2. Copy `setup/` contents into it, if present.
3. Start the program with the arguments from `cmd`. Relative paths in
   arguments resolve against the working directory.
4. Write `stdin` (if any), then close stdin.
5. Wait for exit. **Timeout: 10 seconds.** A timeout fails the case.
6. The case passes if and only if stdout equals `expected_stdout` byte for byte
   **and** the exit code equals `expected_exit`.

### Multi-run case (persistence and crash recovery)

A multi-run case directory contains a `steps` file, an optional `setup/`, and
one subdirectory per step. It has no top-level `cmd`, `stdin` or `expected_*`
files.

`steps` lists one step per line, in execution order:

```
<step-name>
<step-name> kill-after=<N>
```

- `<step-name>` matches `[a-z0-9][a-z0-9_-]*` and names the subdirectory
  `<case>/<step-name>/`.
- `N` is an integer ≥ 1.
- Blank lines are ignored. There are no comments.

Each step directory contains `cmd`, optional `stdin` and `expected_stdout`,
with the same meanings as above. A step **without** `kill-after` also contains
`expected_exit`. A step **with** `kill-after` has no `expected_exit`.

Running a multi-run case:

1. Create **one** fresh working directory and copy `setup/` into it once. All
   steps run in this same directory, in order. Files persist between steps, and
   the harness does not touch them between steps.
2. **Normal step** (no `kill-after`): run exactly like a single-run case.
   Stdin is written in full and then closed. The step passes if stdout and the
   exit code match.
3. **Kill step** (`kill-after=N`): the harness runs the program in
   **lock-step**:
   - It writes the first line of `stdin`, including its `\n`, and flushes.
   - It reads stdout until one complete line (ending in `\n`) has arrived.
   - It repeats this with the next stdin line.
   - As soon as the N-th complete output line has been read, it sends
     **SIGKILL** to the process, without writing any more input and without
     closing stdin, and waits for the process to die.
   - The step passes if the N lines read equal `expected_stdout`, which then
     holds exactly N lines. The step fails if the process exits, or produces no
     line within 10 seconds, before N lines have arrived.
   - Kill steps are only used with tasks whose protocol produces **exactly one
     output line per input line**, and with `N` no greater than the number of
     lines in `stdin`.
4. The case passes only if every step passes. Steps after a failed step are
   still run, for diagnostics, but the case counts as failed.

Programs used with kill steps must therefore **flush stdout after every
response line**. The task specs for line-protocol services state this
requirement.

### Conventions for test writers

- Tests derive only from the frozen spec text. Where the spec says something is
  "not required" or "not tested", do not test it.
- Do not compare stderr. Where the spec requires "an error message on stderr",
  check only stdout and the exit code.
- Keep inputs within the limits each spec states (sizes, number ranges, ASCII
  vs UTF-8).
- Include every worked example from the spec as its own case, named
  `example-1`, `example-2`, and so on.
