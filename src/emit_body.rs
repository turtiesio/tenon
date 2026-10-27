// C backend, part 2: lowering of function bodies (statements, expressions,
// places, patterns, closures). See emit_c.rs for the ownership protocol.

use crate::ast::*;
use crate::check::Res;
use crate::emit_c::*;
use crate::interp::{visit_children, visit_stmt};
use crate::types::Ty;
use std::collections::HashMap;
use std::fmt::Write;

pub struct CV {
    pub code: String,
    pub owned: bool,
}

fn bor(code: impl Into<String>) -> CV {
    CV { code: code.into(), owned: false }
}

fn int_lit(i: i64) -> String {
    if i == i64::MIN { "(-9223372036854775807LL - 1)".into() } else { format!("{}LL", i) }
}

enum Step {
    Field(String),
    List(Ty, String),
    Map(Ty, String),
}

struct Place {
    root: String, // C pointer to the root variable
    steps: Vec<Step>,
}

// Can evaluating e assign to an existing local (so earlier borrowed reads go stale)?
fn may_mutate(c: &crate::check::Checked, e: &Expr) -> bool {
    let mut found = false;
    fn walk(c: &crate::check::Checked, e: &Expr, found: &mut bool) {
        if *found {
            return;
        }
        match &e.kind {
            ExprKind::Lambda(..) => return,
            ExprKind::Method(..) => {
                if let Some(Res::Method(fi, _)) = c.res.get(&e.id) {
                    if c.fns[*fi].self_kind == Some(SelfKind::Mut) {
                        *found = true;
                        return;
                    }
                }
            }
            ExprKind::Block(b) | ExprKind::If(_, b, _) => {
                for s in &b.stmts {
                    if matches!(s.kind, StmtKind::Assign { .. }) {
                        *found = true;
                        return;
                    }
                    visit_stmt(s, &mut |x| walk(c, x, found));
                }
            }
            _ => {}
        }
        visit_children(e, &mut |x| walk(c, x, found));
    }
    walk(c, e, &mut found);
    found
}

impl<'a> Emitter<'a> {
    // ---- function instances ----

    pub fn fn_inst(&mut self, fi: usize, targs: Vec<Ty>) -> String {
        let key = (fi, targs.clone());
        if let Some(n) = self.fn_names.get(&key) {
            return n.clone();
        }
        let base = sanitize(&self.c.fns[fi].name);
        let name = if targs.is_empty() && base == "main" {
            "tn_user_main".to_string()
        } else {
            self.fresh(&format!("f_{}_", base))
        };
        self.fn_names.insert(key, name.clone());
        self.fn_queue.push((fi, targs, name.clone()));
        name
    }

    fn sig(&mut self, fi: usize, targs: &[Ty]) -> (Vec<Ty>, Ty) {
        let f = &self.c.fns[fi];
        let m: HashMap<String, Ty> = f.tparams.iter().cloned().zip(targs.iter().cloned()).collect();
        (f.params.iter().map(|(_, t)| t.subst(&m)).collect(), f.ret.subst(&m))
    }

    pub fn emit_fn(&mut self, fi: usize, targs: &[Ty], name: &str) {
        let c = self.c;
        let info = &c.fns[fi];
        let decl = &c.prog.fns[fi];
        let tsub: HashMap<String, Ty> = info.tparams.iter().cloned().zip(targs.iter().cloned()).collect();
        let ret = info.ret.subst(&tsub);
        let rn = self.cty(&ret);
        let mut params = Vec::new();
        for (i, (n, t)) in info.params.iter().enumerate() {
            let ct = self.cty(&t.subst(&tsub));
            if i == 0 && info.self_kind == Some(SelfKind::Mut) {
                params.push(format!("{} *p_self", ct));
            } else {
                params.push(format!("{} v_{}", ct, n));
            }
        }
        let sig = format!("static {} {}({})", rn, name, if params.is_empty() { "void".into() } else { params.join(", ") });
        let _ = writeln!(self.protos, "{};", sig);
        self.st = FnState { tsub, ret: Some(ret.clone()), self_ptr: info.self_kind == Some(SelfKind::Mut), indent: 1, ..Default::default() };
        self.push(ScopeKind::Fn);
        let r = self.fresh("ret");
        let _ = writeln!(self.st.out, "    {} {};", rn, r);
        self.block_into(decl.body.as_ref().unwrap(), Some(&r), &ret);
        self.release_to(ScopeKind::Fn);
        self.line(&format!("return {};", r));
        self.st.scopes.clear();
        let body = std::mem::take(&mut self.st.out);
        let _ = write!(self.bodies, "{} {{\n{}}}\n", sig, body);
    }

    // ---- emission helpers ----

    fn line(&mut self, s: &str) {
        for _ in 0..self.st.indent {
            self.st.out.push_str("    ");
        }
        self.st.out.push_str(s);
        self.st.out.push('\n');
    }

    fn ety(&self, e: &Expr) -> Ty {
        self.c.ty(e.id).subst(&self.st.tsub)
    }

    fn sub(&self, t: &Ty) -> Ty {
        t.subst(&self.st.tsub)
    }

    pub fn trivial(&mut self, t: &Ty) -> bool {
        match t {
            Ty::Con(n, a) if a.is_empty() && matches!(n.as_str(), "Int" | "Float" | "Bool" | "Unit" | "Console" | "Clock") => true,
            Ty::Tuple(ts) => ts.clone().iter().all(|t| self.trivial(t)),
            Ty::Con(n, _) if n == "List" || n == "Map" || n == "Str" || n == "Fs" => false,
            Ty::Con(..) => {
                if let Some(fs) = self.c.struct_fields(t) {
                    fs.iter().all(|(_, t)| self.trivial(t))
                } else if let Some(vs) = self.c.enum_variants(t) {
                    !self.is_boxed(t) && vs.iter().all(|(_, fs)| fs.iter().all(|t| self.trivial(t)))
                } else {
                    false
                }
            }
            _ => false,
        }
    }

    fn push(&mut self, kind: ScopeKind) {
        self.st.scopes.push(Scope { kind, owned: vec![] });
    }

    fn release_list(&mut self, owned: &[(String, Ty)]) {
        for (n, t) in owned.iter().rev() {
            if !self.trivial(t) {
                let tn = self.cty(t);
                self.line(&format!("{}_release({});", tn, n));
            }
        }
    }

    fn pop(&mut self) {
        let s = self.st.scopes.pop().unwrap();
        self.release_list(&s.owned);
    }

    // Release (without popping) every scope down to and including the innermost `kind`.
    fn release_to(&mut self, kind: ScopeKind) {
        let mut all = Vec::new();
        for s in self.st.scopes.iter().rev() {
            all.push(s.owned.clone());
            if s.kind == kind {
                break;
            }
        }
        for o in all {
            self.release_list(&o);
        }
    }

    fn reg(&mut self, name: &str, t: &Ty) {
        self.st.scopes.last_mut().unwrap().owned.push((name.to_string(), t.clone()));
    }

    fn reg_local(&mut self, name: &str, t: &Ty) {
        let s = self.st.scopes.iter_mut().rev().find(|s| s.kind != ScopeKind::Stmt).unwrap();
        s.owned.push((name.to_string(), t.clone()));
    }

    fn unreg(&mut self, name: &str) {
        for s in self.st.scopes.iter_mut().rev() {
            if let Some(i) = s.owned.iter().position(|(n, _)| n == name) {
                s.owned.remove(i);
                return;
            }
        }
    }

    // Take ownership of a value: move an owned temp, or retain a borrowed one.
    fn own(&mut self, cv: CV, t: &Ty) -> String {
        if cv.owned {
            self.unreg(&cv.code);
            return cv.code;
        }
        if self.trivial(t) {
            return cv.code;
        }
        let tn = self.cty(t);
        format!("{}_retain({})", tn, cv.code)
    }

    fn tmp_owned(&mut self, t: &Ty, init: &str) -> CV {
        let tn = self.cty(t);
        let n = self.fresh("t");
        self.line(&format!("{} {} = {};", tn, n, init));
        self.reg(&n, t);
        CV { code: n, owned: true }
    }

