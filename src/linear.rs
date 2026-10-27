// Linear and unique types (run after type checking).
//
//   linear struct Claim { ... }   must be used exactly once: never copied, never
//                                 dropped; every path must consume it
//   unique struct Handle { ... }  never copied, may be dropped
//
// A value is consumed by passing it by value (argument, `self` of a method,
// return, struct/variant field) or by destructuring it in a `match`. Reading
// fields, comparing and formatting only inspect it. A method's own `self` is
// exempt: the type's methods decide how its values are disposed of.
//
// The analysis is flow-sensitive: branches must agree, a value from outside a
// loop cannot be consumed inside it, and `return`/`break`/`?` may not leave a
// linear value behind.

use crate::ast::*;
use crate::check::{Checked, Res};
use crate::diag::{Diag, Span};
use crate::types::Ty;

type LResult = Result<(), Diag>;

// Generic functions that may take linear or unique type arguments (they consume
// their argument exactly once).
const GENERIC_OK: &[&str] = &["Option.unwrap", "Option.expect", "Result.unwrap", "Result.expect", "panic"];

#[derive(Clone)]
struct Var {
    name: String,
    kind: Kind,
    moved: Option<Span>,
}

struct Walk<'a> {
    c: &'a Checked,
    vars: Vec<Var>,
    loops: Vec<usize>, // vars.len() at the start of each enclosing loop
    diverged: bool,
}

fn err(sp: Span, m: String) -> LResult {
    Err(Diag::new(sp, &m))
}

fn word(k: Kind) -> &'static str {
    if k == Kind::Linear { "linear" } else { "unique" }
}

pub fn check_decls(c: &Checked, prog: &Program) -> LResult {
    for (si, s) in c.structs.iter().enumerate() {
        for (f, t) in &s.fields {
            let k = c.kind_of(t);
            if k != Kind::Plain && s.kind == Kind::Plain || k == Kind::Linear && s.kind == Kind::Unique {
                return err(prog.structs[si].span, format!(
                    "field '{}' of '{}' is {}; declare '{} struct {}'", f, s.name, word(k), word(k), s.name
                ));
            }
        }
    }
    for (ei, e) in c.enums.iter().enumerate() {
        for (v, ts) in &e.variants {
            for t in ts {
                let k = c.kind_of(t);
                if k != Kind::Plain && e.kind == Kind::Plain || k == Kind::Linear && e.kind == Kind::Unique {
                    // Option/Result are generic wrappers: they take the kind of their contents.
                    if e.tparams.iter().any(|p| t.any(&|x| *x == Ty::Param(p.clone()))) {
                        continue;
                    }
                    return err(prog.enums[ei].span, format!(
                        "variant '{}' of '{}' holds a {} value; declare '{} enum {}'", v, e.name, word(k), word(k), e.name
                    ));
                }
            }
        }
    }
    Ok(())
}

pub fn check_fn(c: &Checked, f: &FnDecl, fi: usize) -> LResult {
    let Some(body) = &f.body else { return Ok(()) };
    let info = &c.fns[fi];
    let mut w = Walk { c, vars: vec![], loops: vec![], diverged: false };
    for (n, t) in &info.params {
        let k = c.kind_of(t);
        if k != Kind::Plain && n != "self" {
            w.vars.push(Var { name: n.clone(), kind: k, moved: None });
        }
    }
    w.block(body, true)?;
    w.end_scope(0, body.span)
}

impl<'a> Walk<'a> {
    fn ty(&self, id: Id) -> Option<&Ty> {
        self.c.types.get(&id)
    }
    fn kind(&self, id: Id) -> Kind {
        self.ty(id).map(|t| self.c.kind_of(t)).unwrap_or(Kind::Plain)
    }

