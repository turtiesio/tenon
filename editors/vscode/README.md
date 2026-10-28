# Tenon for VS Code

Syntax highlighting for Tenon (`.tn`): comments, keywords (control,
declarations, and the modifiers `pub linear unique mut ref extern`), `fn name`
and `fn Type.method` names, types, builtin types and capabilities, enum
variants, numbers (`1_000`, `0xFF`, `0b1010`, `0o17`, `1e-9`), character
literals, raw strings `r"..."`, and strings with escapes (`\{`) and
interpolations `{expr}` / `{expr:SPEC}` whose expressions are highlighted as
code and whose format spec is highlighted separately.

There is no build step and there are no dependencies: the grammar is plain
JSON (`syntaxes/tenon.tmLanguage.json`). A language-server client can be added
later as `main` in `package.json`.

## Install

Without any tools: link (or copy) this folder into VS Code's extension
directory, then restart VS Code.

```sh
ln -s "$PWD/editors/vscode" ~/.vscode/extensions/tenon     # from the repository root
```

Or, if you want a `.vsix` package (this uses npm to fetch `vsce`):

```sh
cd editors/vscode && npx --yes @vscode/vsce package          # writes tenon-0.1.0.vsix
code --install-extension tenon-0.1.0.vsix
```

## Checking the grammar

`python3 tools/vscode_grammar_check.py` (run by `./check`) needs only Python 3.
It checks the JSON, that the grammar's keywords are exactly the lexer's, that
every regex compiles, a few pinned token scopes, and that no string,
interpolation or raw string scope leaks past the end of a line in any `.tn`
file of the repository. Keep regexes to the subset that Oniguruma and Python's
`re` share (no `\G`, `\K`, `\p{...}`); the checker translates `\h` and
`(?<name>...)` and rejects the rest.