    fn tmp_val(&mut self, t: &Ty, init: &str) -> CV {
        let tn = self.cty(t);
        let n = self.fresh("t");
        self.line(&format!("{} {} = {};", tn, n, init));
        bor(n)
    }

    // Evaluate left to right; a value that a later operand could invalidate is retained first.
    fn eval_list(&mut self, es: &[&Expr]) -> Vec<CV> {
        let c = self.c;
        let muts: Vec<bool> = es.iter().map(|e| may_mutate(c, e)).collect();
        let mut out = Vec::new();
        for (i, e) in es.iter().enumerate() {
            let cv = self.expr(e);
            if !cv.owned && muts[i + 1..].iter().any(|m| *m) {
                let t = self.ety(e);
                let code = self.own(cv, &t);
                out.push(self.tmp_owned(&t, &code));
            } else {
                out.push(cv);
            }
        }
        out
    }

    // ---- blocks and statements ----

    // Emit a block's statements; the trailing expression's value (if wanted) goes into `result`.
    fn block_into(&mut self, b: &Block, result: Option<&str>, rt: &Ty) {
        self.push(ScopeKind::Block);
        self.stmts_into(b, result, rt);
        self.pop();
    }

    fn stmts_into(&mut self, b: &Block, result: Option<&str>, rt: &Ty) {
        let n = b.stmts.len();
        for (i, s) in b.stmts.iter().enumerate() {
            match (&s.kind, result) {
                (StmtKind::Expr(e), Some(r)) if i + 1 == n => {
                    self.push(ScopeKind::Stmt);
                    let cv = self.expr(e);
                    let code = self.own(cv, rt);
                    self.line(&format!("{} = {};", r, code));
                    self.pop();
                }
                _ => self.stmt(s),
            }
        }
    }

    fn stmt(&mut self, s: &Stmt) {
        self.push(ScopeKind::Stmt);
        match &s.kind {
            StmtKind::Expr(e) => {
                self.expr(e);
            }
            StmtKind::Let { pat, value, mutable, .. } => {
                if *mutable {
                    pat_names(pat, &mut self.st.muts);
                }
                let t = self.c.ty(pat.id).subst(&self.st.tsub);
                let cv = self.expr(value);
                if let PatKind::Bind(n) = &pat.kind {
                    let code = self.own(cv, &t);
                    let tn = self.cty(&t);
                    self.line(&format!("{} v_{} = {};", tn, n, code));
                    self.reg_local(&format!("v_{}", n), &t);
                } else {
                    let v = if cv.owned { cv.code.clone() } else { self.tmp_val(&t, &cv.code).code };
                    self.bind(pat, &v, &t, false);
                }
            }
            StmtKind::Assign { target, op, value } => self.assign(target, *op, value, s),
            StmtKind::While { cond, body } => {
                self.line("for (;;) {");
                self.st.indent += 1;
                self.push(ScopeKind::Stmt);
                let cv = self.expr(cond);
                let c = self.fresh("c");
                self.line(&format!("bool {} = {};", c, cv.code));
                self.pop();
                self.line(&format!("if (!{}) break;", c));
                self.push(ScopeKind::LoopBody);
                self.stmts_into(body, None, &Ty::unit());
                self.pop();
                self.st.indent -= 1;
                self.line("}");
            }
            StmtKind::For { pat, iter, body } => self.for_loop(pat, iter, body),
            StmtKind::Return(v) => {
                let rt = self.st.ret.clone().unwrap();
                let code = match v {
                    Some(e) => {
                        let cv = self.expr(e);
                        self.own(cv, &rt)
                    }
                    None => "0".to_string(),
                };
                let tn = self.cty(&rt);
                let r = self.fresh("r");
                self.line(&format!("{} {} = {};", tn, r, code));
                self.release_to(ScopeKind::Fn);
                self.line(&format!("return {};", r));
            }
            StmtKind::Break => {
                self.release_to(ScopeKind::LoopBody);
                self.line("break;");
            }
            StmtKind::Continue => {
                self.release_to(ScopeKind::LoopBody);
                self.line("continue;");
            }
        }
        self.pop();
    }

    fn for_loop(&mut self, pat: &Pattern, iter: &ForIter, body: &Block) {
        let et = self.c.ty(pat.id).subst(&self.st.tsub);
        self.line("{");
        self.st.indent += 1;
        self.push(ScopeKind::Block);
        let i = self.fresh("i");
        match iter {
            ForIter::Range(a, b) => {
                let vs = self.eval_list(&[a, b]);
                let hi = self.fresh("hi");
                self.line(&format!("int64_t {} = {};", hi, vs[1].code));
                self.line(&format!("for (int64_t {i} = {}; {i} < {hi}; {i}++) {{", vs[0].code));
                self.st.indent += 1;
                self.push(ScopeKind::LoopBody);
                self.bind(pat, &i, &et, true);
            }
            ForIter::Each(e) if self.fusable(e).is_some() => {
                // `for x in s.words()` / `s.lines()`: scan the string instead of
                // building the temporary list (same elements, same order).
                let (recv, next) = self.fusable(e).unwrap();
                let cv = self.expr(recv);
                let code = self.own(cv, &Ty::str());
                let src = self.tmp_owned(&Ty::str(), &code).code;
                let pos = self.fresh("pos");
                let w = self.fresh("w");
                self.line(&format!("int64_t {} = 0;", pos));
                self.line(&format!("for (tn_Str {w}; {next}({src}, &{pos}, &{w});) {{"));
                self.st.indent += 1;
                self.push(ScopeKind::LoopBody);
                self.bind(pat, &w, &et, true);
            }
            ForIter::Each(e) => {
                let st = self.ety(e);
                let cv = self.expr(e);
                let code = self.own(cv, &st);
                let snap = self.tmp_owned(&st, &code).code;
                let ln = self.cty(&st);
                if st.is("List") {
                    self.line(&format!("for (int64_t {i} = 0; {i} < {ln}_len({snap}); {i}++) {{"));
                    self.st.indent += 1;
                    self.push(ScopeKind::LoopBody);
                    self.bind(pat, &format!("{}->data[{}]", snap, i), &et, true);
                } else {
                    self.line(&format!("for (int64_t {i} = 0; {snap} && {i} < {snap}->n; {i}++) {{"));
                    self.st.indent += 1;
                    self.line(&format!("if (!{snap}->e[{i}].live) continue;"));
                    self.push(ScopeKind::LoopBody);
                    let tn = self.cty(&et);
                    let tup = self.fresh("kv");
                    self.line(&format!("{tn} {tup} = {{ {snap}->e[{i}].k, {snap}->e[{i}].v }};"));
                    self.bind(pat, &tup, &et, true);
                }
            }
        }
        self.stmts_into(body, None, &Ty::unit());
        self.pop();
        self.st.indent -= 1;
        self.line("}");
        self.pop();
        self.st.indent -= 1;
        self.line("}");
    }

