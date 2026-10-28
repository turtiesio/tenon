# Packages

A package is a directory with a `tenon.toml` manifest. It can depend on other
packages by local path or by git URL and tag. `tenonc fetch` resolves the
dependencies, fetches git packages into a cache and pins everything in
`tenon.lock`. Builds then work offline from the lock and the cache. There is
no registry.

Implementation: `selfhost/pkg.tn` (manifest, lock, resolution, cache, content
hash) and `selfhost/pkgtoml.tn` (the TOML subset). `selfhost/front.tn`
`load_in` does the import resolution. Test: `tools/pkg_test.sh`, which is
part of `./check`.

## Layout

```
app/
  tenon.toml        the manifest
  tenon.lock        written by `tenonc fetch`; commit it
  src/main.tn       the app's own files: any layout
util/
  tenon.toml
  src/util.tn       a dependency's entry module: src/NAME.tn
  src/helper.tn     its other modules sit next to the entry module
```

A package used as a dependency must have its entry module at
`src/NAME.tn`, where `NAME` is the package's name. `import NAME` loads that
file. The package's other modules are the files next to it (`src/helper.tn`),
reached from the entry module with `import helper` as usual. The root
package (the one you build) may lay out its files any way it likes.

## The manifest: tenon.toml

```toml
[package]
name = "app"            # required: a module name (a-z, 0-9, _; not starting with a digit)
version = "0.1.0"       # required: any non-empty string; recorded in the lock, not compared

[dependencies]          # optional
util = { path = "../util" }                                    # a local directory
json = { git = "https://example.org/json.git", tag = "v1.2.0" } # a git repository at a tag
```

- A dependency's key is the name you import it by. It must match the
  `[package] name` in the dependency's own manifest, and it must be a module
  name.
- `path` is relative to the directory of the manifest that declares it (an
  absolute path is also accepted). `git` is any URL `git clone` accepts:
  `https://`, `ssh://`, `file://`. `tag` is a tag name, checked out as
  `refs/tags/TAG`.
- A dependency has either `path`, or both `git` and `tag`. Any other key is
  an error.
- A dependency may not have the name of a standard library module (`journal`,
  `regex`). That is an error at the line declaring it.
- A git package may depend only on git packages. A `path` inside a pinned
  snapshot would point outside it.
- Only the root package's `tenon.lock` counts. A dependency's own lock file is
  ignored.

## The TOML subset

`tenon.toml` and `tenon.lock` use the small subset of TOML below. Anything
outside it is refused with `FILE:LINE: message`:

- The file is read one line at a time. A line is blank, a comment, a table
  header or a key/value pair. Spaces and tabs around tokens are ignored, and
  a line may end in `\r`.
- Comments: `#` to the end of the line, also after a header or a value (but
  not inside a string).
- Table header: `[name]` or `[name.sub]`, made of bare keys joined by `.`.
  The same header twice is an error. `[[...]]` (arrays of tables) is refused.
- Bare key: one or more ASCII letters, digits, `_` and `-`. Quoted keys and
  dotted keys (`a.b = ...`) are refused.
- `key = value`: a key given twice in a table is an error, and so is a
  key/value pair before the first header.
- A value is one of:
  - a basic string `"..."` with the escapes `\"`, `\\`, `\n` and `\t`. Any
    other escape, a raw control character, `'literal'` strings and
    `"""multi-line"""` strings are refused;
  - an inline table `{ k = "v", k2 = "v2" }` on one line, holding strings
    only. Empty `{}` is allowed. A trailing comma and nested tables are
    refused.
- Numbers, booleans, dates and arrays are refused.

What a valid manifest may contain is narrower still: the tables
`[package]` (keys `name` and `version`) and `[dependencies]` (inline tables
with `path`, or with `git` and `tag`). Every string in it must be non-empty.

## The lock: tenon.lock

`tenonc fetch` writes the lock with one table per dependency, direct or
transitive, sorted by name. It writes the file only if its text changes, so
running `fetch` again with nothing new leaves it byte for byte the same.

```toml
# tenon.lock: written by `tenonc fetch` (docs/packages.md); do not edit.

[package.json]
version = "1.2.0"
source = "git"
git = "https://example.org/json.git"
tag = "v1.2.0"
commit = "6d723b9a51710aa1eb760fb5b8fed79ea41b3100"
hash = "5b306b024aa8742b762a8ed833c0b734"

[package.util]
version = "0.3.0"
source = "path"
path = "../util"
hash = "1dda5e6759912c0a0d614de51609a59f"
```

- `path` is the package's directory relative to the root package, with `.`
  and `..` folded.
- `commit` is the commit the tag resolved to when it was first fetched.
- `hash` is the content hash below.

## Content hash

A package's source files are every `*.tn` file and every `tenon.toml` under
its directory, recursively. Names that start with `.` are skipped, which
covers `.git`. Paths are taken relative to the package directory and sorted
bytewise.

