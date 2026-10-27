// calc: tokenizer, recursive-descent parser, tree-walking evaluator (std only).
use std::collections::HashMap;
use std::io::{BufRead, Write};

const MAX_DEPTH: usize = 1000;
const MAX_NESTING: usize = 200;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Kind {
    Num, Ident, Let, Fn, If, Then, Else,
    Plus, Minus, Star, Slash, Percent,
    LParen, RParen, Comma, Assign,
    EqEq, NotEq, Less, LessEq, Greater, GreaterEq,
    End,
}

#[derive(Clone, Copy)]
struct Token<'a> {
    kind: Kind,
    text: &'a str,
    num: i64,
    col: usize,
}

type Res<T> = Result<T, String>;

fn is_digit(c: u8) -> bool { c.is_ascii_digit() }
fn is_ident_start(c: u8) -> bool { c.is_ascii_alphabetic() || c == b'_' }
fn is_ident_char(c: u8) -> bool { is_ident_start(c) || is_digit(c) }

fn utf8_len(c: u8) -> usize {
    if c >= 240 { 4 } else if c >= 224 { 3 } else if c >= 192 { 2 } else { 1 }
}

fn keyword(w: &str) -> Kind {
    match w {
        "let" => Kind::Let,
        "fn" => Kind::Fn,
        "if" => Kind::If,
        "then" => Kind::Then,
        "else" => Kind::Else,
        _ => Kind::Ident,
    }
}

fn tokenize(line: &str) -> Res<Vec<Token<'_>>> {
    let s = line.as_bytes();
    let n = s.len();
    let mut toks = Vec::new();
    let mut i = 0;
    while i < n {
        let c = s[i];
        let start = i;
        if c == b' ' || c == b'\t' || c == b'\r' {
            i += 1;
        } else if c == b'/' && i + 1 < n && s[i + 1] == b'/' {
            i = n;
        } else if is_digit(c) {
            while i < n && is_digit(s[i]) { i += 1; }
            let text = &line[start..i];
            match text.parse::<i64>() {
                Ok(num) => toks.push(Token { kind: Kind::Num, text, num, col: start + 1 }),
                Err(_) => return Err(format!("integer literal {} is too large at column {}", text, start + 1)),
            }
        } else if is_ident_start(c) {
            while i < n && is_ident_char(s[i]) { i += 1; }
            let text = &line[start..i];
            toks.push(Token { kind: keyword(text), text, num: 0, col: start + 1 });
        } else {
            let next = if i + 1 < n { s[i + 1] } else { 0 };
            let mut kind = Kind::End;
            let mut width = 1;
            match c {
                b'+' => kind = Kind::Plus,
                b'-' => kind = Kind::Minus,
                b'*' => kind = Kind::Star,
                b'/' => kind = Kind::Slash,
                b'%' => kind = Kind::Percent,
                b'(' => kind = Kind::LParen,
                b')' => kind = Kind::RParen,
                b',' => kind = Kind::Comma,
                b'=' => if next == b'=' { kind = Kind::EqEq; width = 2 } else { kind = Kind::Assign },
                b'!' => if next == b'=' { kind = Kind::NotEq; width = 2 },
                b'<' => if next == b'=' { kind = Kind::LessEq; width = 2 } else { kind = Kind::Less },
                b'>' => if next == b'=' { kind = Kind::GreaterEq; width = 2 } else { kind = Kind::Greater },
                _ => {}
            }
            if kind == Kind::End {
                let end = (i + utf8_len(c)).min(n);
                return Err(format!("unexpected character '{}' at column {}", &line[i..end], i + 1));
            }
            toks.push(Token { kind, text: &line[i..i + width], num: 0, col: i + 1 });
            i += width;
        }
    }
    toks.push(Token { kind: Kind::End, text: "", num: 0, col: n + 1 });
    Ok(toks)
}

#[derive(Clone, Copy)]
enum Op { Add, Sub, Mul, Div, Mod, Eq, Ne, Lt, Le, Gt, Ge }

enum Expr {
    Num(i64),
    Var(String),
    Neg(Box<Expr>),
    Bin(Op, Box<Expr>, Box<Expr>),
    If(Box<Expr>, Box<Expr>, Box<Expr>),
    Call(String, Vec<Expr>),
}

