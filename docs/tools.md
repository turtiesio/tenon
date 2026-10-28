# The `tenon` command line

One executable, `tenon`, holds the whole toolchain: the interpreter, the
compiler to native code (through C), the checker, the test runner, the
formatter, the language server and the package fetcher. It is written in
Tenon (`selfhost/tenon.tn`). This page is the reference for its commands,
flags, environment variables and exit statuses.

## Installing

```sh
tools/install.sh              # into ~/.local: ~/.local/bin/tenon, ~/.local/lib/tenon/
tools/install.sh /opt/tenon   # into another PREFIX
```

`tools/install.sh [PREFIX]` needs `cargo` and a C compiler. It builds the
toolchain the way `./check` does, then copies:

| Path | What |
|---|---|
| `PREFIX/bin/tenon` | the executable |
| `PREFIX/lib/tenon/lib/` | the prelude, the standard library (`std/`) and `v2/` |
| `PREFIX/lib/tenon/runtime/tenon.h` | the C runtime that native builds include |

PREFIX defaults to `~/.local`. Put `PREFIX/bin` on `PATH`. The installed
`tenon` finds its files from its own path, so `TENON_ROOT` is not needed
(see "The toolchain root" below). Running the script again replaces the
installed files.

The build has three stages. The frozen seed (`bootstrap/`, a Rust program
built to `target/release/tenon-seed`) builds stage 0 (`target/tenon0`, C at
`-O0`). Stage 0 builds stage 1 (`target/tenon`, `-O2`), which is the `tenon`
that gets installed. In the repository, `./check` builds all three, so
`target/tenon` is ready to use. It finds the repository as its root.

## Usage

`tenon help` (or `--help`, `-h`) prints:

```
usage: tenon COMMAND [ARGUMENTS] [FLAGS]
  tenon run FILE.tn [ARGS...]          interpret (reference semantics); ARGS go to the program
  tenon build FILE.tn [-o OUT] [-O0]   compile to a native executable via C (OUT: FILE without .tn)
  tenon emit FILE.tn                   print the generated C
  tenon check FILE.tn                  type-check only
  tenon test DIR... [--bless]          run the tests in DIR/run and DIR/reject (both backends)
  tenon fmt [--check] FILE... | -      format in place; --check: list unformatted files; -: stdin
  tenon lsp                            the language server, on standard input and output
  tenon fetch [DIR]                    resolve the package's dependencies, write tenon.lock
  tenon tokens FILE.tn                 the lexer's dump
  tenon ast FILE.tn                    the parser's dump
  tenon help | --help, tenon --version
Every command takes --root DIR, the toolchain root (default: $TENON_ROOT, else found from
this executable's path), in any position (for run: before FILE). Reference: docs/tools.md
```

`tenon --version` prints `tenon VERSION`.

### Flags

- A flag may come anywhere after the command, before or after the other
  arguments: `tenon build -O0 prog.tn -o prog` is the same as
  `tenon build prog.tn -o prog -O0`. `--root DIR` may also come before the
  command (`tenon --root DIR check prog.tn`).
- `run` is the exception: everything after its FILE goes to the program
  unchanged, flags included. `tenon run prog.tn --root x` passes
  `["--root", "x"]` to `prog.tn`. Flags for `run` itself go before FILE.
- These are usage errors, which print the problem and the usage text and
  exit with status 2: an unknown command, a flag the command does not take
  (`tenon build prog.tn --bless`), a flag without its value (`-o` at the
  end), and the wrong number of arguments (`tenon check a.tn b.tn`).

| Flag | Commands | Meaning |
|---|---|---|
| `--root DIR` | all | the toolchain root (below) |
| `-o OUT` | `build` | the executable to write; default: FILE without `.tn` |
| `-O0` | `build` | compile the C without optimization (the default is `-O2`); faster to build |
| `--bless` | `test` | write the golden files instead of comparing with them |
| `--check` | `fmt` | do not rewrite; list the files that are not formatted |
| `--help`, `-h` | all | print the usage text, exit 0 |

`test` also takes `--worker K/N`, `--tmp DIR` and `--exe PATH`. These are
for its own worker processes only.

### The toolchain root

The root is the directory holding `lib/prelude.tn`, `lib/std/` and
`runtime/tenon.h`. Every command that compiles reads them from the root at
compile time. The root is the first of these:

1. `--root DIR`;
2. `$TENON_ROOT`;
3. a directory found from the path of the running `tenon`, EXE. With X the
   directory above EXE's directory (`X/bin/tenon`, `X/target/tenon`), the
   candidates are `X/lib/tenon` (the layout that `tools/install.sh` makes)
   and then `X` itself (the repository, for `target/tenon`). The first that
   contains `lib/prelude.tn` wins. EXE is
   read from `/proc` on Linux. Elsewhere it is the name the process was
   started with, looked up on `PATH` if it has no `/`. Symbolic links are
   not followed, so link to an installed `tenon` from a directory where the
   rule also holds, or copy it;
