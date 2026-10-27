// Lexer: source text -> tokens. Newlines become `;` when they end a statement
// (Go-style insertion), except before `.`/`else` or inside ( ) and [ ].

use crate::diag::{Diag, Span};

#[derive(Clone, Debug, PartialEq)]
pub enum Tok {
    Ident(String),
    Kw(&'static str),
    Sym(&'static str),
    Int(i64),
    Float(f64),
    Str(Vec<StrPart>),
    Eof,
}

#[derive(Clone, Debug, PartialEq)]
pub enum StrPart {
    Lit(String),
    Expr(Vec<Token>),
}

#[derive(Clone, Debug, PartialEq)]
pub struct Token {
    pub tok: Tok,
    pub span: Span,
}

const KEYWORDS: &[&str] = &[
    "fn", "let", "var", "if", "else", "while", "for", "in", "match", "return", "break",
    "continue", "struct", "enum", "true", "false", "and", "or", "not", "mut", "self", "linear",
    "unique", "import", "extern",
];

// Longest first so that greedy matching works.
const SYMBOLS: &[&str] = &[
    "..", "==", "!=", "<=", ">=", "->", "=>", "+=", "-=", "*=", "/=", "%=", "+", "-", "*", "/",
    "%", "<", ">", "=", "(", ")", "[", "]", "{", "}", ",", ":", ";", ".", "?", "|", "_",
];

struct Lexer<'a> {
    src: &'a [u8],
    pos: usize,
    line: u32,
    col: u32,
    file: u16,
}

pub fn lex(src: &str, file: u16) -> Result<Vec<Token>, Diag> {
    let mut lx = Lexer { src: src.as_bytes(), pos: 0, line: 1, col: 1, file };
    let raw = lx.tokens(false)?;
    Ok(insert_semis(raw))
}

fn is_ender(t: &Tok) -> bool {
    match t {
        Tok::Ident(_) | Tok::Int(_) | Tok::Float(_) | Tok::Str(_) => true,
        Tok::Sym(s) => matches!(*s, ")" | "]" | "}" | "?" | "_"),
        Tok::Kw(k) => matches!(*k, "return" | "break" | "continue" | "true" | "false" | "self"),
        Tok::Eof => false,
    }
}

// Raw tokens carry newline markers as Sym("\n"); resolve them here.
fn insert_semis(raw: Vec<Token>) -> Vec<Token> {
    let mut out: Vec<Token> = Vec::with_capacity(raw.len());
    let mut stack: Vec<&'static str> = Vec::new();
    for i in 0..raw.len() {
        let t = &raw[i];
        match &t.tok {
            Tok::Sym("\n") => {
                let in_braces = matches!(stack.last(), None | Some(&"{"));
                let prev_ends = out.last().map(|p| is_ender(&p.tok)).unwrap_or(false);
                let next = raw[i + 1..].iter().find(|n| n.tok != Tok::Sym("\n"));
                let next_continues = matches!(
                    next.map(|n| &n.tok),
                    Some(Tok::Sym(".")) | Some(Tok::Kw("else"))
                );
                if in_braces && prev_ends && !next_continues {
                    out.push(Token { tok: Tok::Sym(";"), span: t.span });
                }
                continue;
            }
            Tok::Sym(s @ ("(" | "[" | "{")) => stack.push(s),
            Tok::Sym(")" | "]" | "}") => {
                stack.pop();
            }
            _ => {}
        }
        out.push(t.clone());
    }
    out
}

impl<'a> Lexer<'a> {
    fn span(&self) -> Span {
        Span { file: self.file, line: self.line, col: self.col }
    }
    fn peek(&self, off: usize) -> u8 {
        *self.src.get(self.pos + off).unwrap_or(&0)
    }
    fn bump(&mut self) -> u8 {
        let c = self.peek(0);
        self.pos += 1;
        if c == b'\n' {
            self.line += 1;
            self.col = 1;
        } else {
            self.col += 1;
        }
        c
    }

