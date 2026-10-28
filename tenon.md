# Tenon: the smallest sufficient foundation for trustworthy systems, built fast

**Name:** the language is called **Tenon** (file extension `.tn`). In woodworking joinery, a tenon is the tongue cut to fit an exact slot (a mortise). Pieces join only when their shapes fit, and a well-made joint holds without nails or glue. Likewise, components compose only when their contracts fit; nothing is held together by convention.

Start an independent project. **Discover and build the smallest sufficient foundation for representing, composing, computing, interacting with, governing and evolving complex real-world systems, including practical general-purpose software.**

**Optimize for demonstrated real capability per unit of total complexity:** not feature count, research volume, process machinery or architectural sophistication. Working systems beat theory.

## 1. What to achieve

### 1.1 Targets

- **Performance:** C/Rust/Zig-class. Measure:
  - CPU-bound work, allocation and data structures;
  - text and structured-data processing;
  - startup and executable size;
  - I/O, networking and concurrency;
  - long-running services.
- **Usability:** better than Python and TypeScript, judged by line count, task time and defect rate on the same real tasks. Less boilerplate, less defensive code, clearer diagnostics, fewer ways to make subtle mistakes.
- **Generality:** the foundation must faithfully represent more than programs:
  - people, agents, roles and authority;
  - facts, claims, evidence, uncertainty and disagreement;
  - rules, obligations, permissions and decisions;
  - resources, ownership, time, history and change;
  - processes, failures and recovery.

  Don't collapse distinctions that matter. Represent partial knowledge explicitly.

### 1.2 Properties

- **Allow-only by construction.** Only constructions admitted by types, contracts, capabilities and authority are allowed; everything else is rejected. Prefer structural impossibility to detection after the fact. No implicit coercion, ambient authority, hidden mutation or unchecked escape hatch. The safe way must be the simplest way.
- **Complexity localization.** Every concern has one owner and is solved once at the lowest sufficient boundary. Components depend on stable contracts, not on each other's internals. Complexity should grow with the essential distinctions, not with the number of places a concern is repeated. Derive dependent representations instead of synchronizing them by hand.
- **Correctness by construction.** Invalid states, transitions and compositions are unrepresentable where practical. Check as early as possible. Distinguish guaranteed properties from run-time checks and from external evidence. Never silently assume correctness.
- **No silent failure, loss or disappearing responsibility.** Failures, rejected operations, partial results, obligations, pending work, broken assumptions and uncertainty are never silently dropped. An obligation survives crashes and changes of owner. Distinguish failure from absence, and unknown from false.
- **Explicit authority, effects and resources.** Least authority through capabilities. Mutation, ownership, lifetime and cleanup are visible. Practical I/O, persistence, networking, concurrency and recovery stay correct under retries, crashes and cancellation where the application needs it.
- **Change safety.** Find the real owner and impact of a change, make the smallest sufficient modification, preserve unrelated behavior, detect semantic drift, and keep implementations replaceable under their contracts.
- **Reflexive governance.** The foundation can represent, verify and evolve itself with the same mechanisms it offers others. Its rules and checks are themselves governed artifacts, and a change must not silently weaken or bypass an established guarantee. Keep the trusted base minimal and name the trust anchors explicitly.
- **Honest evidence.** Separate authored facts, derived conclusions, assumptions, verified guarantees, measurements and unknowns. State unmet goals plainly.

## 2. How to work: speed is a requirement

### 2.1 Two speeds (non-negotiable)

| Loop | Budget | Contents |
|---|---|---|
| Inner loop (`check --fast`) | **≤ 60 s** | build; run and reject tests in one mode; differential smoke |
| Landing | **≤ 5 min**, never serial behind anything slow | merge onto main + fast check + fast-forward |
| Evidence | asynchronous, off the critical path | full test matrix, sanitizers, fuzzing, mutation, benchmarks, run continuously against main on spare machines |

- Anything that would push a loop over its budget moves to the next slower loop. Don't build machinery to make a slow path tolerable.
- A regression that evidence finds opens a fix task, with the commit that caused it found by bisection. Reverting is cheap; waiting is not.
- Loop times are measured every day and published. A loop-time regression is a bug.
- An experiment runs for 1 minute by default. Anything longer needs a written reason.