The hash covers, for each file in that order, the bytes of
`PATH "\n" LENGTH "\n" CONTENT`, where LENGTH is the decimal byte length.
Each byte `x`, taken as `x + 1`, feeds four polynomial hashes:
`h = (h * m + x) mod p` with `(m, p, initial h)` =
`(31, 2147483629, 1)`, `(37, 2147483587, 2)`, `(131, 2147483563, 3)` and
`(257, 2147483399, 4)`. The result is the four values as 8 hex digits each,
32 digits in all (`pkg.content_hash`).

The hash detects corruption and accidental edits. It is not cryptographic
and does not protect against a deliberate forgery.

## Resolution

Dependencies are resolved depth-first from the root manifest. A package is
identified by its name, so each name has exactly one source in a build:

- If the same name is reached again from the same source (the same `path`
  relative to the root, or the same `git` and `tag`), it is the same package.
  This is how diamonds are shared.
- If the same name comes from two different sources (two tags, or a path and
  a git URL), that is an error naming both sources and the manifest lines
  that require them: `package 'pad' is required from two sources: git URL tag
  v0.2.0 (by CACHE/tenon.toml:7) and git URL tag v0.1.0 (by app/tenon.toml:8)`.
- If a package depends on itself, directly or through others, that is an
  error showing the path: `dependency cycle: c2 -> c3 -> c2 (at
  ../c3/tenon.toml:7)`. A dependency with the root package's name counts as a
  cycle too.

## Commands

### `tenonc fetch [DIR]`

Resolves the package in `DIR`, or, without `DIR`, the nearest `tenon.toml`
at or above the current directory. It then writes `tenon.lock` and prints
one line per package. For each git dependency:

- if the lock already has it with the same `git` and `tag`, and the cache
  holds that commit with the locked hash, fetch uses the cached copy and does
  not touch the network;
- otherwise it runs `git clone -q --no-checkout URL TMP` and
  `git checkout -q REV`, where REV is the locked commit if there is one, else
  `refs/tags/TAG`. It records `git rev-parse HEAD`, deletes `.git` and moves
  the files to the cache. This replaces a damaged cache entry.

A locked commit is kept even if the tag later moves upstream. To pick up a
moved tag, delete that package's table from the lock, or delete the lock.
`fetch` also recomputes the hash of every path package.

### `tenonc run`, `build`, `emit`, `check`, `test`

A file is inside a package when a `tenon.toml` is in its directory or any
directory above it. For a relative path the search climbs with `..`, so it
works from a subdirectory too, for at most 64 levels. Inside a package these
commands resolve dependencies **offline**:

- With dependencies but no `tenon.lock`, they fail with
  `no tenon.lock for tenon.toml; run \`tenonc fetch\``. A package with no
  dependencies needs no lock.
- If the lock does not match the manifests, they fail with
  `tenon.lock is out of date with tenon.toml (DETAIL); run \`tenonc fetch\``.
  This happens when a dependency is missing from the lock or listed with a
  different source, or when the lock lists a package that is no longer needed.
- A git package must be in the cache at its locked commit, else they fail
  with `... is not in the cache ...; run \`tenonc fetch\``.
- A git package's content hash must equal the lock's. If it does not, they
  fail with `package 'x' in the cache (DIR) does not match tenon.lock
  (content hash H, locked H'): the cache is corrupt or was modified; delete
  that directory and run \`tenonc fetch\``.
- **Path dependencies are live and git dependencies are pinned.** A path
  package is read from its directory as it is now. If its files changed
  since the last fetch, that is not an error, even though the hash in the lock
  is then out of date. `tenonc fetch` refreshes it. Adding or removing a
  dependency in a path package's manifest does make the lock out of date,
  because resolution re-reads every manifest.

Package errors are reported as `tenonc: MESSAGE` with exit status 1. The
language server (`selfhost/tenonlsp.tn`) resolves imports the same way, and
shows a package error as the diagnostic at the start of the file.

## Imports in a package

`import name` in a file is resolved in this order:

1. `name.tn` next to the importing file;
2. the entry module `src/name.tn` of a dependency `name` of the package the
   importing file belongs to. A file belongs to the dependency whose
   directory is the longest prefix of its path, and otherwise to the root
   package;
3. the standard library.

Inside a dependency, `import` therefore reaches that package's own modules
and its own dependencies, never the root's. The privacy rules are unchanged:
only `pub` items are visible to importers.

Module names are global within a program. If two different files would be
the module `name` (the app's `helper.tn` and a dependency's
`src/helper.tn`), that is an error: `module 'helper' is both A and B; module
names must be unique in a program`.

## Cache

`$TENON_HOME/cache/git/HASH/`, with `TENON_HOME` defaulting to `~/.tenon`. It
holds one directory per fetched (URL, commit), with no `.git`, named by a
hash of `URL@COMMIT`. Deleting it is always safe: `tenonc fetch` refills it.

## Network

Only `tenonc fetch` uses the network, through `git` and only for a git
package that the cache lacks. The tests use local repositories under
`file://` URLs and never contact a remote host.
