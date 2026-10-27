#!/usr/bin/env bash
# Scenario test; $RUN is the command that runs the program (interpreter or binary).
# Each case shows its input (prefixed "| ") and then the program's output.
set -u
D=$(mktemp -d)
trap 'rm -rf "$D"' EXIT

# case NAME INPUT: INPUT is interpreted by printf %b and fed on stdin
case_() {
  echo "=== $1"
  printf '%b\n' "$2" | sed 's/^/| /'
  printf '%b' "$2" | $RUN 2>&1
  echo "[exit $?]"
}

case_ "empty input" ''
case_ "only blank lines" '\n\n   \n'
case_ "headings 1-6" '# one\n## two\n### three\n#### four\n##### five\n###### six'
case_ "not headings" '####### seven\n#nospace\n#\n\\# x'
case_ "paragraphs" 'first line\nsecond line\n\nnext paragraph\n   indented line\n\n\n\nlast'
case_ "paragraph interrupted by blocks" 'text\n# head\nmore\n- item\nafter\n> q\nend\n---\nx\n```\nc\n```\ny'
case_ "bullet lists" '- one\n* two\n- three'
case_ "ordered lists" '1. one\n2. two\n10. ten\n7. seven'
case_ "list kinds switch" '- a\n1. b\n2. c\n* d'
case_ "list items with inline" '- **bold** item\n- a [link](u) and `code`'
case_ "marker without text" '-\n- \n1.\n-x\n1.x'
case_ "horizontal rules" 'above\n---\nbelow\n\n---\n  ---  \n----\n--'
case_ "fenced code" '```\nplain\n  indented <b>&amp;</b> "q"\n\n    after blank\n```\nafter'
case_ "fenced code with language" '```rust\nfn main() {}\n```\n``` python extra words\nprint("hi")\n```'
case_ "code is never formatted" '```\n# not a heading\n- not a list\n**not bold** `x` [a](b)\n> not a quote\n---\n```'
case_ "empty fenced code" '```\n```\n```js\n```'
case_ "unclosed fence" 'before\n```\nline one\nline two'
case_ "fence with backtick in info is a paragraph" '```code``` here'
case_ "language is escaped" '```a"b<c\nx\n```'
case_ "block quote" '> quoted text\n> continues\n>\n> second paragraph\nafter quote'
case_ "block quote without space" '>tight\n>  two spaces'
case_ "block quote containing blocks" '> # title\n> - a\n> - b\n> ```\n> code\n>\n> more\n> ```\n> ---\n> text'
case_ "nested block quote" '> outer\n> > inner\n> > more\n> back'
case_ "unclosed fence stops at quote end" '> ```\n> code\nplain'
case_ "bold" 'a **bold** b **two words** c'
case_ "em" 'a *em* b *two words* c'
case_ "inline code" 'use `x < y` or `a && b` or `**no** *format*`'
case_ "links" '[text](http://example.com/a?b=1&c=2) and [two words](rel/path)'
case_ "nested inline" '**bold *em* inside**\n\n*em **bold** inside*\n\n***both***\n\n[**bold link**](u)\n\n[`code` and *em*](u)\n\n**a [link](u) and `code`**'
case_ "closers are found by plain search" '**[**link**](u)**\n\n*a `b* c`\n\n*a **b *c* d** e*'
case_ "star runs" '**a***\n\n***a**\n\n****\n\n*****\n\n******a******'
case_ "adjacent markup" '*a*`b`**c**[d](e)*f*'
case_ "escaping" 'a & b < c > d "e"\n# & < > "\n- & < > "\n> & < > "\n[a&b](x"y<z)'
case_ "unclosed markers" '**open\n\n*open\n\n`open\n\n[open\n\n[open](\n\n[open](x\n\n[open] (x)\n\n[a](b c)'
case_ "markers that cannot open or close" '2 * 3 * 4\n\n** a **\n\n*a *\n\n** \n\na * x'
case_ "empty markup stays literal" '`` and **** and [](x) and [x]()'
case_ "unclosed after closed" '**a** and **b\n\n`a` and `b\n\n*a* and *b'
case_ "markup across lines" 'a **bold\nacross** b\n*em\nacross*'
case_ "unicode" '# Héllo *wörld* ✓\n`日本語` [ünï](ü)'
case_ "windows line endings" '# head\r\n\r\ntext\r\nmore\r\n```\r\ncode\r\n```\r\n'
case_ "no trailing newline" 'last line without newline'
case_ "everything" '# Title\n\nIntro with **bold**, *em*, `code` and [a link](http://x.y).\n\n> A quote\n> - with a list\n\n1. first\n2. second\n\n---\n\n```sh\necho "hi" > out\n```\nDone.'

# files and errors
step() { echo "\$ mdhtml $*"; (cd "$D" && $RUN "$@" 2>&1); echo "[exit $?]"; }
printf '# From a file\n\ntext & more\n' > "$D/in.md"
: > "$D/empty.md"
mkdir "$D/adir"
step in.md
step empty.md
step missing.md
step adir
step in.md extra
step a b c
echo "# file argument wins over stdin"
echo "stdin text" | (cd "$D" && $RUN in.md 2>&1)
echo "[exit $?]"
echo "# no input at all"
$RUN < /dev/null 2>&1
echo "[exit $?]"