    fn consume(&mut self, name: &str, sp: Span) -> LResult {
        let Some(i) = self.vars.iter().rposition(|v| v.name == name) else { return Ok(()) };
        if self.vars[i].moved.is_some() {
            return err(sp, format!(
                "'{}' was already used: a {} value cannot be copied", name, word(self.vars[i].kind)
            ));
        }
        if let Some(&lm) = self.loops.last() {
            if i < lm {
                return err(sp, format!(
                    "'{}' is {} and is consumed inside a loop, so it could be used more than once", name, word(self.vars[i].kind)
                ));
            }
        }
        self.vars[i].moved = Some(sp);
        Ok(())
    }

    // Every linear value declared at or after `from` must have been consumed.
    fn live_check(&self, from: usize, sp: Span, why: &str) -> LResult {
        if self.diverged {
            return Ok(());
        }
        for v in &self.vars[from..] {
            if v.kind == Kind::Linear && v.moved.is_none() {
                return err(sp, format!("linear value '{}' is never used: {} would drop it", v.name, why));
            }
        }
        Ok(())
    }

    fn end_scope(&mut self, mark: usize, sp: Span) -> LResult {
        self.live_check(mark, sp, "the end of this block")?;
        self.vars.truncate(mark);
        Ok(())
    }

    // Run alternative paths from the same state and require them to agree.
    fn branches(&mut self, sp: Span, paths: Vec<&mut dyn FnMut(&mut Self) -> LResult>) -> LResult {
        let before = self.vars.clone();
        let mut outs: Vec<Vec<Var>> = Vec::new();
        let mut all_diverged = true;
        for p in paths {
            self.vars = before.clone();
            self.diverged = false;
            p(self)?;
            if !self.diverged {
                all_diverged = false;
                outs.push(self.vars[..before.len()].to_vec());
            }
        }
        self.vars = before;
        self.diverged = all_diverged;
        if all_diverged {
            return Ok(());
        }
        for i in 0..self.vars.len() {
            let moved: Vec<Option<Span>> = outs.iter().map(|o| o[i].moved).collect();
            let any = moved.iter().find_map(|m| *m);
            if self.vars[i].kind == Kind::Linear && moved.iter().any(|m| m.is_some()) && moved.iter().any(|m| m.is_none()) {
                return err(any.unwrap_or(sp), format!(
                    "linear value '{}' is consumed on some paths but not others; consume it on every path", self.vars[i].name
                ));
            }
            self.vars[i].moved = any;
        }
        Ok(())
    }

    fn block(&mut self, b: &Block, consume: bool) -> LResult {
        let mark = self.vars.len();
        let n = b.stmts.len();
        for (i, s) in b.stmts.iter().enumerate() {
            if self.diverged {
                break;
            }
            match &s.kind {
                StmtKind::Expr(e) if i + 1 == n => self.expr(e, consume)?,
                _ => self.stmt(s)?,
            }
        }
        self.end_scope(mark, b.span)
    }