### 2.2 Order of construction

Don't start a step before the previous one works end to end.

1. **Core language and compiler.**
   - Values, structs and enums, generics, pattern matching, errors as values, capabilities, located traps.
   - Compile to C, or another portable low-level target.
   - Test it against a tiny reference interpreter from day 1. Differential and generative testing is the cheapest strong evidence.
2. **Real programs.** Build 5–10 small but real systems in the language, for example:
   - a crash-safe job queue;
   - a ledger with exactly-once transfers;
   - an HTTP service;
   - a CLI tool;
   - a scheduler;
   - a program that keeps and revises evidence-backed facts.

   Judge usability and performance on these:
   - blind comparisons against Python and TypeScript, written by separate authors on fixed tasks;
   - benchmarks against C and Rust on the same programs.

   Each language gap they expose becomes a task.
3. **Standard library,** extracted only from duplication that actually appeared (two or more real uses). It is layered: pure, then codec, then store, then capability.
4. **Self-hosting and cross-checking.** Write the lexer, parser and checker in the language itself, and keep them in agreement with the bootstrap compiler through differential tests. Two independent implementations are a cheap way to shrink the trusted base.
5. **Governance,** last and small (section 2.5).

Write infrastructure in the language itself (dogfooding) only once step 2 shows it can carry it. Until then, use the simplest script that works.

### 2.3 Design rules (apply to code *and* to process)

- **KISS:**
  - Use the smallest mechanism that meets the requirement.
  - Every new mechanism states what it replaces, and the old one is deleted in the same change.
  - **Mechanism budget:** at most about 5 pieces of process infrastructure at any time. To add one, remove or merge one.
- **DRY:** One source per fact. Lists of stages, tools, paths, environment variables, limits and rules are defined once and derived everywhere else.
- **SOLID:**
  - One responsibility per module, and depend on interfaces rather than concrete modules.
  - No file over about 1,000 lines and no function over about 80 lines without a stated reason.
- **No speculation:** a feature, library function, rule or check exists only because a real program or a real failure needed it.

### 2.4 Running agents

- **One planner, a few workers, one queue.**
  - The planner writes self-contained tasks: the goal, an acceptance test, the files involved, and what not to touch.
  - Workers implement the task and land it themselves through the fast path.
  - The planner reacts to results and never polls or babysits.
- **Concurrency follows capacity.**
  - Start with 3 workers, and never run more than the machine can serve within the inner-loop budget.
  - From day 1, every heavy command takes a slot from one machine-wide pool.
  - Remote machines run only asynchronous evidence work, each under an explicit CPU cap.
- **Workers run only the fast check locally,** never the full evidence suite.
- **Workers decide everything that isn't a product decision.**
  - They fix merge conflicts, flaky tests, missing classifications and stale branches themselves instead of escalating.
  - The user is asked only about choices that change the product or its guarantees. Those questions are batched (a few per day at most), each with a recommendation.
- **Red teams run on a schedule** against main. Each finding becomes a task with a minimal reproduction, and becomes a regression test when it's fixed.
- **Choose runners deliberately.** One model family implements; another reviews and red-teams. Check refusal policies before assigning work (some models refuse security testing).
- **Durable state.**
  - Tasks, results and decisions live in one crash-safe journal, so nothing depends on any single process or conversation staying alive.
  - Anything that can't be recovered is archived before it's deleted.
  - Processes a job starts are always killed as a whole group when it ends or times out.

### 2.5 Governance: start minimal, grow from incidents

Start with exactly this:

1. **The tests are the contract.** A landing passes the fast check, and main passes the evidence suite.
2. **An append-only approvals log** for a short list of guarantee-bearing changes: removing or weakening a language rule, a capability, or a test that guards one. It's checked by one small tool of a few hundred lines. The log records who approved what and why, and history is never rewritten.
3. **Mutation testing as evidence, not as a gate.** It runs asynchronously, and surviving mutants are reported as tasks.

Add a governance mechanism only when a real incident proves it's needed. Make it the smallest fix for that class of incident, with a test that reproduces the incident. Each mechanism has explicit cost limits: what it adds to landing time (at most 10 s) and how many trusted lines it adds. Measure the trusted base from day 1, and set caps only once its growth is understood.