    fn fusable<'e>(&self, e: &'e Expr) -> Option<(&'e Expr, &'static str)> {
        let ExprKind::Method(recv, _, args) = &e.kind else { return None };
        let Some(Res::Method(fi, _)) = self.c.res.get(&e.id) else { return None };
        if !args.is_empty() {
            return None;
        }
        match self.c.fns[*fi].name.as_str() {
            "Str.words" => Some((recv, "tn_next_word")),
            "Str.lines" => Some((recv, "tn_next_line")),
            _ => None,
        }
    }

    // ---- places ----

    fn place(&mut self, e: &Expr) -> Place {
        match &e.kind {
            ExprKind::Name(n) => {
                let root = if n == "self" && self.st.self_ptr { "p_self".to_string() } else { format!("&v_{}", n) };
                Place { root, steps: vec![] }
            }
            ExprKind::Field(b, f) => {
                let mut p = self.place(b);
                p.steps.push(Step::Field(format!("f_{}", f)));
                p
            }
            ExprKind::TupleField(b, i) => {
                let mut p = self.place(b);
                p.steps.push(Step::Field(format!("f{}", i)));
                p
            }
            ExprKind::Index(b, i) => {
                let bt = self.ety(b);
                let mut p = self.place(b);
                let it = self.ety(i);
                let cv = self.expr(i);
                let code = self.own(cv, &it);
                let k = self.tmp_owned(&it, &code).code;
                p.steps.push(if bt.is("List") { Step::List(bt, k) } else { Step::Map(bt, k) });
                p
            }
            _ => unreachable!("checker guarantees places"),
        }
    }

    // Pointer to the place after the first `n` steps.
    fn place_ptr(&mut self, p: &Place, n: usize, sp: crate::diag::Span) -> String {
        let mut cur = p.root.clone();
        for st in &p.steps[..n] {
            cur = match st {
                Step::Field(f) => format!("(&({})->{})", cur, f),
                Step::List(t, k) => {
                    let ln = self.cty(t);
                    let et = self.cty(&t.args()[0]);
                    let q = self.fresh("p");
                    let loc = self.loc(sp);
                    self.line(&format!("{} *{} = {}_at_mut({}, {}, {});", et, q, ln, cur, k, loc));
                    q
                }
                Step::Map(t, k) => {
                    let mn = self.cty(t);
                    let vt = self.cty(&t.args()[1]);
                    let q = self.fresh("p");
                    let loc = self.loc(sp);
                    self.line(&format!("{} *{} = {}_at_mut({}, {}, {});", vt, q, mn, cur, k, loc));
                    q
                }
            };
        }
        cur
    }

    fn assign(&mut self, target: &Expr, op: Option<BinOp>, value: &Expr, s: &Stmt) {
        let t = self.ety(target);
        let p = self.place(target);
        let cv = self.expr(value);
        let code = self.own(cv, &t);
        let tn = self.cty(&t);
        let nv = self.fresh("nv");
        self.line(&format!("{} {} = {};", tn, nv, code));
        match op {
            None => {
                if let Some(Step::Map(mt, k)) = p.steps.last() {
                    let (mt, k) = (mt.clone(), k.clone());
                    let ptr = self.place_ptr(&p, p.steps.len() - 1, target.span);
                    let mn = self.cty(&mt);
                    self.unreg(&k);
                    self.line(&format!("{}_insert({}, {}, {});", mn, ptr, k, nv));
                    return;
                }
                let ptr = self.place_ptr(&p, p.steps.len(), target.span);
                if !self.trivial(&t) {
                    self.line(&format!("{}_release(*{});", tn, ptr));
                }
                self.line(&format!("*{} = {};", ptr, nv));
            }
            Some(op) => {
                self.reg(&nv, &t);
                let ptr = self.place_ptr(&p, p.steps.len(), target.span);
                let r = self.arith(op, &t, &format!("(*{})", ptr), &nv, s.span);
                let code = self.own(r, &t);
                if !self.trivial(&t) {
                    self.line(&format!("{}_release(*{});", tn, ptr));
                }
                self.line(&format!("*{} = {};", ptr, code));
            }
        }
    }

    // ---- patterns ----

    fn pat_test(&mut self, p: &Pattern, v: &str, t: &Ty) -> String {
        match &p.kind {
            PatKind::Wild | PatKind::Bind(_) => "1".into(),
            PatKind::Int(i) => format!("({} == {})", v, int_lit(*i)),
            PatKind::Bool(b) => if *b { format!("({})", v) } else { format!("(!{})", v) },
            PatKind::Str(s) => format!("tn_Str_eq({}, tn_str_lit({}, {}))", v, c_string(s), s.len()),
            PatKind::Tuple(ps) => {
                let Ty::Tuple(ts) = t else { unreachable!() };
                let parts: Vec<String> =
                    ps.iter().zip(ts.clone()).enumerate().map(|(i, (p, t))| self.pat_test(p, &format!("({}).f{}", v, i), &t)).collect();
                parts.join(" && ")
            }
            PatKind::Variant(_, _, ps) => {
                let Some(Res::Variant(_, vi, _)) = self.c.res.get(&p.id) else { unreachable!() };
                let vi = *vi;
                let fts = self.c.enum_variants(t).unwrap()[vi].1.clone();
                let mut parts = vec![format!("{} == {}", self.tag(t, v), vi)];
                for (j, (sp, ft)) in ps.iter().zip(fts).enumerate() {
                    let pv = self.payload(t, v, vi, j);
                    let s = self.pat_test(sp, &pv, &ft);
                    if s != "1" {
                        parts.push(s);
                    }
                }
                format!("({})", parts.join(" && "))
            }
            PatKind::Or(_) => unreachable!("or-patterns are expanded"),
        }
    }

    // Bind pattern variables (retained) from value `v`, which is known to match.
    // `borrow`: the matched value outlives these bindings and cannot change
    // meanwhile, so they need no reference of their own.
    fn bind(&mut self, p: &Pattern, v: &str, t: &Ty, borrow: bool) {
        match &p.kind {
            PatKind::Bind(n) => {
                let tn = self.cty(t);
                if borrow || self.trivial(t) {
                    self.line(&format!("{} v_{} = {};", tn, n, v));
                    return;
                }
                self.line(&format!("{} v_{} = {}_retain({});", tn, n, tn, v));
                self.reg_local(&format!("v_{}", n), t);
            }
            PatKind::Tuple(ps) => {
                let Ty::Tuple(ts) = t else { unreachable!() };
                for (i, (p, t)) in ps.iter().zip(ts.clone()).enumerate() {
                    self.bind(p, &format!("({}).f{}", v, i), &t, borrow);
                }
            }
            PatKind::Variant(_, _, ps) => {
                let Some(Res::Variant(_, vi, _)) = self.c.res.get(&p.id) else { unreachable!() };
                let vi = *vi;
                let fts = self.c.enum_variants(t).unwrap()[vi].1.clone();
                for (j, (sp, ft)) in ps.iter().zip(fts).enumerate() {
                    let pv = self.payload(t, v, vi, j);
                    self.bind(sp, &pv, &ft, borrow);
                }
            }
            _ => {}
        }
    }

    // ---- expressions ----

    pub fn expr(&mut self, e: &Expr) -> CV {
        let t = self.ety(e);
        match &e.kind {
            ExprKind::Int(i) => bor(int_lit(*i)),
            ExprKind::Float(f) => bor(format!("{:e}", f)),
            ExprKind::Bool(b) => bor(if *b { "true" } else { "false" }),
            ExprKind::Unit => bor("0"),
            ExprKind::Str(segs) => self.interp_str(segs),
            ExprKind::Name(_) | ExprKind::Path(..) => self.name_value(e, &t),
            ExprKind::Call(callee, args) => self.call(e, callee, args, &t),
            ExprKind::Method(recv, _, args) => self.method(e, recv, args, &t),
            ExprKind::Field(b, f) => {
                let cv = self.expr(b);
                bor(format!("({}).f_{}", cv.code, f))
            }
            ExprKind::TupleField(b, i) => {
                let cv = self.expr(b);
                bor(format!("({}).f{}", cv.code, i))
            }
            ExprKind::Index(b, i) => {
                let bt = self.ety(b);
                let vs = self.eval_list(&[b, i]);
                let bn = self.cty(&bt);
                let loc = self.loc(e.span);
                self.tmp_val(&t, &format!("*{}_at({}, {}, {})", bn, vs[0].code, vs[1].code, loc))
            }
            ExprKind::Unary(op, x) => {
                let cv = self.expr(x);
                let code = match op {
                    UnOp::Not => format!("!({})", cv.code),
                    UnOp::Neg if t.is("Int") => format!("tn_neg({}, {})", cv.code, self.loc(e.span)),
                    UnOp::Neg => format!("(-({}))", cv.code),
                };
                self.tmp_val(&t, &code)
            }
            ExprKind::Binary(op, l, r) => self.binary(e, *op, l, r),
            ExprKind::If(c, then, els) => {
                let res = self.result_var(&t);
                let cv = self.expr(c);
                self.line(&format!("if ({}) {{", cv.code));
                self.st.indent += 1;
                self.block_into(then, res.as_deref(), &t);
                self.st.indent -= 1;
                if let Some(x) = els {
                    self.line("} else {");
                    self.st.indent += 1;
                    self.push(ScopeKind::Block);
                    let v = self.expr(x);
                    if let Some(r) = &res {
                        let code = self.own(v, &t);
                        self.line(&format!("{} = {};", r, code));
                    }
                    self.pop();
                    self.st.indent -= 1;
                }
                self.line("}");
                self.finish_result(res, &t)
            }
            ExprKind::Block(b) => {
                let res = self.result_var(&t);
                self.line("{");
                self.st.indent += 1;
                self.block_into(b, res.as_deref(), &t);
                self.st.indent -= 1;
                self.line("}");
                self.finish_result(res, &t)
            }
            ExprKind::Match(s, arms) => self.match_expr(e, s, arms, &t),
            ExprKind::List(xs) => {
                let refs: Vec<&Expr> = xs.iter().collect();
                let vs = self.eval_list(&refs);
                if vs.is_empty() {
                    let ln = self.cty(&t);
                    return bor(format!("(({}) NULL)", ln));
                }
                let et = t.args()[0].clone();
                let ln = self.cty(&t);
                let l = self.tmp_owned(&t, &format!("{}_alloc({})", ln, vs.len()));
                for (i, v) in vs.into_iter().enumerate() {
                    let code = self.own(v, &et);
                    self.line(&format!("{}->data[{}] = {};", l.code, i, code));
                }
                self.line(&format!("{}->len = {};", l.code, xs.len()));
                l
            }
            ExprKind::MapLit(ps) => {
                let refs: Vec<&Expr> = ps.iter().flat_map(|(k, v)| [k, v]).collect();
                let vs = self.eval_list(&refs);
                if vs.is_empty() {
                    let mn = self.cty(&t);
                    return bor(format!("(({}) NULL)", mn));
                }
                let (kt, vt) = (t.args()[0].clone(), t.args()[1].clone());
                let mn = self.cty(&t);
                let m = self.tmp_owned(&t, "NULL");
                let mut it = vs.into_iter();
                while let (Some(k), Some(v)) = (it.next(), it.next()) {
                    let kc = self.own(k, &kt);
                    let vc = self.own(v, &vt);
                    self.line(&format!("{}_insert(&{}, {}, {});", mn, m.code, kc, vc));
                }
                m
            }
            ExprKind::Tuple(xs) => {
                let Ty::Tuple(ts) = &t else { unreachable!() };
                let ts = ts.clone();
                let refs: Vec<&Expr> = xs.iter().collect();
                let vs = self.eval_list(&refs);
                let codes: Vec<String> = vs.into_iter().zip(&ts).map(|(v, t)| self.own(v, t)).collect();
                let tn = self.cty(&t);
                self.tmp_owned(&t, &format!("({}){{ {} }}", tn, codes.join(", ")))
            }
            ExprKind::StructLit(_, fields, base) => {
                let decl = self.c.struct_fields(&t).unwrap();
                let mut refs: Vec<&Expr> = fields.iter().map(|(_, v)| v).collect();
                if let Some(b) = base {
                    refs.push(b);
                }
                let mut vs = self.eval_list(&refs);
                let base_cv = if base.is_some() { vs.pop() } else { None };
                let mut inits = Vec::new();
                for ((f, _), v) in fields.iter().zip(vs) {
                    let ft = decl.iter().find(|(n, _)| n == f).unwrap().1.clone();
                    let code = self.own(v, &ft);
                    inits.push(format!(".f_{} = {}", f, code));
                }
                if let Some(b) = base_cv {
                    for (f, ft) in &decl {
                        if !fields.iter().any(|(g, _)| g == f) {
                            let code = self.own(bor(format!("({}).f_{}", b.code, f)), ft);
                            inits.push(format!(".f_{} = {}", f, code));
                        }
                    }
                }
                let tn = self.cty(&t);
                self.tmp_owned(&t, &format!("({}){{ {} }}", tn, inits.join(", ")))
            }
            ExprKind::Try(x) => self.try_expr(e, x, &t),
            ExprKind::Lambda(params, _, body) => self.lambda(e, params, body, &t),
        }
    }

    fn result_var(&mut self, t: &Ty) -> Option<String> {
        if t.is("Unit") {
            return None;
        }
        let tn = self.cty(t);
        let r = self.fresh("r");
        self.line(&format!("{} {} = {{0}};", tn, r));
        Some(r)
    }

    fn finish_result(&mut self, res: Option<String>, t: &Ty) -> CV {
        match res {
            Some(r) => {
                self.reg(&r, t);
                CV { code: r, owned: true }
            }
            None => bor("0"),
        }
    }

    fn interp_str(&mut self, segs: &[StrSeg]) -> CV {
        if let [StrSeg::Lit(s)] = segs {
            return bor(format!("tn_str_lit({}, {})", c_string(s), s.len()));
        }
        let refs: Vec<&Expr> = segs.iter().filter_map(|s| if let StrSeg::Expr(x) = s { Some(x) } else { None }).collect();
        let tys: Vec<Ty> = refs.iter().map(|x| self.ety(x)).collect();
        let vs = self.eval_list(&refs);
        let b = self.fresh("b");
        self.line(&format!("tn_buf {} = tn_buf_new();", b));
        let mut it = vs.into_iter().zip(tys);
        for s in segs {
            match s {
                StrSeg::Lit(l) => self.line(&format!("tn_buf_add(&{}, {}, {});", b, c_string(l), l.len())),
                StrSeg::Expr(_) => {
                    let (v, t) = it.next().unwrap();
                    let tn = self.cty(&t);
                    self.line(&format!("{}_show(&{}, {}, true);", tn, b, v.code));
                }
            }
        }
        self.tmp_owned(&Ty::str(), &format!("tn_buf_finish(&{})", b))
    }

    fn local_code(&self, n: &str) -> String {
        if n == "self" && self.st.self_ptr { "(*p_self)".into() } else { format!("v_{}", n) }
    }

    fn name_value(&mut self, e: &Expr, t: &Ty) -> CV {
        match self.c.res[&e.id].clone() {
            Res::Local(n) => bor(self.local_code(&n)),
            Res::Fn(fi, targs) => {
                let targs: Vec<Ty> = targs.iter().map(|x| self.sub(x)).collect();
                let w = self.fn_wrapper(fi, targs);
                bor(format!("((tn_fn){{ (void *){}, NULL }})", w))
            }
            Res::Variant(_, vi, _) => {
                if let Ty::Fn(ps, r) = t {
                    let w = self.ctor_wrapper(&r, vi, ps);
                    return bor(format!("((tn_fn){{ (void *){}, NULL }})", w));
                }
                let code = self.ctor(t, vi, &[]);
                self.tmp_owned(t, &code)
            }
            _ => unreachable!(),
        }
    }

    fn call(&mut self, e: &Expr, callee: &Expr, args: &[Expr], t: &Ty) -> CV {
        let loc = self.loc(e.span);
        if let Some(Res::CallValue) = self.c.res.get(&e.id) {
            let mut refs: Vec<&Expr> = vec![callee];
            refs.extend(args.iter());
            let ptys: Vec<Ty> = args.iter().map(|a| self.ety(a)).collect();
            let vs = self.eval_list(&refs);
            let f = vs[0].code.clone();
            let rn = self.cty(t);
            let mut sig = vec!["tn_env *".to_string()];
            for p in &ptys {
                sig.push(self.cty(p));
            }
            let mut call_args = vec![format!("({}).env", f)];
            call_args.extend(vs[1..].iter().map(|v| v.code.clone()));
            let code = format!("(({} (*)({})) ({}).f)({})", rn, sig.join(", "), f, call_args.join(", "));
            return self.tmp_owned(t, &code);
        }
        let refs: Vec<&Expr> = args.iter().collect();
        match self.c.res.get(&callee.id).cloned() {
            Some(Res::Fn(fi, targs)) => {
                let targs: Vec<Ty> = targs.iter().map(|x| self.sub(x)).collect();
                let vs = self.eval_list(&refs);
                if self.c.fns[fi].is_extern {
                    let (ptys, _) = self.sig(fi, &targs);
                    return self.extern_call(&self.c.fns[fi].name.clone(), vs, &ptys, t, e.span);
                }
                let name = self.fn_inst(fi, targs);
                let codes: Vec<String> = vs.iter().map(|v| v.code.clone()).collect();
                let _ = loc;
                self.tmp_owned(t, &format!("{}({})", name, codes.join(", ")))
            }
            Some(Res::Variant(_, vi, _)) => {
                let vs = self.eval_list(&refs);
                let fts = self.c.enum_variants(t).unwrap()[vi].1.clone();
                let codes: Vec<String> = vs.into_iter().zip(&fts).map(|(v, ft)| self.own(v, ft)).collect();
                let code = self.ctor(t, vi, &codes);
                self.tmp_owned(t, &code)
            }
            _ => unreachable!("call without resolution"),
        }
    }

    fn method(&mut self, e: &Expr, recv: &Expr, args: &[Expr], t: &Ty) -> CV {
        match self.c.res[&e.id].clone() {
            Res::ToStr => {
                let rt = self.ety(recv);
                let cv = self.expr(recv);
                let tn = self.cty(&rt);
                let b = self.fresh("b");
                self.line(&format!("tn_buf {} = tn_buf_new();", b));
                self.line(&format!("{}_show(&{}, {}, true);", tn, b, cv.code));
                self.tmp_owned(&Ty::str(), &format!("tn_buf_finish(&{})", b))
            }
            Res::Method(fi, targs) => {
                let targs: Vec<Ty> = targs.iter().map(|x| self.sub(x)).collect();
                let (ptys, _) = self.sig(fi, &targs);
                let info = &self.c.fns[fi];
                let name = info.name.clone();
                let is_extern = info.is_extern;
                if info.self_kind == Some(SelfKind::Mut) {
                    let p = self.place(recv);
                    let refs: Vec<&Expr> = args.iter().collect();
                    let vs = self.eval_list(&refs);
                    // Arguments are owned so they cannot alias the receiver being mutated.
                    let mut owned = Vec::new();
                    for (v, pt) in vs.into_iter().zip(&ptys[1..]) {
                        let code = self.own(v, pt);
                        owned.push(self.tmp_owned(pt, &code));
                    }
                    let ptr = self.place_ptr(&p, p.steps.len(), recv.span);
                    if is_extern {
                        return self.extern_mut(&name, &ptr, &ptys, owned, t, e.span);
                    }
                    let f = self.fn_inst(fi, targs);
                    let mut codes = vec![ptr];
                    codes.extend(owned.iter().map(|v| v.code.clone()));
                    return self.tmp_owned(t, &format!("{}({})", f, codes.join(", ")));
                }
                let mut refs: Vec<&Expr> = vec![recv];
                refs.extend(args.iter());
                let vs = self.eval_list(&refs);
                if is_extern {
                    return self.extern_call(&name, vs, &ptys, t, e.span);
                }
                let f = self.fn_inst(fi, targs);
                let codes: Vec<String> = vs.iter().map(|v| v.code.clone()).collect();
                self.tmp_owned(t, &format!("{}({})", f, codes.join(", ")))
            }
            _ => unreachable!(),
        }
    }

    fn binary(&mut self, e: &Expr, op: BinOp, l: &Expr, r: &Expr) -> CV {
        if op == BinOp::And || op == BinOp::Or {
            let lv = self.expr(l);
            let res = self.fresh("b");
            self.line(&format!("bool {} = {};", res, lv.code));
            self.line(&format!("if ({}{}) {{", if op == BinOp::And { "" } else { "!" }, res));
            self.st.indent += 1;
            self.push(ScopeKind::Block);
            let rv = self.expr(r);
            self.line(&format!("{} = {};", res, rv.code));
            self.pop();
            self.st.indent -= 1;
            self.line("}");
            return bor(res);
        }
        let lt = self.ety(l);
        let vs = self.eval_list(&[l, r]);
        let (a, b) = (vs[0].code.clone(), vs[1].code.clone());
        let tn = self.cty(&lt);
        let scalar = lt.is("Int") || lt.is("Float") || lt.is("Bool") || lt.is("Unit");
        let has_map = lt.any(&|t| t.is("Map"));
        let code = match op {
            BinOp::Eq | BinOp::Ne => {
                let neg = if op == BinOp::Ne { "!" } else { "" };
                if scalar { format!("{}({} == {})", neg, a, b) } else { format!("{}{}_eq({}, {})", neg, tn, a, b) }
            }
            BinOp::Lt | BinOp::Le | BinOp::Gt | BinOp::Ge => {
                let o = match op {
                    BinOp::Lt => "<",
                    BinOp::Le => "<=",
                    BinOp::Gt => ">",
                    _ => ">=",
                };
                if lt.is("Int") || lt.is("Float") {
                    format!("({} {} {})", a, o, b)
                } else {
                    if has_map {
                        let loc = self.loc(e.span);
                        self.line(&format!("tn_cur_loc = {};", loc));
                    }
                    format!("({}_cmp({}, {}) {} 0)", tn, a, b, o)
                }
            }
            _ => return self.arith(op, &lt, &a, &b, e.span),
        };
        self.tmp_val(&Ty::bool(), &code)
    }

    fn arith(&mut self, op: BinOp, t: &Ty, a: &str, b: &str, sp: crate::diag::Span) -> CV {
        let loc = self.loc(sp);
        if t.is("Int") {
            let f = match op {
                BinOp::Add => "tn_add",
                BinOp::Sub => "tn_sub",
                BinOp::Mul => "tn_mul",
                BinOp::Div => "tn_div",
                _ => "tn_rem",
            };
            return self.tmp_val(t, &format!("{}({}, {}, {})", f, a, b, loc));
        }
        if t.is("Float") {
            let code = match op {
                BinOp::Add => format!("({} + {})", a, b),
                BinOp::Sub => format!("({} - {})", a, b),
                BinOp::Mul => format!("({} * {})", a, b),
                BinOp::Div => format!("({} / {})", a, b),
                _ => format!("fmod({}, {})", a, b),
            };
            return self.tmp_val(t, &code);
        }
        if t.is("Str") {
            return self.tmp_owned(t, &format!("tn_str_concat({}, {})", a, b));
        }
        let ln = self.cty(t);
        self.tmp_owned(t, &format!("{}_concat({}, {})", ln, a, b))
    }

    fn match_expr(&mut self, e: &Expr, s: &Expr, arms: &[Arm], t: &Ty) -> CV {
        let st = self.ety(s);
        let res = self.result_var(t);
        let cv = self.expr(s);
        let stable = cv.owned || (is_ident(&cv.code) && cv.code.starts_with("v_") && !self.st.muts.contains(&cv.code));
        let sv = if cv.owned || is_ident(&cv.code) { cv.code } else { self.tmp_val(&st, &cv.code).code };
        let done = self.fresh("done");
        for a in arms {
            for alt in expand_or(&a.pat) {
                let test = self.pat_test(&alt, &sv, &st);
                self.line(&format!("if ({}) {{", test));
                self.st.indent += 1;
                self.push(ScopeKind::Block);
                self.bind(&alt, &sv, &st, stable);
                if let Some(g) = &a.guard {
                    let gv = self.expr(g);
                    self.line(&format!("if ({}) {{", gv.code));
                    self.st.indent += 1;
                }
                self.push(ScopeKind::Stmt);
                let v = self.expr(&a.body);
                if let Some(r) = &res {
                    let code = self.own(v, t);
                    self.line(&format!("{} = {};", r, code));
                }
                self.pop();
                self.release_to(ScopeKind::Block);
                self.line(&format!("goto {};", done));
                if a.guard.is_some() {
                    self.st.indent -= 1;
                    self.line("}");
                }
                self.pop();
                self.st.indent -= 1;
                self.line("}");
            }
        }
        let loc = self.loc(e.span);
        self.line(&format!("tn_trap(\"no match arm (internal error)\", {});", loc));
        self.line(&format!("{}:;", done));
        self.finish_result(res, t)
    }

    fn try_expr(&mut self, e: &Expr, x: &Expr, t: &Ty) -> CV {
        let xt = self.ety(x);
        let cv = self.expr(x);
        let v = if cv.owned || cv.code.starts_with("v_") { cv.code } else { self.tmp_val(&xt, &cv.code).code };
        let rt = self.st.ret.clone().unwrap();
        let tag = self.tag(&xt, &v);
        self.line(&format!("if ({} != 0) {{", tag));
        self.st.indent += 1;
        let ret = if xt.is("Option") {
            self.ctor_named(&rt, "None", &[])
        } else {
            let et = xt.args()[1].clone();
            let p = self.payload(&xt, &v, 1, 0);
            let code = self.own(bor(p), &et);
            self.ctor_named(&rt, "Err", &[code])
        };
        let rn = self.cty(&rt);
        let r = self.fresh("r");
        self.line(&format!("{} {} = {};", rn, r, ret));
        self.release_to(ScopeKind::Fn);
        self.line(&format!("return {};", r));
        self.st.indent -= 1;
        self.line("}");
        let _ = e;
        let p = self.payload(&xt, &v, 0, 0);
        let _ = t;
        bor(p)
    }

    // ---- closures and function values ----

    fn lambda(&mut self, e: &Expr, params: &[(String, Option<TypeExpr>)], body: &Expr, t: &Ty) -> CV {
        let Ty::Fn(pts, rt) = t else { unreachable!() };
        let caps: Vec<(String, Ty)> = self.c.captures[&e.id].iter().map(|(n, ct)| (n.clone(), self.sub(ct))).collect();
        let name = self.fresh("lam");
        let rn = self.cty(rt);
        // environment
        let mut env = format!("struct {}_env {{ tn_env h;", name);
        let mut drop = format!("static void {}_drop(tn_env *e) {{ struct {}_env *E = (void *)e; ", name, name);
        for (n, ct) in &caps {
            let tn = self.cty(ct);
            let _ = write!(env, " {} c_{};", tn, n);
            let _ = write!(drop, "{}_release(E->c_{}); ", tn, n);
        }
        env.push_str(" };\n");
        drop.push_str("free(E); }\n");
        self.helpers.push_str(&env);
        self.helpers.push_str(&drop);
        let mut ps = vec!["tn_env *env_".to_string()];
        for ((pn, _), pt) in params.iter().zip(pts) {
            let tn = self.cty(pt);
            ps.push(format!("{} v_{}", tn, pn));
        }
        let sig = format!("static {} {}({})", rn, name, ps.join(", "));
        let _ = writeln!(self.protos, "{};", sig);
        // body, in a fresh function context
        let tsub = self.st.tsub.clone();
        let saved = std::mem::replace(
            &mut self.st,
            FnState { tsub, ret: Some((**rt).clone()), self_ptr: false, indent: 1, ..Default::default() },
        );
        self.push(ScopeKind::Fn);
        self.line(&format!("struct {}_env *E = (void *)env_; (void)E;", name));
        for (n, ct) in &caps {
            let tn = self.cty(ct);
            self.line(&format!("{} v_{} = E->c_{};", tn, n, n));
        }
        let r = self.fresh("ret");
        self.line(&format!("{} {};", rn, r));
        self.push(ScopeKind::Stmt);
        let v = self.expr(body);
        let code = self.own(v, rt);
        self.line(&format!("{} = {};", r, code));
        self.pop();
        self.release_to(ScopeKind::Fn);
        self.line(&format!("return {};", r));
        let out = std::mem::replace(&mut self.st, saved).out;
        let _ = write!(self.bodies, "{} {{\n{}}}\n", sig, out);
        // creation
        if caps.is_empty() {
            return bor(format!("((tn_fn){{ (void *){}, NULL }})", name));
        }
        let env_v = self.fresh("env");
        self.line(&format!("struct {n}_env *{env_v} = tn_alloc(sizeof *{env_v}); {env_v}->h.rc = 1; {env_v}->h.drop = {n}_drop;", n = name));
        for (n, ct) in &caps {
            let code = self.own(bor(self.local_code(n)), ct);
            self.line(&format!("{}->c_{} = {};", env_v, n, code));
        }
        self.tmp_owned(t, &format!("((tn_fn){{ (void *){}, &{}->h }})", name, env_v))
    }

    fn fn_wrapper(&mut self, fi: usize, targs: Vec<Ty>) -> String {
        let key = format!("fn{}:{:?}", fi, targs);
        if let Some(w) = self.wrappers.get(&key) {
            return w.clone();
        }
        let (ptys, rt) = self.sig(fi, &targs);
        let w = self.fresh("fnv");
        self.wrappers.insert(key, w.clone());
        let rn = self.cty(&rt);
        let mut ps = vec!["tn_env *e".to_string()];
        for (i, p) in ptys.iter().enumerate() {
            let tn = self.cty(p);
            ps.push(format!("{} a{}", tn, i));
        }
        let sig = format!("static {} {}({})", rn, w, ps.join(", "));
        let _ = writeln!(self.protos, "{};", sig);
        let args: Vec<CV> = (0..ptys.len()).map(|i| bor(format!("a{}", i))).collect();
        if self.c.fns[fi].is_extern {
            let saved = std::mem::replace(&mut self.st, FnState { ret: Some(rt.clone()), indent: 1, ..Default::default() });
            self.push(ScopeKind::Fn);
            let name = self.c.fns[fi].name.clone();
            let v = self.extern_call(&name, args, &ptys, &rt, crate::diag::Span::default());
            let code = self.own(v, &rt);
            let r = self.fresh("r");
            self.line(&format!("{} {} = {};", rn, r, code));
            self.release_to(ScopeKind::Fn);
            self.line(&format!("return {};", r));
            let out = std::mem::replace(&mut self.st, saved).out;
            let _ = write!(self.bodies, "{} {{ (void)e;\n{}}}\n", sig, out);
        } else {
            let f = self.fn_inst(fi, targs);
            let a: Vec<String> = (0..ptys.len()).map(|i| format!("a{}", i)).collect();
            let _ = writeln!(self.bodies, "{} {{ (void)e; return {}({}); }}", sig, f, a.join(", "));
        }
        w
    }

    fn ctor_wrapper(&mut self, et: &Ty, vi: usize, ptys: &[Ty]) -> String {
        let key = format!("ctor{:?}:{}", et, vi);
        if let Some(w) = self.wrappers.get(&key) {
            return w.clone();
        }
        let w = self.fresh("fnv");
        self.wrappers.insert(key, w.clone());
        let en = self.cty(et);
        let mut ps = vec!["tn_env *e".to_string()];
        let mut args = Vec::new();
        for (i, p) in ptys.iter().enumerate() {
            let tn = self.cty(p);
            ps.push(format!("{} a{}", tn, i));
            args.push(format!("{}_retain(a{})", tn, i));
        }
        let sig = format!("static {} {}({})", en, w, ps.join(", "));
        let _ = writeln!(self.protos, "{};", sig);
        let code = self.ctor(et, vi, &args);
        let _ = writeln!(self.bodies, "{} {{ (void)e; return {}; }}", sig, code);
        w
    }

    // ---- builtins (signatures live in prelude.tn) ----

    fn some_none(&mut self, t: &Ty, cond: &str, val: &str) -> CV {
        let s = self.ctor_named(t, "Some", &[val.to_string()]);
        let n = self.ctor_named(t, "None", &[]);
        self.tmp_owned(t, &format!("{} ? {} : {}", cond, s, n))
    }

    fn io_result(&mut self, t: &Ty, k: &str, ok: &str, msg: &str) -> CV {
        let et = t.args()[1].clone();
        let errs: Vec<String> = (0..3).map(|i| self.ctor(&et, i, &[msg.to_string()])).collect();
        let err = format!("({k} == 1 ? {} : {k} == 2 ? {} : {})", errs[0], errs[1], errs[2]);
        let okv = self.ctor_named(t, "Ok", &[ok.to_string()]);
        let errv = self.ctor_named(t, "Err", &[err]);
        self.tmp_owned(t, &format!("{} == 0 ? {} : {}", k, okv, errv))
    }

    fn extern_call(&mut self, name: &str, args: Vec<CV>, ptys: &[Ty], t: &Ty, sp: crate::diag::Span) -> CV {
        let a: Vec<String> = args.iter().map(|v| v.code.clone()).collect();
        let loc = self.loc(sp);
        let tn = self.cty(t);
        match name {
            "panic" => {
                self.line(&format!("tn_trap_str({}, {});", a[0], loc));
                let r = self.fresh("t");
                self.line(&format!("{} {} = {{0}};", tn, r));
                bor(r)
            }
            "assert" => {
                self.line(&format!("if (!({})) tn_trap(\"assertion failed\", {});", a[0], loc));
                bor("0")
            }
            "Int.to_float" => self.tmp_val(t, &format!("(double)({})", a[0])),
            "Int.char" => self.tmp_owned(t, &format!("tn_int_char({}, {})", a[0], loc)),
            "Float.to_int" => self.tmp_val(t, &format!("tn_float_to_int({}, {})", a[0], loc)),
            "Float.sqrt" | "Float.floor" | "Float.ceil" | "Float.round" => {
                self.tmp_val(t, &format!("{}({})", &name[6..], a[0]))
            }
            "Str.len" => self.tmp_val(t, &format!("({}).len", a[0])),
            "Str.byte" => self.tmp_val(t, &format!("tn_str_byte({}, {}, {})", a[0], a[1], loc)),
            "Str.slice" => self.tmp_owned(t, &format!("tn_str_slice({}, {}, {}, {})", a[0], a[1], a[2], loc)),
            "Str.find" => {
                let i = self.tmp_val(&Ty::int(), &format!("tn_str_find({}, {}, 0)", a[0], a[1])).code;
                self.some_none(t, &format!("{} >= 0", i), &i)
            }
            "Str.split" => self.tmp_owned(t, &format!("tn_str_split({}, {}, {})", a[0], a[1], loc)),
            "Str.words" => self.tmp_owned(t, &format!("tn_str_words({})", a[0])),
            "Str.lines" => self.tmp_owned(t, &format!("tn_str_lines({})", a[0])),
            "Str.trim" => self.tmp_owned(t, &format!("tn_str_trim({}, true, true)", a[0])),
            "Str.trim_start" => self.tmp_owned(t, &format!("tn_str_trim({}, true, false)", a[0])),
            "Str.trim_end" => self.tmp_owned(t, &format!("tn_str_trim({}, false, true)", a[0])),
            "Str.starts_with" => self.tmp_val(t, &format!("tn_str_starts({}, {})", a[0], a[1])),
            "Str.ends_with" => self.tmp_val(t, &format!("tn_str_ends({}, {})", a[0], a[1])),
            "Str.to_int" | "Str.to_float" => {
                let (ty, f) = if name == "Str.to_int" { ("tn_Int", "tn_str_to_int") } else { ("tn_Float", "tn_str_to_float") };
                let o = self.fresh("o");
                self.line(&format!("{} {} = 0;", ty, o));
                let ok = self.tmp_val(&Ty::bool(), &format!("{}({}, &{})", f, a[0], o)).code;
                self.some_none(t, &ok, &o)
            }
            "Str.upper" | "Str.lower" if args[0].owned => {
                // The receiver is a temporary: hand it over so it can be reused in place.
                self.unreg(&a[0]);
                self.tmp_owned(t, &format!("tn_str_case_move({}, {})", a[0], name == "Str.upper"))
            }
            "Str.upper" | "Str.lower" => {
                self.tmp_owned(t, &format!("tn_str_case({}, {})", a[0], name == "Str.upper"))
            }
            "Str.replace" => self.tmp_owned(t, &format!("tn_str_replace({}, {}, {}, {})", a[0], a[1], a[2], loc)),
            "Str.chars" => self.tmp_owned(t, &format!("tn_str_chars({})", a[0])),
            "List.len" => {
                let ln = self.cty(&ptys[0]);
                self.tmp_val(t, &format!("{}_len({})", ln, a[0]))
            }
            "List.slice" => {
                let ln = self.cty(&ptys[0]);
                self.tmp_owned(t, &format!("{}_slice({}, {}, {}, {})", ln, a[0], a[1], a[2], loc))
            }
            "List.join" => self.tmp_owned(t, &format!("tn_str_join({}, {})", a[0], a[1])),
            "Map.len" => {
                let mn = self.cty(&ptys[0]);
                self.tmp_val(t, &format!("{}_len({})", mn, a[0]))
            }
            "Map.get" => {
                let mn = self.cty(&ptys[0]);
                let vt = ptys[0].args()[1].clone();
                let vn = self.cty(&vt);
                let p = self.fresh("p");
                self.line(&format!("{} *{} = {}_get({}, {});", vn, p, mn, a[0], a[1]));
                let val = if self.trivial(&vt) { format!("*{}", p) } else { format!("{}_retain(*{})", vn, p) };
                self.some_none(t, &p, &val)
            }
            "Map.keys" | "Map.values" => {
                let ln = tn.clone();
                let et = t.args()[0].clone();
                let en = self.cty(&et);
                let l = self.tmp_owned(t, "NULL");
                let f = if name == "Map.keys" { "k" } else { "v" };
                let i = self.fresh("i");
                self.line(&format!(
                    "for (int64_t {i} = 0; {m} && {i} < {m}->n; {i}++) if ({m}->e[{i}].live) {ln}_push(&{l}, {en}_retain({m}->e[{i}].{f}));",
                    m = a[0],
                    l = l.code
                ));
                l
            }
            "Option.unwrap" | "Option.expect" | "Result.unwrap" | "Result.expect" => {
                let xt = ptys[0].clone();
                let tag = self.tag(&xt, &a[0]);
                self.line(&format!("if ({} != 0) {{", tag));
                match name {
                    "Option.unwrap" => self.line(&format!("    tn_trap(\"unwrap on None\", {});", loc)),
                    "Option.expect" => self.line(&format!("    tn_trap_str({}, {});", a[1], loc)),
                    _ => {
                        let b = self.fresh("b");
                        self.line(&format!("    tn_buf {} = tn_buf_new();", b));
                        if name == "Result.unwrap" {
                            let xn = self.cty(&xt);
                            self.line(&format!("    tn_buf_cstr(&{}, \"unwrap on \"); {}_show(&{}, {}, false);", b, xn, b, a[0]));
                        } else {
                            let et = xt.args()[1].clone();
                            let en = self.cty(&et);
                            let p = self.payload(&xt, &a[0], 1, 0);
                            self.line(&format!("    tn_buf_str(&{b}, {}); tn_buf_cstr(&{b}, \": \"); {en}_show(&{b}, {p}, false);", a[1]));
                        }
                        self.line(&format!("    tn_trap_buf(&{}, {});", b, loc));
                    }
                }
                self.line("}");
                bor(self.payload(&xt, &a[0], 0, 0))
            }
            "Console.print" | "Console.println" => {
                self.line(&format!("tn_write(({}).p, (size_t)({}).len);", a[1], a[1]));
                if name == "Console.println" {
                    self.line("tn_write(\"\\n\", 1);");
                }
                bor("0")
            }
            "Console.eprintln" => {
                self.line(&format!("tn_eprintln({});", a[1]));
                bor("0")
            }
            "Console.read_line" => {
                let s = self.fresh("s");
                self.line(&format!("tn_Str {} = {{0}};", s));
                let ok = self.tmp_val(&Ty::bool(), &format!("tn_read_line(&{})", s)).code;
                self.some_none(t, &ok, &s)
            }
            "Console.read_all" => self.tmp_owned(t, "tn_read_all()"),
            "Fs.read" | "Fs.list" => {
                let okt = t.args()[0].clone();
                let on = self.cty(&okt);
                let (r, m) = (self.fresh("r"), self.fresh("m"));
                self.line(&format!("{} {} = {{0}}; tn_Str {} = {{0}};", on, r, m));
                let f = if name == "Fs.read" { "tn_fs_read" } else { "tn_fs_list" };
                let k = self.tmp_val(&Ty::int(), &format!("{}({}, {}, &{}, &{})", f, a[0], a[1], r, m)).code;
                self.io_result(t, &k, &r, &m)
            }
            "Fs.write" | "Fs.append" | "Fs.remove" | "Fs.mkdir" => {
                let m = self.fresh("m");
                self.line(&format!("tn_Str {} = {{0}};", m));
                let f = format!("tn_fs_{}", &name[3..]);
                let extra = if name == "Fs.write" || name == "Fs.append" { format!("{}, ", a[2]) } else { String::new() };
                let k = self.tmp_val(&Ty::int(), &format!("{}({}, {}, {}&{})", f, a[0], a[1], extra, m)).code;
                self.io_result(t, &k, "0", &m)
            }
            "Fs.exists" => self.tmp_val(t, &format!("tn_fs_exists({}, {})", a[0], a[1])),
            "Fs.within" => self.tmp_owned(t, &format!("tn_fs_within({}, {})", a[0], a[1])),
            "Fs.read_only" => {
                self.tmp_owned(t, &format!("tn_fs_make(tn_Str_retain(({0})->root), ({0})->att, false)", a[0]))
            }
            "Clock.now_ms" => self.tmp_val(t, "tn_now_ms()"),
            "Clock.mono_ns" => self.tmp_val(t, "tn_mono_ns()"),
            "Clock.sleep_ms" => {
                self.line(&format!("tn_sleep_ms({});", a[1]));
                bor("0")
            }
            _ => panic!("emit: missing builtin {}", name),
        }
    }

    // Mutating builtins: `p` points at the receiver place; args are owned temps.
    fn extern_mut(&mut self, name: &str, p: &str, ptys: &[Ty], args: Vec<CV>, t: &Ty, sp: crate::diag::Span) -> CV {
        let rt = &ptys[0];
        let loc = self.loc(sp);
        let ln = self.cty(rt);
        let mut a = Vec::new();
        let tys: Vec<Ty> = match name {
            "List.push" => vec![rt.args()[0].clone()],
            "List.insert" => vec![Ty::int(), rt.args()[0].clone()],
            "List.sort_by" => vec![Ty::unit()],
            "Map.insert" => vec![rt.args()[0].clone(), rt.args()[1].clone()],
            _ => args.iter().map(|_| Ty::unit()).collect(),
        };
        for (v, ty) in args.into_iter().zip(tys) {
            if name == "List.sort_by" || name == "Map.remove" || name == "List.remove" {
                a.push(v.code);
            } else {
                a.push(self.own(v, &ty));
            }
        }
        match name {
            "List.push" => {
                self.line(&format!("{}_push({}, {});", ln, p, a[0]));
                bor("0")
            }
            "List.pop" => {
                let et = rt.args()[0].clone();
                let en = self.cty(&et);
                let o = self.fresh("o");
                self.line(&format!("{} {} = {{0}};", en, o));
                let ok = self.tmp_val(&Ty::bool(), &format!("{}_pop({}, &{})", ln, p, o)).code;
                self.some_none(t, &ok, &o)
            }
            "List.insert" => {
                self.line(&format!("{}_insert({}, {}, {}, {});", ln, p, a[0], a[1], loc));
                bor("0")
            }
            "List.remove" => self.tmp_owned(t, &format!("{}_remove({}, {}, {})", ln, p, a[0], loc)),
            "List.clear" | "List.reverse" | "List.sort" => {
                if name == "List.sort" && rt.any(&|x| x.is("Map")) {
                    self.line(&format!("tn_cur_loc = {};", loc));
                }
                self.line(&format!("{}_{}({});", ln, &name[5..], p));
                bor("0")
            }
            "List.sort_by" => {
                let Ty::Fn(_, kt) = ptys[1].clone() else { unreachable!() };
                let h = self.sort_by_helper(rt, &kt);
                if kt.any(&|x| x.is("Map")) {
                    self.line(&format!("tn_cur_loc = {};", loc));
                }
                self.line(&format!("{}({}, {});", h, p, a[0]));
                bor("0")
            }
            "Map.insert" => {
                self.line(&format!("{}_insert({}, {}, {});", ln, p, a[0], a[1]));
                bor("0")
            }
            "Map.remove" => {
                let vt = rt.args()[1].clone();
                let vn = self.cty(&vt);
                let o = self.fresh("o");
                self.line(&format!("{} {} = {{0}};", vn, o));
                let ok = self.tmp_val(&Ty::bool(), &format!("{}_remove({}, {}, &{})", ln, p, a[0], o)).code;
                self.some_none(t, &ok, &o)
            }
            _ => panic!("emit: missing mutating builtin {}", name),
        }
    }

    fn sort_by_helper(&mut self, lt: &Ty, kt: &Ty) -> String {
        let key = format!("sortby{:?}{:?}", lt, kt);
        if let Some(w) = self.wrappers.get(&key) {
            return w.clone();
        }
        let h = self.fresh("sortby");
        self.wrappers.insert(key, h.clone());
        let ln = self.cty(lt);
        let et = self.cty(&lt.args()[0]);
        let kn = self.cty(kt);
        let _ = writeln!(self.protos, "static void {}({} *p, tn_fn f);", h, ln);
        let _ = writeln!(
            self.helpers,
            "static int {h}_cmp(void *ctx, int64_t a, int64_t b) {{ {kn} *k = ctx; return {kn}_cmp(k[a], k[b]); }}"
        );
        let _ = writeln!(
            self.bodies,
            "static void {h}({ln} *p, tn_fn f) {{\n    int64_t n = {ln}_len(*p);\n    if (n < 2) return;\n    \
             {kn} *keys = tn_alloc(sizeof({kn}) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) keys[i] = (({kn} (*)(tn_env *, {et})) f.f)(f.env, (*p)->data[i]);\n    \
             int64_t *idx = tn_alloc(sizeof(int64_t) * (size_t)n), *tmp = tn_alloc(sizeof(int64_t) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) idx[i] = i;\n    tn_msort_idx(idx, tmp, n, {h}_cmp, keys);\n    \
             {ln}_unique(p);\n    {et} *out = tn_alloc(sizeof({et}) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) out[i] = (*p)->data[idx[i]];\n    \
             memcpy((*p)->data, out, sizeof({et}) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) {kn}_release(keys[i]);\n    free(keys); free(idx); free(tmp); free(out);\n}}"
        );
        h
    }
}