4. the current directory.

`tokens`, `ast` and `fmt` do not need the root.

## Commands

### `tenon run FILE.tn [ARGS...]`

Interprets FILE with the reference interpreter. The program gets ARGS as
`sys.args`. `tenon run` ends with the program's own exit status, so a trap
gives 70, 71, 72 or 74 as the program would (reference §9). If the program
is rejected, `tenon run` prints the diagnostic and exits with status 1.

Workers (reference §18) run on one thread under a deterministic scheduler,
with the same results as `tenon build` for every program whose output does
not depend on scheduling (selfhost/iwork.tn). A worker runs when `main`
waits (`recv`, `join`, `try_recv`), until it finishes or waits itself. A
waiting worker is resumed by running it again from the start, with every
effect it already had (output, files, channels) replayed from a log instead
of repeated. So resuming a worker costs the work it did before, and a worker
blocked in a socket read or `Poller.wait` without a timeout holds up the
others. Use `tenon build` for speed.

### `tenon build FILE.tn [-o OUT] [-O0]`

Compiles FILE to C, then compiles the C with `$CC` (default `cc`) into the
executable OUT. A large program is split into several C files that compile
in parallel. Builds are cached. An entry in the cache is the executable plus
its C text, and it is used only when the new C text is exactly the same
(`TENON_CACHE`, `TENON_KEEP_C` below). The native executable must behave
exactly as `tenon run` does: the test suite checks this for every test.

### `tenon emit FILE.tn`

Prints the C program that `build` compiles, as one text.

### `tenon check FILE.tn`

Type-checks FILE and the modules it imports. Prints nothing when the
program is accepted. Otherwise prints the first diagnostic,
`FILE:LINE:COL: error: MESSAGE` with the line and a caret, and exits with
status 1.

### `tenon test DIR... [--bless]`

Runs the test corpus in each DIR:

| Path | The test |
|---|---|
| `DIR/run/NAME.tn` | runs with the interpreter and as a native build (`-O0`); both must print `NAME.out`: standard output, then `exit: N`, then each standard-error line as `stderr: LINE` |
| `DIR/reject/NAME.tn` | must be rejected; its first line `// error: TEXT` names a substring of the expected diagnostic |
| `DIR/lex/NAME.tn`, `DIR/parse/NAME.tn` | only under a `v2/` directory: what `tenon tokens` / `tenon ast` prints must be `NAME.tokens` / `NAME.ast` |

A run test may start with `// stdin: TEXT` (`\n` and `\xHH` escapes) and
`// args: A B C`. A file whose first line is `// module` is imported by
tests and is not run itself. Each test runs from its own directory, with a
20-second timeout. `--bless` writes missing or different golden files
instead of failing. The tests are shared among 8 worker processes, which run
the same `tenon` executable (`test` finds its own path as in rule 3 above;
no environment variable is needed). The last line is the summary,
`tests: N run (x2 backends), N reject, N failed, Ts`. The exit status is 1
if any test failed.

### `tenon fmt [--check] FILE...`, `tenon fmt -`

Rewrites each FILE in the canonical layout ("Formatting" below). Each file is
written atomically, and only if it changes. With `--check`, nothing is
written: the files that are not formatted are listed, one per line, and the
exit status is 1 if there are any. `tenon fmt -` formats standard input to
standard output. A file that cannot be read, parsed or written is reported
and left unchanged, and the exit status is 2.

### `tenon lsp`

The language server: the Language Server Protocol 3.17 over standard input
and output (JSON-RPC 2.0 with `Content-Length` framing). It reports
diagnostics as you type, the same first diagnostic as `tenon check`, and
answers hover, go to definition and completion. Buffers are checked from
their unsaved text. Inside a package, imports resolve as in `tenon check`.
The exit status is 0 after `shutdown` then `exit`, otherwise 1.

To use it in an editor, configure the editor to start `tenon lsp` (add
`--root DIR` if the rule above does not find the root). For VS Code, use
the extension in `editors/vscode`. Its setting `tenon.serverPath` (default
`tenon`, looked up on `PATH`) names the executable, which it starts with
`lsp`. `tenon.root` sets `--root` ([editors/vscode/README.md](../editors/vscode/README.md)).

### `tenon fetch [DIR]`

Resolves the dependencies of the package in DIR, or of the nearest
`tenon.toml` at or above the current directory. Git packages are fetched
into the cache, and `tenon.lock` is written. This is the only command that
uses the network. Inside a package, `run`, `build`, `emit`, `check`, `test`
and `lsp` resolve imports offline from `tenon.lock` and the cache. They fail
with a request to run `tenon fetch` when the lock is missing or out of date.
The details are in [docs/packages.md](packages.md).

