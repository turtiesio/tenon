// `tenon ast FILE`: a canonical S-expression dump of the parsed file, which
// the self-hosted parser (selfhost/parser.tn) must reproduce exactly.
// Positions are written as @LINE:COL on expressions, statements and patterns.

use crate::ast::*;
use crate::diag::Span;

pub fn dump(src: &str) -> String {
    let mut prog = Program { structs: vec![], enums: vec![], fns: vec![], imports: vec![], modules: vec![] };
    let mut next_id = 0;
    let r = crate::lexer::lex(src, 1).and_then(|t| crate::parser::parse_program(&t, &mut next_id, &mut prog));
    if let Err(d) = r {
        return format!("error {}:{} {}\n", d.span.line, d.span.col, d.msg);
    }
    let mut out = String::new();
    for i in &prog.imports {
        out.push_str(&format!("(import {})\n", i.name));
    }
    for s in &prog.structs {
        out.push_str(&format!("(struct{}{} {}{}", vis(s.public), kind(s.kind), s.name, tps(&s.tparams)));
        for ((f, t), p) in s.fields.iter().zip(&s.pub_fields) {
            out.push_str(&format!(" ({}{} {})", if *p { "pub " } else { "" }, f, ty(t)));
        }
        out.push_str(")\n");
    }
    for e in &prog.enums {
        out.push_str(&format!("(enum{}{} {}{}", vis(e.public), kind(e.kind), e.name, tps(&e.tparams)));
        for v in &e.variants {
            let fs: Vec<String> = v.fields.iter().map(ty).collect();
            out.push_str(&format!(" ({}{})", v.name, fs.iter().map(|f| format!(" {}", f)).collect::<String>()));
        }
        out.push_str(")\n");
    }
    for f in &prog.fns {
        let owner = f.owner.as_ref().map(|o| format!("{}.", ty(o))).unwrap_or_default();
        let selfk = match f.self_kind {
            Some(SelfKind::Value) => " self",
            Some(SelfKind::Mut) => " mut-self",
            None => "",
        };
        let head = if f.is_const { "const" } else { "fn" };
        out.push_str(&format!("({}{} {}{}{}{}", head, vis(f.public), owner, f.name, tps(&f.tparams), selfk));
        for p in &f.params {
            out.push_str(&format!(" ({}{}{} {})", p.name, if p.by_ref { " ref" } else { "" }, if p.by_mut { " mut" } else { "" }, ty(&p.ty)));
        }
        if let Some(r) = &f.ret {
            out.push_str(&format!(" -> {}", ty(r)));
        }
        match &f.body {
            Some(b) => out.push_str(&format!(" {})\n", block(b))),
            None => out.push_str(" extern)\n"),
        }
    }
    out
}

fn vis(p: bool) -> &'static str {
    if p { " pub" } else { "" }
}
fn kind(k: Kind) -> &'static str {
    match k {
        Kind::Plain => "",
        Kind::Linear => " linear",
        Kind::Unique => " unique",
    }
}
fn tps(ps: &[String]) -> String {
    if ps.is_empty() { String::new() } else { format!("[{}]", ps.join(", ")) }
}
fn at(s: Span) -> String {
    format!("@{}:{}", s.line, s.col)
}
fn list(xs: impl Iterator<Item = String>) -> String {
    xs.map(|x| format!(" {}", x)).collect()
}

fn ty(t: &TypeExpr) -> String {
    match &t.kind {
        TypeExprKind::Named(n, a) if a.is_empty() => n.clone(),
        TypeExprKind::Named(n, a) => format!("{}[{}]", n, a.iter().map(ty).collect::<Vec<_>>().join(", ")),
        TypeExprKind::Fn(a, r) => format!("fn({}) -> {}", a.iter().map(ty).collect::<Vec<_>>().join(", "), ty(r)),
        TypeExprKind::Tuple(a) => format!("({})", a.iter().map(ty).collect::<Vec<_>>().join(", ")),
    }
}

fn block(b: &Block) -> String {
    format!("(block{})", list(b.stmts.iter().map(stmt)))
}

fn stmt(s: &Stmt) -> String {
    let body = match &s.kind {
        StmtKind::Let { pat: p, mutable, ty: t, value, els } => format!(
            "let{} {}{} {}{}",
            if *mutable { " var" } else { "" },
            pat(p),
            t.as_ref().map(|t| format!(" : {}", ty(t))).unwrap_or_default(),
            expr(value),
            els.as_ref().map(|b| format!(" (else {})", block(b))).unwrap_or_default()
        ),
        StmtKind::Expr(e) => format!("expr {}", expr(e)),
        StmtKind::Assign { target, op, value } => {
            format!("assign{} {} {}", op.map(|o| format!(" {:?}", o)).unwrap_or_default(), expr(target), expr(value))
        }
        StmtKind::While { cond, body } => format!("while {} {}", expr(cond), block(body)),
        StmtKind::For { pat: p, iter, body } => {
            let it = match iter {
                ForIter::Range(a, b) => format!("(range {} {})", expr(a), expr(b)),
                ForIter::Each(e) => format!("(each {})", expr(e)),
            };
            format!("for {} {} {}", pat(p), it, block(body))
        }
        StmtKind::Return(v) => format!("return{}", v.as_ref().map(|e| format!(" {}", expr(e))).unwrap_or_default()),
        StmtKind::Break => "break".into(),
        StmtKind::Continue => "continue".into(),
    };
    format!("({}{})", at(s.span), format!(" {}", body))
}