fn is_ident(s: &str) -> bool {
    s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

fn pat_names(p: &Pattern, out: &mut std::collections::HashSet<String>) {
    match &p.kind {
        PatKind::Bind(n) => {
            out.insert(format!("v_{}", n));
        }
        PatKind::Tuple(ps) | PatKind::Variant(_, _, ps) | PatKind::Or(ps) => ps.iter().for_each(|p| pat_names(p, out)),
        _ => {}
    }
}

// Expand or-patterns (also nested ones) into separate alternatives.
fn expand_or(p: &Pattern) -> Vec<Pattern> {
    let mk = |kind: PatKind| Pattern { id: p.id, span: p.span, kind };
    match &p.kind {
        PatKind::Or(alts) => alts.iter().flat_map(expand_or).collect(),
        PatKind::Tuple(ps) => product(ps).into_iter().map(|v| mk(PatKind::Tuple(v))).collect(),
        PatKind::Variant(q, n, ps) => product(ps).into_iter().map(|v| mk(PatKind::Variant(q.clone(), n.clone(), v))).collect(),
        _ => vec![p.clone()],
    }
}

fn product(ps: &[Pattern]) -> Vec<Vec<Pattern>> {
    let mut acc: Vec<Vec<Pattern>> = vec![vec![]];
    for p in ps {
        let alts = expand_or(p);
        let mut next = Vec::new();
        for a in &acc {
            for alt in &alts {
                let mut v = a.clone();
                v.push(alt.clone());
                next.push(v);
            }
        }
        acc = next;
    }
    acc
}