### `tenon tokens FILE.tn`, `tenon ast FILE.tn`

Print the lexer's tokens, or the parser's syntax tree, of FILE (or the first
lexer or parser error). The test runner and `tools/selfhost.sh` compare
these dumps.

## Formatting

The layout that `tenon fmt` writes (reference §16):

- Line breaks are the author's: long lines are not reflowed, and lines are
  never joined. The only line added splits `a; b` in a block written on
  several lines (a block written on one line, `{ t += x; i += 1 }`, stays).
- Indentation is 4 spaces per line that opened a bracket still open (several
  brackets opened on one line count once). A line starting with `)`, `]` or
  `}` is indented as the line that opened it.
- In a block, a line that continues the previous one (it starts with `.`,
  `and`, `or` or a binary operator, or the previous line ends with `=`,
  `=>`, `->`, an operator...) is indented 4 more than the first line of its
  statement. A line starting with `else` lines up with its `if`. A block
  after a head that spans lines (`if a` / `and b {`) is indented from the
  head's first line.
- One space around binary operators, `=`, `->`, `=>` and `|`, after `,`,
  `;` and `:`, and inside braces written on one line (`Point { x: 1 }`; but
  `{}`). No space before `(` and `[` in calls, indexing and generics
  (`f(x)`, `xs[i]`, `List[Int]`), after a unary `-`, around `.` and `..`
  (`0..n`, `..base`), or before `?`, `,`, `:` and closing brackets.
- A list whose closing bracket starts a line (arguments, parameters,
  elements, struct fields, enum variants, match arms) ends with a comma,
  except after a block arm's `}` or a struct literal's `..base`. A list
  closed on the same line has no trailing comma. A `;` at the end of a line
  is removed where the newline ends the statement anyway.
- Comments are kept. A comment on its own line takes the indentation of the
  next line (one level deeper before a closing bracket); end-of-line comments
  on consecutive lines are aligned one space after the longest line of code.
- At most one blank line in a row, and none at the start or end of the file,
  after an opening bracket or before a closing one.
- String and character literals are copied byte for byte, interpolations
  and format specs included.

The formatter checks its own output before writing it: the formatted text
must lex to the same tokens as the original (up to a `,` or `;` before a
closing bracket) and must parse. `tools/fmt_check.sh` (run by `./check`)
also checks that every file in the repository except those listed in
`tools/fmt_skip.txt` is formatted, that formatting is idempotent, and that
`tenon ast` of each file it changes is unchanged except positions.

## Environment variables

| Variable | Used by | Meaning | Default |
|---|---|---|---|
| `TENON_ROOT` | every command that compiles, `lsp` | the toolchain root, when there is no `--root` | found from the executable's path, else the current directory |
| `TENON_HOME` | packages | holds the package cache, `$TENON_HOME/cache/git/` | `~/.tenon` |
| `TENON_CACHE` | `build` | the build cache directory; `off` disables the cache | `$TMPDIR/tenon-cache` (`/tmp/tenon-cache` without `TMPDIR`) |
| `TENON_KEEP_C` | `build` | if set, keep the C text as `OUT.c` next to the output, as one file, and bypass the cache | unset |
| `CC` | `build` | the C compiler | `cc` |

Programs see their environment through `sys.proc.env(NAME)`. `tenon` passes
its environment on to the programs it runs.

The repository's own tools also read `TENON`, `TENON0` and `SEED`, the
executables they test ([docs/dev/testing.md](dev/testing.md)).

## Exit statuses

| Status | Meaning |
|---|---|
| 0 | success: the program was accepted, built or formatted, all tests passed, the server was shut down |
| 1 | a diagnostic: the program was rejected (also by `run`, `build`, `emit` and `check`), a package error, the C compiler failed, a test failed, `fmt --check` found unformatted files, the language server ended without `shutdown` |
| 2 | a usage error (with the usage text), or a file that cannot be read or written: the source, the prelude or the runtime under the root, a file `fmt` cannot read, parse or write |
| 70 | a trap. Under `run` this is the program's trap. Otherwise it is an internal error in `tenon` itself; please report it |
| 71 | out of memory |
| 72 | stack overflow |
| 74 | standard output could not be written |

70, 71, 72 and 74 are reserved for the runtime. A Tenon program's `main`
may not return them (reference §9). `tenon run` exits with the status of the
program it runs, whatever it is, and so does a native executable.

## The seed

`target/release/tenon-seed` is the frozen Rust bootstrap (`bootstrap/`,
governance/README.md). Its only job is to build stage 0 of `tenon`. It
has the older command set (`run build emit check test tokens ast`) and none
of the newer language features (traits, workers: code under `v2/`
directories). `tools/selfhost.sh` cross-checks `tenon` against it on the
corpus ([docs/dev/compiler.md](dev/compiler.md)). It is not installed.