fn pat(p: &Pattern) -> String {
    let body = match &p.kind {
        PatKind::Wild => "_".into(),
        PatKind::Bind(n) => format!("bind {}", n),
        PatKind::Int(i) => format!("int {}", i),
        PatKind::Str(s) => format!("str {}", quote(s)),
        PatKind::Bool(b) => format!("bool {}", b),
        PatKind::Tuple(ps) => format!("tuple{}", list(ps.iter().map(pat))),
        PatKind::Variant(q, v, ps) => {
            format!("variant {}{}{}", q.as_ref().map(|q| format!("{}.", q)).unwrap_or_default(), v, list(ps.iter().map(pat)))
        }
        PatKind::Or(ps) => format!("or{}", list(ps.iter().map(pat))),
    };
    format!("({} {})", at(p.span), body)
}

fn quote(s: &str) -> String {
    let mut q = String::new();
    crate::value::quote(s, &mut q);
    q
}

fn expr(e: &Expr) -> String {
    let body = match &e.kind {
        ExprKind::Int(i) => format!("int {}", i),
        ExprKind::Float(f) => format!("float {}", crate::value::fmt_float(*f)),
        ExprKind::Bool(b) => format!("bool {}", b),
        ExprKind::Str(segs) => format!(
            "str{}",
            list(segs.iter().map(|s| match s {
                StrSeg::Lit(l) => quote(l),
                StrSeg::Expr(x) => expr(x),
            }))
        ),
        ExprKind::Unit => "unit".into(),
        ExprKind::Name(n) => format!("name {}", n),
        ExprKind::Path(t, m) => format!("path {} {}", t, m),
        ExprKind::Field(b, f) => format!("field {} {}", expr(b), f),
        ExprKind::TupleField(b, i) => format!("tfield {} {}", expr(b), i),
        ExprKind::Index(a, b) => format!("index {} {}", expr(a), expr(b)),
        ExprKind::Call(f, args) => format!("call {}{}", expr(f), list(args.iter().map(expr))),
        ExprKind::Method(r, m, args) => format!("method {} {}{}", expr(r), m, list(args.iter().map(expr))),
        ExprKind::Unary(op, x) => format!("{} {}", if *op == UnOp::Neg { "neg" } else { "not" }, expr(x)),
        ExprKind::Binary(op, l, r) => format!("{:?} {} {}", op, expr(l), expr(r)),
        ExprKind::If(c, t, els) => {
            format!("if {} {}{}", expr(c), block(t), els.as_ref().map(|x| format!(" {}", expr(x))).unwrap_or_default())
        }
        ExprKind::Match(s, arms) => format!(
            "match {}{}",
            expr(s),
            list(arms.iter().map(|a| if a.fallback {
                // the `_` arm added by `if let` / `while let` (parser.rs `if_let`)
                format!("(else {})", expr(&a.body))
            } else {
                format!(
                    "(arm {}{} {})",
                    pat(&a.pat),
                    a.guard.as_ref().map(|g| format!(" (guard {})", expr(g))).unwrap_or_default(),
                    expr(&a.body)
                )
            }))
        ),
        ExprKind::Block(b) => block(b),
        ExprKind::List(xs) => format!("list{}", list(xs.iter().map(expr))),
        ExprKind::MapLit(ps) => format!("map{}", list(ps.iter().map(|(k, v)| format!("({} {})", expr(k), expr(v))))),
        ExprKind::Tuple(xs) => format!("tuple{}", list(xs.iter().map(expr))),
        ExprKind::StructLit(n, fs, base) => format!(
            "new {}{}{}",
            n,
            list(fs.iter().map(|(f, v)| format!("({} {})", f, expr(v)))),
            base.as_ref().map(|b| format!(" (base {})", expr(b))).unwrap_or_default()
        ),
        ExprKind::Try(x) => format!("try {}", expr(x)),
        ExprKind::MutArg(x) => format!("mutarg {}", expr(x)),
        ExprKind::Lambda(ps, r, b) => format!(
            "lambda ({}){} {}",
            ps.iter()
                .map(|(n, t)| t.as_ref().map(|t| format!("{}: {}", n, ty(t))).unwrap_or(n.clone()))
                .collect::<Vec<_>>()
                .join(", "),
            r.as_ref().map(|r| format!(" -> {}", ty(r))).unwrap_or_default(),
            expr(b)
        ),
    };
    format!("({} {})", at(e.span), body)
}
