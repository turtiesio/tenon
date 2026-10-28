# Unattended automation

How the repository keeps improving while nobody is at a machine: what runs
on GitHub, how its changes reach main, and what stops them from weakening a
guarantee. User decisions of 2026-10-28 (docs/log.md, entry 25).

## Mechanisms (tenon.md §2.3: at most about 5)

| # | Mechanism | Parts | Replaces or extends |
|---|---|---|---|
| 1 | the gate | `./check`, run by `ops/repo/land.sh` and by CI (`.github/workflows/ci.yml`) | unchanged |
| 2 | landing | attended: `ops/repo/land.sh` (direct push); unattended: a pull request that merges itself when CI passes (`ops/repo/gh.py pr`, branch protection, auto-merge) | extends `ops/repo/land.sh`'s rule, "nothing reaches main unless the gate passes on exactly it", to agents |
| 3 | approvals | `ops/governance/approvals.log`, `ops/governance/guarded.txt`, `ops/repo/approvals.py` (`--pr` for pull requests) | extends: a pull request may not approve itself |
| 4 | evidence | `ops/evidence/evidence.sh`, `ops/repo/status.py`, run nightly by `.github/workflows/nightly.yml` | the local daily run becomes the fallback |
| 5 | the queue and its agents | GitHub issues with six labels (`ops/repo/gh_labels.sh`); one agent runner (`.github/workflows/agent.yml`) with its briefs (`ops/agents/`), started by `redteam.yml`, `hygiene.yml` and `fixer.yml` | the local scheduled tasks, `.evidence/regressions.md` and task lists in docs |

CI is not counted separately: it only runs the gate and the approvals
checker. Until the owner disables the local scheduled tasks (below), the
evidence run and the red team exist twice; that is the transition, not a
sixth mechanism.

## What runs, and when (UTC)