### 2.6 Starting decisions (from a previous attempt; keep unless evidence says otherwise)

These held up under red-teaming. Start from them instead of re-deriving them:
- **Value semantics:** reference counting plus copy-on-write; string views; no null; no implicit coercion; exhaustive matching.
- **Effects:** errors as values with located traps for bugs, and fixed, reserved exit codes for traps, out-of-memory, stack overflow and output failure.
- **Authority:** capabilities passed to `main` (file system, network, clock, process, console) and attenuated by narrowing. Module privacy acts as unforgeability.
- **Obligations:** linear types for things that must not be dropped (replies, locks, claimed jobs), and affine "unique" types for handles that must not be copied.
- **Generics and data:** static dispatch with traits; derived, strict data codecs.
- **Compilation target:** C, plus a reference interpreter for differential fuzzing.

These cost a lot. Avoid them, or design for them from day 1:
- **Bootstrap language.** A slow, large bootstrap compiler (Python) became most of the trusted base. Choose the bootstrap language for speed and size, and plan self-hosting early.
- **Single platform.** macOS-only testing hid Linux and gcc differences until late. Run CI on macOS and Linux from day 1.
- **Governance before product.** Approvals, budgets, vetting, mutation gates and merge trains were built before there was enough product to protect, and landing slowed from minutes to hours.
- **Long serial work.** A full evidence regeneration on every landing made main move once an hour, and branches kept re-merging to catch up with it.

**Bootstrap compiler: Rust, standard library only, no third-party crates.**
- **Why:**
  - It's fast enough that compiling never shows up in the inner loop.
  - It's memory-safe, so the bootstrap adds no memory-safety bugs to the trusted base.
  - It's portable to macOS and Linux with one toolchain.
  - Agents write it reliably.
- **Limits:** keep it under about 10k lines, as a straight pipeline: lexer → parser → checker → C emitter, one module each.
- **Trust:** the C compiler and `rustc` are named trust anchors. The self-hosted checker (step 4 in §2.2) is the cross-check, not a replacement.
- **Runtime:** a single C header with no dependencies beyond libc. Every check it performs is covered by a test.

**Blind usability study, a fixed protocol:**
1. **Tasks first.** Write 10 task specifications before any solution exists, each with input/output examples (CLI, data processing, a stateful service, persistence with crash recovery, concurrency). A separate agent writes the hidden acceptance tests, which no author sees.
2. **Independent authors.** For each language (Tenon, Python, TypeScript), 3 independent agent sessions each solve every task. They come from at least two model families, and each starts from a fresh context. An author sees only the task specification and that language's public docs. Tenon authors get only its user docs, so the study also measures how learnable the docs are.
3. **Time box.** 30 minutes of wall time per solution.
4. **Measurements:**
   - hidden-test pass rate;
   - non-blank, non-comment lines and tokens;
   - time and attempts until the visible examples pass;
   - compile or run errors along the way;
   - defects the hidden tests found.
5. **Reporting.** Report the median of the 3 per language, with every solution and log published. Re-run the study at each milestone with new tasks, so the language isn't tuned to a fixed set.
6. **Human check.** A human reviews a random sample for unfair solutions, such as a Python version deliberately written badly.

### 2.7 Operating rules learned the hard way

- **Main is always green; revert first.** A red main is fixed or reverted within minutes. Nobody builds on red.
- **Land small and often.** A branch older than about a day is rebased or split. Never queue many large branches behind each other.
- **Scope cleanup.** Kill only the processes and files your own job started. Never run machine-wide `pkill`, and never leave state in shared `/tmp` or on remote machines.
- **Deploy consistently.** When a long-running tool is upgraded (daemon, console), every reader and writer of its data is upgraded together, and records carry a schema version.
- **Plan for runner outages.** Agents hit rate limits and machines reboot. Committed checkpoints and the journal let any task resume, so no progress lives only in a conversation.
- **Treat flakiness as a bug,** fixed at the source. A timing-sensitive test or check is never allowed to block or mislead decisions.