enum Stmt {
    DefVar(String, Expr),
    DefFn(String, Vec<String>, Expr),
    Show(Expr),
}

struct Parser<'a, 'b> {
    toks: &'b [Token<'a>],
    pos: usize,
    depth: usize,
}

fn describe(t: &Token) -> String {
    if t.kind == Kind::End { "end of line".to_string() } else { format!("'{}'", t.text) }
}

fn unexpected(t: &Token, wanted: &str) -> String {
    format!("expected {} but found {} at column {}", wanted, describe(t), t.col)
}

impl<'a, 'b> Parser<'a, 'b> {
    fn peek(&self) -> Token<'a> { self.toks[self.pos] }

    fn next(&mut self) -> Token<'a> {
        let t = self.toks[self.pos];
        if t.kind != Kind::End { self.pos += 1; }
        t
    }

    fn expect(&mut self, kind: Kind, wanted: &str) -> Res<Token<'a>> {
        let t = self.peek();
        if t.kind != kind { return Err(unexpected(&t, wanted)); }
        Ok(self.next())
    }

    fn finish(&self) -> Res<()> {
        let t = self.peek();
        if t.kind != Kind::End {
            return Err(format!("unexpected {} at column {}", describe(&t), t.col));
        }
        Ok(())
    }

    fn enter(&mut self) -> Res<()> {
        self.depth += 1;
        if self.depth > MAX_NESTING {
            return Err(format!("expression nested too deeply (limit {}) at column {}", MAX_NESTING, self.peek().col));
        }
        Ok(())
    }

    fn expr(&mut self) -> Res<Expr> {
        self.enter()?;
        let r = self.equality();
        self.depth -= 1;
        r
    }

    fn equality(&mut self) -> Res<Expr> {
        let mut left = self.relational()?;
        while self.peek().kind == Kind::EqEq || self.peek().kind == Kind::NotEq {
            let op = if self.next().kind == Kind::EqEq { Op::Eq } else { Op::Ne };
            let right = self.relational()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn relational(&mut self) -> Res<Expr> {
        let mut left = self.additive()?;
        loop {
            let op = match self.peek().kind {
                Kind::Less => Op::Lt,
                Kind::LessEq => Op::Le,
                Kind::Greater => Op::Gt,
                Kind::GreaterEq => Op::Ge,
                _ => break,
            };
            self.next();
            let right = self.additive()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn additive(&mut self) -> Res<Expr> {
        let mut left = self.term()?;
        while self.peek().kind == Kind::Plus || self.peek().kind == Kind::Minus {
            let op = if self.next().kind == Kind::Plus { Op::Add } else { Op::Sub };
            let right = self.term()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn term(&mut self) -> Res<Expr> {
        let mut left = self.unary()?;
        loop {
            let op = match self.peek().kind {
                Kind::Star => Op::Mul,
                Kind::Slash => Op::Div,
                Kind::Percent => Op::Mod,
                _ => break,
            };
            self.next();
            let right = self.unary()?;
            left = Expr::Bin(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn unary(&mut self) -> Res<Expr> {
        if self.peek().kind == Kind::Minus {
            self.enter()?;
            self.next();
            let operand = self.unary();
            self.depth -= 1;
            return Ok(Expr::Neg(Box::new(operand?)));
        }
        self.primary()
    }

    fn call_args(&mut self) -> Res<Vec<Expr>> {
        let mut args = Vec::new();
        if self.peek().kind == Kind::RParen {
            self.next();
            return Ok(args);
        }
        loop {
            args.push(self.expr()?);
            if self.peek().kind == Kind::Comma {
                self.next();
            } else {
                self.expect(Kind::RParen, "',' or ')'")?;
                break;
            }
        }
        Ok(args)
    }

    fn primary(&mut self) -> Res<Expr> {
        let t = self.peek();
        match t.kind {
            Kind::Num => {
                self.next();
                Ok(Expr::Num(t.num))
            }
            Kind::Ident => {
                self.next();
                if self.peek().kind == Kind::LParen {
                    self.next();
                    let args = self.call_args()?;
                    Ok(Expr::Call(t.text.to_string(), args))
                } else {
                    Ok(Expr::Var(t.text.to_string()))
                }
            }
            Kind::LParen => {
                self.next();
                let inner = self.expr()?;
                self.expect(Kind::RParen, "')'")?;
                Ok(inner)
            }
            Kind::If => {
                self.next();
                let cond = self.expr()?;
                self.expect(Kind::Then, "'then'")?;
                let yes = self.expr()?;
                self.expect(Kind::Else, "'else'")?;
                let no = self.expr()?;
                Ok(Expr::If(Box::new(cond), Box::new(yes), Box::new(no)))
            }
            _ => Err(unexpected(&t, "an expression")),
        }
    }

    fn params(&mut self) -> Res<Vec<String>> {
        let mut names: Vec<String> = Vec::new();
        if self.peek().kind == Kind::RParen {
            self.next();
            return Ok(names);
        }
        loop {
            let t = self.expect(Kind::Ident, "a parameter name")?;
            if names.iter().any(|n| n == t.text) {
                return Err(format!("duplicate parameter '{}' at column {}", t.text, t.col));
            }
            names.push(t.text.to_string());
            if self.peek().kind == Kind::Comma {
                self.next();
            } else {
                self.expect(Kind::RParen, "',' or ')'")?;
                break;
            }
        }
        Ok(names)
    }
}

fn parse_line(line: &str) -> Res<Option<Stmt>> {
    let toks = tokenize(line)?;
    if toks.len() == 1 { return Ok(None); }
    let mut p = Parser { toks: &toks, pos: 0, depth: 0 };
    let first = p.peek();
    if first.kind == Kind::Let {
        p.next();
        let name = p.expect(Kind::Ident, "a variable name")?;
        p.expect(Kind::Assign, "'='")?;
        let e = p.expr()?;
        p.finish()?;
        Ok(Some(Stmt::DefVar(name.text.to_string(), e)))
    } else if first.kind == Kind::Fn {
        p.next();
        let name = p.expect(Kind::Ident, "a function name")?;
        p.expect(Kind::LParen, "'('")?;
        let params = p.params()?;
        p.expect(Kind::Assign, "'='")?;
        let body = p.expr()?;
        p.finish()?;
        Ok(Some(Stmt::DefFn(name.text.to_string(), params, body)))
    } else {
        let e = p.expr()?;
        p.finish()?;
        Ok(Some(Stmt::Show(e)))
    }
}

// ---- checked arithmetic ----

fn add(a: i64, b: i64) -> Res<i64> {
    a.checked_add(b).ok_or_else(|| format!("integer overflow in {} + {}", a, b))
}

fn sub(a: i64, b: i64) -> Res<i64> {
    a.checked_sub(b).ok_or_else(|| format!("integer overflow in {} - {}", a, b))
}

fn neg(a: i64) -> Res<i64> {
    a.checked_neg().ok_or_else(|| format!("integer overflow in -({})", a))
}

fn mul(a: i64, b: i64) -> Res<i64> {
    a.checked_mul(b).ok_or_else(|| format!("integer overflow in {} * {}", a, b))
}

fn div(a: i64, b: i64) -> Res<i64> {
    if b == 0 { return Err("division by zero".to_string()); }
    a.checked_div(b).ok_or_else(|| format!("integer overflow in {} / -1", a))
}

fn rem(a: i64, b: i64) -> Res<i64> {
    if b == 0 { return Err("division by zero".to_string()); }
    if b == -1 { return Ok(0); }
    Ok(a % b)
}

fn apply(op: Op, a: i64, b: i64) -> Res<i64> {
    match op {
        Op::Add => add(a, b),
        Op::Sub => sub(a, b),
        Op::Mul => mul(a, b),
        Op::Div => div(a, b),
        Op::Mod => rem(a, b),
        Op::Eq => Ok((a == b) as i64),
        Op::Ne => Ok((a != b) as i64),
        Op::Lt => Ok((a < b) as i64),
        Op::Le => Ok((a <= b) as i64),
        Op::Gt => Ok((a > b) as i64),
        Op::Ge => Ok((a >= b) as i64),
    }
}

// ---- evaluator ----

struct FnDef {
    params: Vec<String>,
    body: Expr,
}

struct Interp {
    vars: HashMap<String, i64>,
    fns: HashMap<String, FnDef>,
}

// The parameters of the function being evaluated, with their values.
struct Env<'a> {
    names: &'a [String],
    vals: &'a [i64],
}

impl Env<'_> {
    fn get(&self, name: &str) -> Option<i64> {
        self.names.iter().position(|n| n == name).map(|i| self.vals[i])
    }
}

fn plural(n: usize, word: &str) -> String {
    if n == 1 { format!("{} {}", n, word) } else { format!("{} {}s", n, word) }
}

impl Interp {
    fn eval(&self, e: &Expr, env: &Env, depth: usize) -> Res<i64> {
        match e {
            Expr::Num(n) => Ok(*n),
            Expr::Var(name) => {
                if let Some(v) = env.get(name) { return Ok(v); }
                if let Some(v) = self.vars.get(name) { return Ok(*v); }
                if self.fns.contains_key(name) {
                    Err(format!("'{}' is a function, not a variable", name))
                } else {
                    Err(format!("unknown variable '{}'", name))
                }
            }
            Expr::Neg(x) => neg(self.eval(x, env, depth)?),
            Expr::Bin(op, l, r) => {
                let a = self.eval(l, env, depth)?;
                let b = self.eval(r, env, depth)?;
                apply(*op, a, b)
            }
            Expr::If(c, yes, no) => {
                if self.eval(c, env, depth)? != 0 { self.eval(yes, env, depth) } else { self.eval(no, env, depth) }
            }
            Expr::Call(name, args) => self.call(name, args, env, depth),
        }
    }

    fn call(&self, name: &str, args: &[Expr], env: &Env, depth: usize) -> Res<i64> {
        let f = match self.fns.get(name) {
            Some(f) => f,
            None => {
                if self.vars.contains_key(name) || env.get(name).is_some() {
                    return Err(format!("'{}' is not a function", name));
                }
                return Err(format!("unknown function '{}'", name));
            }
        };
        if args.len() != f.params.len() {
            return Err(format!("function '{}' takes {}, got {}", name, plural(f.params.len(), "argument"), args.len()));
        }
        let mut vals = Vec::with_capacity(args.len());
        for a in args {
            vals.push(self.eval(a, env, depth)?);
        }
        if depth >= MAX_DEPTH {
            return Err(format!("call depth limit ({}) exceeded in '{}'", MAX_DEPTH, name));
        }
        self.eval(&f.body, &Env { names: &f.params, vals: &vals }, depth + 1)
    }

    // Runs one statement; Ok(Some(text)) is output to print.
    fn run(&mut self, stmt: Stmt) -> Res<Option<String>> {
        let empty = Env { names: &[], vals: &[] };
        match stmt {
            Stmt::DefVar(name, e) => {
                if self.fns.contains_key(&name) {
                    return Err(format!("'{}' is already defined as a function", name));
                }
                let v = self.eval(&e, &empty, 0)?;
                self.vars.insert(name, v);
                Ok(None)
            }
            Stmt::DefFn(name, params, body) => {
                if self.vars.contains_key(&name) {
                    return Err(format!("'{}' is already defined as a variable", name));
                }
                self.fns.insert(name, FnDef { params, body });
                Ok(None)
            }
            Stmt::Show(e) => Ok(Some(self.eval(&e, &empty, 0)?.to_string())),
        }
    }
}

fn main() {
    let stdin = std::io::stdin();
    let mut input = stdin.lock();
    let stdout = std::io::stdout();
    let mut out = std::io::BufWriter::new(stdout.lock());
    let mut interp = Interp { vars: HashMap::new(), fns: HashMap::new() };
    let mut statements = 0;
    let mut errors = 0;
    let mut buf: Vec<u8> = Vec::new();
    loop {
        buf.clear();
        if input.read_until(b'\n', &mut buf).unwrap() == 0 { break; }
        if buf.ends_with(b"\n") {
            buf.pop();
            if buf.ends_with(b"\r") { buf.pop(); }
        }
        let line = String::from_utf8_lossy(&buf);
        let result = match parse_line(&line) {
            Ok(None) => continue,
            Ok(Some(stmt)) => interp.run(stmt),
            Err(msg) => Err(msg),
        };
        statements += 1;
        match result {
            Ok(Some(text)) => writeln!(out, "{}", text).unwrap(),
            Ok(None) => {}
            Err(msg) => {
                errors += 1;
                writeln!(out, "error: {}", msg).unwrap();
            }
        }
    }
    writeln!(out, "bye ({} statements, {} errors)", statements, errors).unwrap();
    out.flush().unwrap();
    std::process::exit(if errors > 0 { 1 } else { 0 });
}