| Workflow | When | Model | Secret | Output |
|---|---|---|---|---|
| `ci.yml` | every push to main, every pull request, and on request | none | none | the gate on Linux and macOS; for pull requests the job `approvals` |
| `nightly.yml` | 02:17 daily | none | none | `ops/evidence/evidence.sh` on Linux, one issue per open regression, STATUS.md as a pull request |
| `redteam.yml` | Sunday 18:00 (Monday 03:00 in Seoul) | Codex for both parts: conformance on `gpt-6.1-sol`, then authority on `gpt-daybreak-blue-latest` with `--cyber-access-program daybreak_blue`; Claude only as the fallback the owner starts (Refusals, below) | `OPENAI_API_KEY` (the fallback: `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`) | the weekly correctness review, two parts: conformance (docs versus behaviour; `ops/agents/conformance.md`) and authority (capabilities, isolation, obligations, memory safety; `ops/agents/authority.md`); findings in `tests/redteam/` through a pull request, one issue each |
| `hygiene.yml` | Wednesday 18:00 (Thursday 03:00 in Seoul) | Claude | `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | the weekly hygiene review (`ops/agents/hygiene.md`): small fixes as a pull request, larger items as issues |
| `fixer.yml` | 7 times a day (01:23, 04:23, 08:23, 11:23, 14:23, 18:23, 21:23) | Claude and Codex alternately (by run number) when both secrets exist, else the one that exists | either | the oldest open `agent-ok` issue fixed in a pull request, or handed to the owner (`ops/agents/fixer.md`) |

Budget: at most 7 fixer runs a day plus 3 review runs a week, about 7.5
agent runs a day, inside the 10 the owner set. A fixer run with no
`agent-ok` issue ends before any model is called; the nightly run calls no
model. Every agent run follows `ops/agents/common.md` first.

The nightly run sizes the evidence to fit about 30 minutes on a 4-core
runner: `FUZZ_N=200`, `CHECKFUZZ_N=300`, `MUTATE_N=5`, `BENCH_RUNS=3`
(`ops/evidence/evidence.sh` reads them; the local run's defaults are larger).
`.evidence/` is kept between nights in the Actions cache, so running totals
and `.evidence/history.jsonl` (STATUS.md, "Correctness over time") continue,
and uploaded as the run's artifact `evidence` for 14 days.

**Model settings per part** (owner decision 2026-10-28, docs/log.md): each
part of the correctness review passes its own Codex model and cyber access
program to `agent.yml` (inputs `codex-model`, default `gpt-6.1-sol`, and
`cyber-program`, given to `codex exec` as `--cyber-access-program`).
`gpt-6.1-sol` declines the authority brief ("flagged for possible
cybersecurity risk") and Daybreak programs are not available for it, so
authority runs on `gpt-daybreak-blue-latest` with `daybreak_blue`. The
pull request and the brief's "This run" line name the model and program.

**Refusals.** A declined brief is reported, never replaced by another model
in the same run. When Codex's final message declines the work (and the run
wrote no `.agent/pr.md` or `.agent/issues.json`), the step "finish" fails the
run, writes the message to the run summary and opens or updates the issue
`[agent:refused-ROLE]` labeled `needs-owner`; a refusal the API raises as an
error fails the Codex step and the log says so. The documented fallback for
the authority part is Claude, started by the owner:
`gh workflow run redteam.yml -f authority_engine=claude` (or Actions,
redteam, "Run workflow"); the scheduled run always uses Codex.

## The queue: GitHub issues

| Label | Meaning |
|---|---|
| `regression` | opened by the nightly run from `ops/repo/status.py`'s open regressions |
| `redteam` | a finding of the weekly correctness review |
| `hygiene` | an item of the weekly hygiene review |
| `agent-ok` | clear and mechanical, with an acceptance test: a fixer run may take it |
| `needs-owner` | a product decision or a weakening of a guarantee: the owner decides |
| `in-progress` | taken by a fixer run |

One issue per distinct problem: its title starts with a stable key in
brackets (`[asan:trap_unwrap]`, `[mutant:compiler/emit.tn:177]`,
`[bench:wordfreq]`, `[conformance:sort-by-nan]`), and `ops/repo/gh.py issues`
updates the issue with that key instead of opening another; it reopens one
that was closed as completed when the problem is seen again, and leaves one
closed as not planned alone. Fuzzing and checkfuzz have one key each (a new
seed is not a new problem); a benchmark over 1.5x of C, a check over its
budget and a failing `./check` are labeled `regression` without `agent-ok`.

A fixer run takes only issues opened by the owner, a collaborator or the
workflows themselves (`github-actions[bot]`): on a public repository the
text of anyone else's issue is not an instruction. Labels can only be set
by people with triage rights, so `agent-ok` is a decision of the owner or
of a review run.

## How an unattended change reaches main

1. The agent edits the working tree of a fresh checkout of main and writes
   `.agent/pr.md`, `.agent/issues.json` or `.agent/blocked.md`, and does not
   commit, push or call GitHub. The checkout keeps no credentials and the
   GitHub token is given only to the workflow's own steps, except that
   Claude's action requires the token as an input; Claude's tools are
   limited to files and the shell. Whatever an agent pushed anyway would
   still need CI and the approvals check to reach main (step 3).
2. The workflow (`agent.yml`, step "finish", with `ops/repo/gh.py` as main has
   it) opens the listed issues, runs `./check`, and then `ops/repo/gh.py pr`:
   it commits the change on a branch, runs main's `ops/repo/approvals.py --pr`,
   pushes, opens the pull request with auto-merge (squash), and approves
   CI's `pull_request` run. GitHub holds that run ("action_required") while
   `github-actions[bot]` counts as a first-time contributor (the approval
   policy of this public repository), and only a `pull_request` run counts
   for branch protection: on the first nightly pull request (#7) a
   `workflow_dispatch` run of the same commit passed and the pull request
   stayed blocked until the held run was approved. If the token may not
   approve it, the pull request waits for the owner (Actions, the run,
   "Approve and run"); if no run appears, `ops/repo/gh.py` starts `ci.yml` on
   the branch.
3. Branch protection on main requires the checks `fast (ubuntu-latest)`,
   `fast (macos-latest)` and `approvals`, from GitHub Actions, before a pull
   request merges; it requires no review and not an up-to-date branch (a
   stale branch would otherwise wait forever; a break from two pull requests
   that pass alone shows on main's next CI run and in the nightly run).
4. The job `approvals` runs the base commit's `ops/repo/approvals.py --pr`
   (the branch's own copy could have been changed). Beyond the attended
   rules it refuses any change to `ops/governance/approvals.log` (approvals come
   only from the owner), a removed line of `ops/governance/guarded.txt` (rules
   may only be added), and any change under an `owner` line there: `check`,
   `ops/repo/land.sh`, `ops/repo/approvals.py`, `ops/gates/approvals_test.sh`,
   `ops/governance/README.md`, `ops/agents/` (the briefs), `.github/`. So an agent's pull request that
   weakens a guarded test, touches the frozen seed or changes the gate
   fails CI and cannot merge; the owner reads it and decides.

A review run's change may touch only `tests/redteam/` (`--only`). A fixer
run whose change is refused, fails `./check`, adds no guarded test where one
is required, or is given up by the agent hands the issue back: it removes
`in-progress`, adds `needs-owner` and comments with the reason. If the agent
step itself fails (an outage, a rate limit), the issue only loses
`in-progress` and returns to the queue.

**Correctness along the way.** Every fix of an issue labeled `regression`
or `redteam` adds a test that fails before the fix and passes after it,
and lists it in `ops/governance/guarded.txt`, so that weakening it later needs
the owner's approval; the pull request names the test and shows both runs.
The workflow refuses such a fix when it adds no line to
`ops/governance/guarded.txt`; that the test fails before the fix is shown in
the pull request, not re-run by the workflow.

**No AI credit lines** (owner rule, docs/log.md): the briefs forbid
`Co-Authored-By` trailers and "Generated with" lines naming Claude,
Anthropic, OpenAI, Codex or GPT, and `ops/repo/gh.py` drops any such line from
the commits, pull requests and issues it writes. The model that ran is
recorded as a sentence in the pull request instead.

## The owner's side

- **Direct pushes keep working.** Protection does not apply to
  administrators (`enforce_admins` is off), so `ops/repo/land.sh` pushes as
  before; GitHub prints "Bypassed rule violations" (tried on a scratch
  branch with the same protection on 2026-10-28). Force pushes and deleting
  main are refused for everyone.
- **Secrets** (Settings, Secrets and variables, Actions, "New repository
  secret", or `gh secret set NAME`, which asks for the value):
  `OPENAI_API_KEY` for Codex; `ANTHROPIC_API_KEY` or
  `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) for Claude. A
  workflow whose secret is missing logs a notice ("skipped: no secret ...")
  and does nothing else.