### 2.8 Out of scope for the first milestone

Leave these out until milestone 1 is done:
- distributed execution;
- federated or sharded anything;
- trait objects or dynamic dispatch;
- macros;
- a package manager;
- an IDE or language server;
- optimizations beyond what the benchmarks demand;
- web consoles beyond a one-screen status page.

### 2.9 Working with the user

- **The user owns product decisions and any weakening of a guarantee.** Everything else is yours to decide; act, and report afterwards.
- **Ask rarely and well:** batch questions, give 2–4 options with a recommendation, and state what each option costs.
- **Report outcomes, not activity:** what landed, measured results, open problems and decisions needed. No progress chatter.
- **Respect resource limits:** shared machines, CPU caps and rate limits. Ask before using new external services or accounts.

### 2.10 First day

1. Create the repo and its CI (macOS and Linux), plus a `check --fast` that runs in under 10 s on an empty project, and the fast landing path.
2. Write the language reference as a single source document. Then a vertical slice: a program that reads a file, transforms the data and prints it, compiled to C, run, and checked differentially against the reference interpreter.
3. Add the generated status file, showing loop times, test counts and one benchmark against C and Python.
4. Write the 10 usability task specifications and their hidden tests now, before the language can solve them.
5. Choose the first real program (§2.2, step 2), and grow the language until it runs.

## 3. Evidence and reporting

- **One generated status file,** never edited by hand. It shows:
  - loop times;
  - test, fuzz and mutation results on main;
  - benchmark tables (vs C, Rust, Python, TypeScript);
  - usability results;
  - the trusted-line count;
  - open regressions.
- **Every claim in the docs links to the command that reproduces it.**
- **An iteration log** records each decision, its rationale and its measured effect, including reversals and mistakes.

## 4. First milestone: definition of done

- 10 real programs run correctly, with differential and fuzz testing green.
- A blind usability study puts the language at or below Python on line count and task time.
- Performance is within 1.5× of C on the program benchmarks.
- `check --fast` stays at or under 60 s, and landing at or under 5 min, measured over a week of normal work.
- The self-hosted lexer, parser and checker agree with the bootstrap compiler on the full corpus.
- The approvals log and its checker exist, and have refused at least one real weakening in a test.

Only then decide which further governance, scale or infrastructure mechanisms are worth their cost, and only with measurements showing they pay for themselves.

## 5. Second milestone: definition of done

Scope chosen by the user after milestone 1 (decisions in docs/log.md). Order of
construction: repository layout, then self-hosting, so that every later feature
is built once, in Tenon, not mirrored in two front ends.

- **Fully self-hosted compiler.** The Tenon compiler (selfhost/) checks and
  compiles itself to C. Fixpoint: the compiler built by stage 1 and the one built
  by stage 2 emit byte-identical C for themselves and the full corpus. Every test
  and program passes on the self-hosted compiler on both backends. The Rust
  bootstrap becomes a frozen seed: changing it requires an approvals entry, and
  its line count only shrinks. Self-hosted compile time stays within 3x of the
  bootstrap's.
- **Traits.** `trait`, `impl Trait for Type`, generic bounds (`fn f[T: Show](x: T)`)
  compiled by monomorphization, and explicit `dyn Trait` values for heterogeneous
  collections. The derived eq/ord/hash/show become ordinary traits. Coherence (at
  most one impl per trait and type, in the trait's or the type's module) is checked.
- **Multi-core: isolated workers and channels.** `spawn` runs a function on another
  core with its own heap; workers share nothing and communicate through typed
  channels; sent values are moved or copied, unique and linear types move, and
  capabilities are passed only explicitly. No data races by construction (checked,
  with reject tests). A `par_map` helper. A parallel benchmark reaches at least 3x
  speedup on 4 cores, and a real program uses workers. Coexists with the event loop.
- **Tooling for human users.**
  - `tenon fmt`: one canonical layout, idempotent, the whole corpus formatted.
  - Language server: diagnostics, hover types, go-to-definition, completion, with tests.
  - Packages: a `tenon.toml` manifest, dependencies by local path or git URL and tag,
    a lockfile with content hashes, offline builds from a cache; no registry.
  - VS Code: editors/vscode with a TextMate grammar (checked against the whole
    corpus) and a language-server client, built as a local .vsix.
