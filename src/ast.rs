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
    Let { pat: Pattern, mutable: bool, ty: Option<TypeExpr>, value: Expr },
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
    Expr(Expr),
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
}

#[derive(Debug, Clone)]
pub struct Arm {
    pub pat: Pattern,
    pub guard: Option<Expr>,
    pub body: Expr,
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