    // Lex until EOF, or (inside string interpolation) until the unmatched `}`.
    fn tokens(&mut self, in_interp: bool) -> Result<Vec<Token>, Diag> {
        let mut out = Vec::new();
        let mut depth = 0usize;
        loop {
            // whitespace and comments
            loop {
                let c = self.peek(0);
                if c == b'\n' {
                    let sp = self.span();
                    self.bump();
                    out.push(Token { tok: Tok::Sym("\n"), span: sp });
                } else if c == b' ' || c == b'\t' || c == b'\r' {
                    self.bump();
                } else if c == b'/' && self.peek(1) == b'/' {
                    while self.peek(0) != b'\n' && self.pos < self.src.len() {
                        self.bump();
                    }
                } else {
                    break;
                }
            }
            let sp = self.span();
            if self.pos >= self.src.len() {
                if in_interp {
                    return Err(Diag::new(sp, "unterminated interpolation in string"));
                }
                out.push(Token { tok: Tok::Eof, span: sp });
                return Ok(out);
            }
            let c = self.peek(0);
            if in_interp && c == b'}' && depth == 0 {
                self.bump();
                return Ok(out);
            }
            let tok = if c.is_ascii_digit() {
                self.number()?
            } else if c.is_ascii_alphabetic() || (c == b'_' && is_ident_char(self.peek(1))) {
                let start = self.pos;
                while is_ident_char(self.peek(0)) {
                    self.bump();
                }
                let s = std::str::from_utf8(&self.src[start..self.pos]).unwrap();
                match KEYWORDS.iter().find(|k| **k == s) {
                    Some(k) => Tok::Kw(k),
                    None => Tok::Ident(s.to_string()),
                }
            } else if c == b'"' {
                self.string()?
            } else {
                let rest = &self.src[self.pos..];
                let sym = SYMBOLS.iter().find(|s| rest.starts_with(s.as_bytes()));
                match sym {
                    Some(s) => {
                        for _ in 0..s.len() {
                            self.bump();
                        }
                        if *s == "{" {
                            depth += 1;
                        } else if *s == "}" {
                            depth = depth.saturating_sub(1);
                        }
                        Tok::Sym(s)
                    }
                    None => {
                        let ch = std::str::from_utf8(rest)
                            .ok()
                            .and_then(|s| s.chars().next())
                            .unwrap_or('?');
                        return Err(Diag::new(sp, &format!("unexpected character '{}'", ch)));
                    }
                }
            };
            out.push(Token { tok, span: sp });
        }
    }

    fn number(&mut self) -> Result<Tok, Diag> {
        let sp = self.span();
        let start = self.pos;
        while self.peek(0).is_ascii_digit() || self.peek(0) == b'_' {
            self.bump();
        }
        let mut is_float = false;
        if self.peek(0) == b'.' && self.peek(1).is_ascii_digit() {
            is_float = true;
            self.bump();
            while self.peek(0).is_ascii_digit() || self.peek(0) == b'_' {
                self.bump();
            }
        }
        if self.peek(0) == b'e' || self.peek(0) == b'E' {
            let save = (self.pos, self.line, self.col);
            self.bump();
            if self.peek(0) == b'-' || self.peek(0) == b'+' {
                self.bump();
            }
            if self.peek(0).is_ascii_digit() {
                is_float = true;
                while self.peek(0).is_ascii_digit() {
                    self.bump();
                }
            } else {
                (self.pos, self.line, self.col) = save;
            }
        }
        let text: String = std::str::from_utf8(&self.src[start..self.pos])
            .unwrap()
            .chars()
            .filter(|c| *c != '_')
            .collect();
        if is_float {
            text.parse::<f64>()
                .map(Tok::Float)
                .map_err(|_| Diag::new(sp, "invalid float literal"))
        } else {
            text.parse::<i64>()
                .map(Tok::Int)
                .map_err(|_| Diag::new(sp, "integer literal does not fit in Int (64-bit)"))
        }
    }

    fn string(&mut self) -> Result<Tok, Diag> {
        let sp = self.span();
        self.bump(); // opening quote
        let mut parts = Vec::new();
        let mut lit: Vec<u8> = Vec::new();
        loop {
            if self.pos >= self.src.len() {
                return Err(Diag::new(sp, "unterminated string"));
            }
            let c = self.bump();
            match c {
                b'"' => break,
                b'\n' => return Err(Diag::new(sp, "unterminated string (newline in string)")),
                b'\\' => {
                    let e = self.bump();
                    match e {
                        b'n' => lit.push(b'\n'),
                        b't' => lit.push(b'\t'),
                        b'r' => lit.push(b'\r'),
                        b'0' => lit.push(0),
                        b'\\' => lit.push(b'\\'),
                        b'"' => lit.push(b'"'),
                        b'{' => lit.push(b'{'),
                        b'}' => lit.push(b'}'),
                        _ => {
                            return Err(Diag::new(
                                self.span(),
                                &format!("unknown escape '\\{}'", e as char),
                            ));
                        }
                    }
                }
                b'{' => {
                    if !lit.is_empty() {
                        parts.push(StrPart::Lit(String::from_utf8(std::mem::take(&mut lit)).unwrap()));
                    }
                    let isp = self.span();
                    let mut toks = self.tokens(true)?;
                    toks.retain(|t| t.tok != Tok::Sym("\n"));
                    if toks.is_empty() {
                        return Err(Diag::new(isp, "empty interpolation '{}' (write \\{ for a brace)"));
                    }
                    toks.push(Token { tok: Tok::Eof, span: self.span() });
                    parts.push(StrPart::Expr(toks));
                }
                b'}' => return Err(Diag::new(self.span(), "unmatched '}' in string (write \\})")),
                _ => lit.push(c),
            }
        }
        if !lit.is_empty() || parts.is_empty() {
            parts.push(StrPart::Lit(String::from_utf8(lit).unwrap()));
        }
        Ok(Tok::Str(parts))
    }
}

fn is_ident_char(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}