- **Kill switch:** the repository variable `AGENTS_ENABLED` set to `false`
  (Settings, Secrets and variables, Actions, Variables, or
  `gh variable set AGENTS_ENABLED --body false`) stops every agent run
  before it starts a runner; deleting it or setting `true` resumes them.
  The nightly run and CI are not affected.
- **One agent at a time:** every agent run is in the concurrency group
  `agents`; a run that starts while another works waits, and of several
  waiting runs GitHub keeps only the newest.
- **Labels:** `ops/repo/gh_labels.sh` creates or updates the six labels.

## Loop times on two machines

The 60 s budget of `./check` is the development machine's. The runner is
slower (about 140 s for `./check`), so `ops/repo/status.py` records each loop
time under the machine it ran on (`TENON_MACHINE`; `local` by default, the
nightly run sets `github-ubuntu-latest`). Milestone verdicts use the
development machine's history; on the runner a check time over 1.5x its
median of the last 7 runs is a regression.

## The local scheduled tasks

The owner's machine (T3) runs the same work as scheduled tasks: the daily
evidence run (`ops/evidence/evidence.sh`, which lands STATUS.md with
`ops/repo/land.sh`), and the weekly correctness review (Codex conformance on
`gpt-6.1-sol`, Codex authority on `gpt-daybreak-blue-latest` with
`daybreak_blue`). The weekly hygiene task is disabled. **GitHub is
primary;** the local tasks stay as they are until the owner has seen the
cloud runs work, and are then disabled. Until then both write STATUS.md:
whichever lands later wins, and a nightly pull request made stale by a
local landing is rebuilt from main the next night (its branch,
`nightly/status`, is reused). The tasks' prompts name repository paths:
since the layout of 2026-10-28 (docs/log.md) they are
`ops/evidence/evidence.sh`, `ops/repo/land.sh`, `ops/evidence/asan.sh`,
`ops/evidence/tsan.sh`, `ops/governance/guarded.txt`, `seed/` and
`evidence/study/` (formerly `tools/`, `governance/`, `bootstrap/` and
`study/`).
