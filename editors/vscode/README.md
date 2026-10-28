# Tenon for VS Code

- Syntax highlighting for Tenon (`.tn`): comments, keywords (control,
  declarations, and the modifiers `pub linear unique mut ref extern`), `fn name`
  and `fn Type.method` names, types, builtin types and capabilities, enum
  variants, numbers (`1_000`, `0xFF`, `0b1010`, `0o17`, `1e-9`), character
  literals, raw strings `r"..."`, and strings with escapes (`\{`) and
  interpolations `{expr}` / `{expr:SPEC}` whose expressions are highlighted as
  code and whose format spec is highlighted separately.
- A client for the Tenon language server, `tenon lsp` (selfhost/lsp.tn):
  - diagnostics: the checker's first diagnostic (parse errors too), exactly as
    `tenon check` reports it, updated as you type (unsaved text is checked;
    imported modules are read from disk, and every open file is checked again
    when one is saved). A file without `fn main` is taken as a module, so
    "program has no 'fn main'" is not shown;
  - hover: the type of the name under the cursor, the signature of a function
    or method (with the comment above its declaration), a struct's fields, an
    enum's variants;
  - go to definition: locals and parameters, functions and methods, constants,
    types, struct fields, enum variants, imported modules and their items, and
    prelude items (in `lib/prelude.tn`);
  - completion: after `.`, the fields and methods of the receiver's type (the
    prelude's methods too), the members of a module (`journal.`) or of a type
    (`Shape.`, `Point.origin`); elsewhere the locals in scope, functions,
    constants, types, variants, imported modules and keywords.

  While a file does not parse, hover and definition answer from its last
  analysis for the lines above the change.

There is no build step and there are no dependencies: the grammar is plain
JSON (`syntaxes/tenon.tmLanguage.json`) and the client (`extension.js`) uses
only the `vscode` API and Node built-ins (it frames JSON-RPC by hand).

## Install

Install `tenon`, which holds the language server (`tenon lsp`), on your
PATH, from the repository root (docs/tools.md):

```sh
tools/install.sh        # ~/.local/bin/tenon; put ~/.local/bin on PATH
```

Then link (or copy) this folder into VS Code's extension directory and
restart VS Code:

```sh
ln -s "$PWD/editors/vscode" ~/.vscode/extensions/tenon     # from the repository root
```

Or, if you want a `.vsix` package (this uses npm to fetch `vsce`):

```sh
cd editors/vscode && npx --yes @vscode/vsce package          # writes tenon-0.2.0.vsix
code --install-extension tenon-0.2.0.vsix
```

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `tenon.serverPath` | `tenon` | the `tenon` executable, started as `tenon lsp`; a bare name is looked up on PATH |
| `tenon.root` | (empty) | the toolchain root: the directory with `lib/prelude.tn` and `lib/std/`, passed as `--root`. Empty: a workspace folder containing `lib/prelude.tn` (the Tenon repository itself), else `$TENON_ROOT`, else the root `tenon` finds from its own path (docs/tools.md) |

Changing a setting restarts the server; so does the command "Tenon: Restart
Language Server". Its messages are in the "Tenon" output channel.

Any other editor with a language-server client can run `tenon lsp [--root DIR]`
the same way: it speaks LSP over stdin and stdout.

## Checking

- `python3 tools/vscode_grammar_check.py` (run by `./check`) needs only Python 3.
  It checks the JSON, that the grammar's keywords are exactly the lexer's, that
  every regex compiles, a few pinned token scopes, and that no string,
  interpolation or raw string scope leaks past the end of a line in any `.tn`
  file of the repository. Keep regexes to the subset that Oniguruma and Python's
  `re` share (no `\G`, `\K`, `\p{...}`); the checker translates `\h` and
  `(?<name>...)` and rejects the rest.
- `python3 tools/lsp_test.py` (run by `./check`) drives `target/tenon lsp`
  through scripted sessions on `tests/lsp/`, asserting exact responses; it
  also runs `node --check extension.js` and `tools/lsp_client_test.js`, which
  loads this client with a stand-in `vscode` module against the real server.