    fn bind(&mut self, p: &Pattern) -> LResult {
        let k = self.kind(p.id);
        match &p.kind {
            PatKind::Bind(n) if k != Kind::Plain => self.vars.push(Var { name: n.clone(), kind: k, moved: None }),
            PatKind::Wild if k == Kind::Linear => {
                return err(p.span, "'_' would drop a linear value; bind it and consume it".into());
            }
            PatKind::Tuple(ps) | PatKind::Variant(_, _, ps) => {
                for q in ps {
                    self.bind(q)?;
                }
            }
            PatKind::Or(alts) => {
                if k != Kind::Plain {
                    return err(p.span, format!("'|' patterns cannot bind {} values", word(k)));
                }
                for a in alts {
                    self.bind(a)?;
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn stmt(&mut self, s: &Stmt) -> LResult {
        match &s.kind {
            StmtKind::Expr(e) => self.expr(e, true),
            StmtKind::Let { pat, value, .. } => {
                self.expr(value, true)?;
                self.bind(pat)
            }
            StmtKind::Assign { target, value, .. } => {
                self.expr(value, true)?;
                if let ExprKind::Index(b, i) = &target.kind {
                    self.expr(b, false)?;
                    self.expr(i, true)?;
                }
                if self.kind(target.id) == Kind::Linear {
                    let ExprKind::Name(n) = &target.kind else {
                        return err(target.span, "cannot overwrite a linear value in place; it would be dropped".into());
                    };
                    if let Some(v) = self.vars.iter_mut().rev().find(|v| v.name == *n) {
                        if v.moved.is_none() {
                            return err(target.span, format!("assigning to '{}' would drop its linear value; consume it first", n));
                        }
                        v.moved = None;
                    }
                }
                Ok(())
            }
            StmtKind::While { cond, body } => {
                self.loops.push(self.vars.len());
                self.expr(cond, false)?;
                let r = self.branches(s.span, vec![&mut |w: &mut Self| w.block(body, false), &mut |_| Ok(())]);
                self.loops.pop();
                self.diverged = false;
                r
            }
            StmtKind::For { pat, iter, body } => {
                match iter {
                    ForIter::Range(a, b) => {
                        self.expr(a, false)?;
                        self.expr(b, false)?;
                    }
                    ForIter::Each(e) => self.expr(e, false)?,
                }
                self.loops.push(self.vars.len());
                let r = self.branches(s.span, vec![
                    &mut |w: &mut Self| {
                        let mark = w.vars.len();
                        w.bind(pat)?;
                        w.block(body, false)?;
                        w.end_scope(mark, body.span)
                    },
                    &mut |_| Ok(()),
                ]);
                self.loops.pop();
                self.diverged = false;
                r
            }
            StmtKind::Return(v) => {
                if let Some(e) = v {
                    self.expr(e, true)?;
                }
                self.live_check(0, s.span, "this 'return'")?;
                self.diverged = true;
                Ok(())
            }
            StmtKind::Break | StmtKind::Continue => {
                let from = self.loops.last().copied().unwrap_or(0);
                self.live_check(from, s.span, "this 'break'/'continue'")?;
                self.diverged = true;
                Ok(())
            }
        }
    }

    fn generic_args_ok(&self, fi: usize, targs: &[Ty], sp: Span) -> LResult {
        let name = &self.c.fns[fi].name;
        if GENERIC_OK.contains(&name.as_str()) {
            return Ok(());
        }
        for t in targs {
            let k = self.c.kind_of(t);
            if k != Kind::Plain {
                return err(sp, format!(
                    "'{}' is generic and may copy or drop its arguments; it cannot be used with the {} type {}", name, word(k), t
                ));
            }
        }
        Ok(())
    }

    fn expr(&mut self, e: &Expr, consume: bool) -> LResult {
        if let Some(t) = self.ty(e.id) {
            if let Ty::Con(n, a) = t {
                if (n == "List" || n == "Map") && a.iter().any(|x| self.c.kind_of(x) != Kind::Plain) {
                    return err(e.span, format!("{} cannot hold linear or unique values", n));
                }
            }
        }
        match &e.kind {
            ExprKind::Int(_) | ExprKind::Float(_) | ExprKind::Bool(_) | ExprKind::Unit | ExprKind::Path(..) => Ok(()),
            ExprKind::Str(segs) => {
                for s in segs {
                    if let StrSeg::Expr(x) = s {
                        self.expr(x, false)?;
                    }
                }
                Ok(())
            }
            ExprKind::Name(n) => {
                if let Some(Res::Fn(fi, targs)) = self.c.res.get(&e.id) {
                    return self.generic_args_ok(*fi, targs, e.span);
                }
                if consume && self.kind(e.id) != Kind::Plain {
                    if let Some(Res::Local(_)) = self.c.res.get(&e.id) {
                        return self.consume(n, e.span);
                    }
                }
                Ok(())
            }
            ExprKind::Field(b, f) => {
                self.expr(b, false)?;
                if consume && self.kind(e.id) != Kind::Plain {
                    return err(e.span, format!("cannot move {} field '{}' out of a value", word(self.kind(e.id)), f));
                }
                Ok(())
            }
            ExprKind::TupleField(b, _) => {
                if consume && self.kind(e.id) != Kind::Plain {
                    return self.expr(b, true);
                }
                self.expr(b, false)
            }
            ExprKind::Index(b, i) => {
                self.expr(b, false)?;
                self.expr(i, true)
            }
            ExprKind::Call(callee, args) => {
                if let Some(Res::Fn(fi, targs)) = self.c.res.get(&callee.id) {
                    self.generic_args_ok(*fi, targs, e.span)?;
                }
                self.expr(callee, false)?;
                for a in args {
                    self.expr(a, true)?;
                }
                Ok(())
            }
            ExprKind::Method(recv, _, args) => {
                match self.c.res.get(&e.id) {
                    Some(Res::Method(fi, targs)) => {
                        self.generic_args_ok(*fi, targs, e.span)?;
                        let by_value = self.c.fns[*fi].self_kind == Some(SelfKind::Value);
                        self.expr(recv, by_value)?;
                    }
                    _ => self.expr(recv, false)?,
                }
                for a in args {
                    self.expr(a, true)?;
                }
                Ok(())
            }
            ExprKind::Unary(_, x) => self.expr(x, false),
            ExprKind::Binary(op, l, r) => {
                self.expr(l, false)?;
                if *op == BinOp::And || *op == BinOp::Or {
                    return self.branches(e.span, vec![&mut |w: &mut Self| w.expr(r, false), &mut |_| Ok(())]);
                }
                self.expr(r, false)
            }
            ExprKind::If(c, then, els) => {
                self.expr(c, false)?;
                self.branches(e.span, vec![
                    &mut |w: &mut Self| w.block(then, consume),
                    &mut |w: &mut Self| match els {
                        Some(x) => w.expr(x, consume),
                        None => Ok(()),
                    },
                ])
            }
            ExprKind::Match(s, arms) => {
                let destructure = self.kind(s.id) != Kind::Plain;
                self.expr(s, destructure)?;
                let mut paths: Vec<Box<dyn FnMut(&mut Self) -> LResult + '_>> = Vec::new();
                for a in arms {
                    paths.push(Box::new(move |w: &mut Self| {
                        let mark = w.vars.len();
                        if destructure {
                            w.bind(&a.pat)?;
                        }
                        if let Some(g) = &a.guard {
                            w.expr(g, false)?;
                        }
                        w.expr(&a.body, consume)?;
                        w.end_scope(mark, a.body.span)
                    }));
                }
                let refs: Vec<&mut dyn FnMut(&mut Self) -> LResult> =
                    paths.iter_mut().map(|p| p.as_mut() as &mut dyn FnMut(&mut Self) -> LResult).collect();
                self.branches(e.span, refs)
            }
            ExprKind::Block(b) => self.block(b, consume),
            ExprKind::List(xs) | ExprKind::Tuple(xs) => {
                for x in xs {
                    self.expr(x, true)?;
                }
                Ok(())
            }
            ExprKind::MapLit(ps) => {
                for (k, v) in ps {
                    self.expr(k, true)?;
                    self.expr(v, true)?;
                }
                Ok(())
            }
            ExprKind::StructLit(_, fs, base) => {
                for (_, v) in fs {
                    self.expr(v, true)?;
                }
                if let Some(b) = base {
                    self.expr(b, true)?;
                }
                Ok(())
            }
            ExprKind::Try(x) => {
                self.expr(x, true)?;
                self.live_check(0, e.span, "the early return of '?'")
            }
            ExprKind::Lambda(params, _, body) => {
                for (n, t) in &self.c.captures[&e.id] {
                    let k = self.c.kind_of(t);
                    if k != Kind::Plain {
                        return err(e.span, format!("closures cannot capture the {} value '{}'", word(k), n));
                    }
                }
                let Some(Ty::Fn(pts, _)) = self.ty(e.id).cloned() else { return Ok(()) };
                let mut inner = Walk { c: self.c, vars: vec![], loops: vec![], diverged: false };
                for ((n, _), t) in params.iter().zip(&pts) {
                    let k = self.c.kind_of(t);
                    if k != Kind::Plain {
                        inner.vars.push(Var { name: n.clone(), kind: k, moved: None });
                    }
                }
                inner.expr(body, true)?;
                inner.end_scope(0, body.span)
            }
        }
    }
}