- **Evidence.** A new blind usability wave on fresh tasks shows no regression
  against wave 6 on lines and time. Benchmarks stay within 1.5x of C. `check --fast`
  stays at or under 60 s and landing at or under 5 min.

## 6. Third milestone: definition of done

Scope chosen by the user after milestone 2's plan (decisions in docs/log.md):
ready for real users, deeper correctness by construction, and scale. AI models
count as real users. No Windows or WebAssembly target in this milestone.

- **Ready for real users.**
  - Standard library breadth: HTTP client and server, JSON, time and dates,
    hashing and cryptographic primitives, subprocesses on top of `Proc`, with
    explicit authority for everything that touches the outside world.
  - Packages: per-package module namespaces; a cryptographic content hash in the
    lockfile.
  - Debugging: source-level stack traces on traps, `tenon run --trace`, and a
    profiler that attributes time to Tenon functions.
  - Usability by real users: a study wave in which model authors (Claude, Codex
    and others; at least two families) build three larger outside-style programs
    (a web service, a CLI tool, a data pipeline) from specifications and maintain
    them through two rounds of changed requirements; time, defects and change
    effort reported per language as in §2.6.
- **Correctness by construction, deeper.**
  - Contracts: `requires` / `ensures` / invariants, proved at compile time where a
    simple decision procedure can, checked at run time otherwise, never silently
    dropped.
  - Effects beyond capabilities: a function's effects (I/O, nondeterminism,
    traps) visible in its signature or inferred and checkable at boundaries.
  - Property-based testing in the standard library, used by the corpus.
  - Evidence: bugs prevented, measured on the corpus and the red team's findings.
- **Scale.**
  - Distributed execution: workers on other machines with the same isolation
    and `Send` rules as local workers, and failures surfaced, never hidden.
  - Macros or compile-time code generation, hygienic, with the generated code
    visible to the formatter, the language server and the checker.
  - Each added only with measurements showing it pays for itself (§4).
- **Gaps carried over:** user Eq/Ord/Hash impls, trait type parameters and
  supertraits, channels the event loop can wait on, all diagnostics in the
  language server, and the small language gaps the studies found.
- **Self-governing infrastructure in Tenon.** The authority over the project's
  process lives in Tenon programs, not in any hosting service:
  - One Tenon system (`tenon ops` or similar) owns the task queue, governance
    (approvals, frozen paths, guarded tests), the evidence record and the agent
    harness (starting Codex, Claude or other agents through `Proc`, with their
    briefs, budgets, kill switch and audit log). Its state is durable and
    versioned in the repository or a store it controls.
  - It runs centralized (one machine) or distributed (several runners, using the
    milestone's distributed workers), with the same rules either way.
  - GitHub Actions, the local T3 scheduler or any other host is only an adapter
    that runs it and reports to it; replacing the host changes no rule. GitHub
    issues, if used, mirror the queue rather than define it.
  - Agents authenticate with their providers' supported sign-in (Codex through
    OpenAI's OAuth login, models gpt-6.1-terra at xhigh and gpt-6-luna at high;
    Claude through its own login), never with credentials in the repository.
- **Console.** An operations console, served by a Tenon program: STATUS and
  correctness trends, the task queue, running and past agent runs with their
  logs and diffs, budgets, approvals waiting for the owner, and the kill switch.
  It reads the same state the Tenon system owns; it is not a second source of
  truth.
- **No staleness.** The repository stays clean as it grows, by mechanism:
  - `./check` fails on: a doc claim without a test or command behind it, a path in
    the docs that does not exist, a file over ~1000 lines or a function over ~80
    lines without a stated reason, unformatted code, and a STATUS.md older than
    the last evidence run.
  - The evidence loop reports dead code (unused functions, modules, tools) and
    duplicated code, as tasks.
  - A weekly hygiene review, alongside the weekly red team, audits for drift
    (KISS, DRY, single responsibility, docs versus behaviour) and lands fixes.
  - Dogfooding: the repository's own tools move from Python and shell to Tenon
    where Tenon can do the job, so the language is used for its own maintenance.
