// Syntax tree. Every expression and pattern has a unique id; the checker
// records types and name resolutions in side tables keyed by that id.

use crate::diag::Span;

pub type Id = u32;

#[derive(Debug, Clone)]
pub struct Program {
    pub structs: Vec<StructDecl>,
    pub enums: Vec<EnumDecl>,
    pub fns: Vec<FnDecl>,
    pub imports: Vec<Import>,
    pub modules: Vec<String>, // module name per source file id ("" for prelude and main)
}

#[derive(Debug, Clone)]
pub struct Import {
    pub file: u16, // importing file
    pub name: String,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct TypeExpr {
    pub kind: TypeExprKind,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub enum TypeExprKind {
    Named(String, Vec<TypeExpr>),
    Fn(Vec<TypeExpr>, Box<TypeExpr>),
    Tuple(Vec<TypeExpr>),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Plain,
    Linear, // must be consumed exactly once
    Unique, // may be dropped, never copied
}

#[derive(Debug, Clone)]
pub struct StructDecl {
    pub name: String,
    pub tparams: Vec<String>,
    pub fields: Vec<(String, TypeExpr)>,
    pub pub_fields: Vec<bool>,
    pub kind: Kind,
    pub public: bool,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct EnumDecl {
    pub name: String,
    pub tparams: Vec<String>,
    pub variants: Vec<VariantDecl>,
    pub kind: Kind,
    pub public: bool,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct VariantDecl {
    pub name: String,
    pub fields: Vec<TypeExpr>,
    pub span: Span,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SelfKind {
    Value,
    Mut,
}

#[derive(Debug, Clone)]
pub struct FnDecl {
    pub name: String,
    pub owner: Option<TypeExpr>, // `fn Type[Args].name`; bare unknown names in Args are params
    pub tparams: Vec<String>,    // the function's own type params
    pub self_kind: Option<SelfKind>,
    pub params: Vec<Param>,
    pub ret: Option<TypeExpr>,
    pub body: Option<Block>, // None: `extern`, implemented by each backend
    pub public: bool,
    pub is_const: bool, // `const NAME: T = expr`: a zero-parameter function used as a value
    pub span: Span,
}

impl FnDecl {
    pub fn owner_name(&self) -> Option<&str> {
        match &self.owner {
            Some(TypeExpr { kind: TypeExprKind::Named(n, _), .. }) => Some(n),
            _ => None,
        }
    }
    pub fn full_name(&self) -> String {
        match self.owner_name() {
            Some(o) => format!("{}.{}", o, self.name),
            None => self.name.clone(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Param {
    pub name: String,
    pub by_ref: bool, // `x: ref T`: inspected, never consumed (for linear/unique T)
    pub by_mut: bool, // `x: mut T`: the caller passes a place (`f(mut v)`) that the function may change
    pub ty: TypeExpr,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct Block {
    pub stmts: Vec<Stmt>,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct Stmt {
    pub kind: StmtKind,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub enum StmtKind {
    // `let PAT = value else { must leave }` when `els` is present
    Let { pat: Pattern, mutable: bool, ty: Option<TypeExpr>, value: Expr, els: Option<Block> },
    Expr(Expr),
    Assign { target: Expr, op: Option<BinOp>, value: Expr },
    While { cond: Expr, body: Block },
    For { pat: Pattern, iter: ForIter, body: Block },
    Return(Option<Expr>),
    Break,
    Continue,
}

#[derive(Debug, Clone)]
pub enum ForIter {
    Range(Expr, Expr),
    Each(Expr),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BinOp {
    Add,
    Sub,
    Mul,
    Div,
    Rem,
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    And,
    Or,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnOp {
    Neg,
    Not,
}

#[derive(Debug, Clone)]
pub struct Expr {
    pub id: Id,
    pub span: Span,
    pub kind: ExprKind,
}

#[derive(Debug, Clone)]
pub enum StrSeg {
    Lit(String),
    Expr(Expr, Option<FmtSpec>), // `{e}` or `{e:SPEC}`
}

// A format spec `{e:SPEC}` (docs/reference.md §8):
//   [[fill]align]['0']width[',']['.'precision][x|X|b|o]   (every part optional)
#[derive(Debug, Clone, PartialEq)]
pub struct FmtSpec {
    pub text: String,
    pub fill: char,
    pub align: Option<char>, // '<', '>' or '^'; None: numbers right, text left
    pub zero: bool,          // sign-aware zero padding (Int, Float)
    pub width: usize,
    pub group: bool,         // ',' between groups of three digits (Int, Float)
    pub prec: Option<usize>, // Float decimals, as Float.to_fixed
    pub radix: Option<char>, // 'x', 'X', 'b', 'o' (Int)
}

impl FmtSpec {
    // The grammar check; the type rules are in the checker. Messages are
    // mirrored by selfhost/parser.tn `parse_spec`.
    pub fn parse(text: &str) -> Result<FmtSpec, String> {
        let bad = |why: String| Err(format!("malformed format spec '{}': {}", text, why));
        let cs: Vec<char> = text.chars().collect();
        if cs.is_empty() {
            return Err("empty format spec after ':' (remove the ':' or write a spec such as {x:>5})".into());
        }
        let is_align = |c: char| c == '<' || c == '>' || c == '^';
        let (mut i, mut fill, mut align) = (0, ' ', None);
        if cs.len() >= 2 && is_align(cs[1]) {
            fill = cs[0];
            align = Some(cs[1]);
            i = 2;
        } else if is_align(cs[0]) {
            align = Some(cs[0]);
            i = 1;
        }
        let mut zero = false;
        if i + 1 < cs.len() && cs[i] == '0' && cs[i + 1].is_ascii_digit() {
            zero = true;
            i += 1;
        }
        let digits = |i: &mut usize| {
            let start = *i;
            while *i < cs.len() && cs[*i].is_ascii_digit() {
                *i += 1;
            }
            cs[start..*i].iter().collect::<String>()
        };
        let w = digits(&mut i);
        if w.len() > 3 {
            return bad(format!("width {} is too large (at most 999)", w));
        }
        if align.is_some() && w.is_empty() {
            return bad("an alignment needs a width, as in {x:>5}".into());
        }
        if zero && align.is_some() {
            return bad("'0' padding cannot be combined with a fill or alignment".into());
        }
        let width = w.parse::<usize>().unwrap_or(0);
        let group = i < cs.len() && cs[i] == ',';
        if group {
            i += 1;
        }
        let mut prec = None;
        if i < cs.len() && cs[i] == '.' {
            i += 1;
            let p = digits(&mut i);
            if p.is_empty() {
                return bad("'.' must be followed by the number of decimals, as in {x:.2}".into());
            }
            if p.len() > 3 || p.parse::<usize>().unwrap() > 100 {
                return bad(format!("precision {} is too large (at most 100)", p));
            }
            prec = Some(p.parse::<usize>().unwrap());
        }
        let mut radix = None;
        if i < cs.len() && matches!(cs[i], 'x' | 'X' | 'b' | 'o') {
            radix = Some(cs[i]);
            i += 1;
        }
        if group && radix.is_some() {
            return bad(format!("',' grouping cannot be combined with the radix '{}'", radix.unwrap()));
        }
        if i < cs.len() {
            let c = cs[i];
            let hint = match c {
                'f' => " (decimals are written {x:.2}, without 'f')".to_string(),
                'd' => " (Int is decimal by default; drop the 'd')".to_string(),
                _ => " (the grammar is [[fill]align][0][width][,][.precision][x|X|b|o])".to_string(),
            };
            return bad(format!("unexpected '{}'{}", c, hint));
        }
        Ok(FmtSpec { text: text.to_string(), fill, align, zero, width, group, prec, radix })
    }

    // ',' grouping of the integer digits of a number's text (after the sign,
    // up to the first non-digit: "-1234.5" -> "-1,234.5"; "inf" unchanged).
    // With '0' the padding zeros are digits too, grouped like the others, and
    // the text never starts with ',': it may be one longer than the width.
    // Mirrored by runtime/tenon.h tn_fmt_group.
    fn group_digits(&self, body: &str) -> String {
        let (sign, rest) = if body.starts_with('-') { body.split_at(1) } else { ("", body) };
        let n = rest.bytes().take_while(|c| c.is_ascii_digit()).count();
        if n == 0 {
            return body.to_string();
        }
        let (int, tail) = rest.split_at(n);
        let mut k = n;
        if self.zero {
            while sign.len() + k + (k - 1) / 3 + tail.len() < self.width {
                k += 1;
            }
        }
        let digits = "0".repeat(k - n) + int;
        let mut out = sign.to_string();
        for (i, c) in digits.chars().enumerate() {
            if i > 0 && (k - i) % 3 == 0 {
                out.push(',');
            }
            out.push(c);
        }
        out + tail
    }

    // Pad `body` (already converted: digits, decimals or text) to the width.
    // `numeric`: right-aligned by default, and '0' pads after the sign.
    pub fn pad(&self, body: &str, numeric: bool, out: &mut String) {
        let grouped;
        let body = if self.group {
            grouped = self.group_digits(body);
            grouped.as_str()
        } else {
            body
        };
        let n = body.chars().count();
        if n >= self.width {
            out.push_str(body);
            return;
        }
        let pad = self.width - n;
        if self.zero {
            let (sign, digits) = if body.starts_with('-') { body.split_at(1) } else { ("", body) };
            out.push_str(sign);
            out.extend(std::iter::repeat('0').take(pad));
            out.push_str(digits);
            return;
        }
        let left = match self.align.unwrap_or(if numeric { '>' } else { '<' }) {
            '<' => 0,
            '^' => pad / 2,
            _ => pad,
        };
        out.extend(std::iter::repeat(self.fill).take(left));
        out.push_str(body);
        out.extend(std::iter::repeat(self.fill).take(pad - left));
    }
}

// The digits of an Int in a format-spec radix, '-' for negatives.
pub fn radix_digits(v: i64, r: char) -> String {
    let m = v.unsigned_abs();
    let d = match r {
        'x' => format!("{:x}", m),
        'X' => format!("{:X}", m),
        'b' => format!("{:b}", m),
        _ => format!("{:o}", m),
    };
    if v < 0 { format!("-{}", d) } else { d }
}

#[derive(Debug, Clone)]
pub enum ExprKind {
    Int(i64),
    Float(f64),
    Bool(bool),
    Str(Vec<StrSeg>),
    Unit,
    Name(String),
    Path(String, String), // Type.member
    Field(Box<Expr>, String),
    TupleField(Box<Expr>, usize),
    Index(Box<Expr>, Box<Expr>),
    Call(Box<Expr>, Vec<Expr>),
    Method(Box<Expr>, String, Vec<Expr>),
    Unary(UnOp, Box<Expr>),
    Binary(BinOp, Box<Expr>, Box<Expr>),
    If(Box<Expr>, Block, Option<Box<Expr>>),
    Match(Box<Expr>, Vec<Arm>),
    Block(Block),
    List(Vec<Expr>),
    MapLit(Vec<(Expr, Expr)>),
    Tuple(Vec<Expr>),
    StructLit(String, Vec<(String, Expr)>, Option<Box<Expr>>),
    Try(Box<Expr>),
    Lambda(Vec<(String, Option<TypeExpr>)>, Option<TypeExpr>, Box<Expr>),
    MutArg(Box<Expr>), // `mut place` as an argument to a `mut` parameter
}

#[derive(Debug, Clone)]
pub struct Arm {
    pub pat: Pattern,
    pub guard: Option<Expr>,
    pub body: Expr,
    // The `_` arm the parser adds for `if let` / `while let` (see Parser::if_let):
    // never reported as unreachable, and named in the linear "would drop" message.
    pub fallback: bool,
}

#[derive(Debug, Clone)]
pub struct Pattern {
    pub id: Id,
    pub span: Span,
    pub kind: PatKind,
}

#[derive(Debug, Clone)]
pub enum PatKind {
    Wild,
    Bind(String),
    Int(i64),
    Str(String),
    Bool(bool),
    Tuple(Vec<Pattern>),
    Variant(Option<String>, String, Vec<Pattern>),
    Or(Vec<Pattern>),
}
