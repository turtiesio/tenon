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

pub(crate) fn bor(code: impl Into<String>) -> CV {
    CV { code: code.into(), owned: false }
}

pub(crate) fn int_lit(i: i64) -> String {
    if i == i64::MIN { "(-9223372036854775807LL - 1)".into() } else { format!("{}LL", i) }
}

pub(crate) enum Step {
    Field(String),
    List(Ty, String),
    Map(Ty, String),
}

pub(crate) struct Place {
    root: String, // C pointer to the root variable
    steps: Vec<Step>,
}

// Can evaluating e assign to an existing local (so earlier borrowed reads go stale)?
fn may_mutate(c: &crate::check::Checked, e: &Expr) -> bool {
    let mut found = false;
    pub(crate) fn walk(c: &crate::check::Checked, e: &Expr, found: &mut bool) {
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

    pub(crate) fn sig(&mut self, fi: usize, targs: &[Ty]) -> (Vec<Ty>, Ty) {
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

    pub(crate) fn line(&mut self, s: &str) {
        for _ in 0..self.st.indent {
            self.st.out.push_str("    ");
        }
        self.st.out.push_str(s);
        self.st.out.push('\n');
    }

    pub(crate) fn ety(&self, e: &Expr) -> Ty {
        self.c.ty(e.id).subst(&self.st.tsub)
    }

    pub(crate) fn sub(&self, t: &Ty) -> Ty {
        t.subst(&self.st.tsub)
    }

    pub fn trivial(&mut self, t: &Ty) -> bool {
        match t {
            Ty::Con(n, a) if a.is_empty() && matches!(n.as_str(), "Int" | "Float" | "Bool" | "Unit" | "Console" | "Clock" | "Net") => true,
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

    pub(crate) fn push(&mut self, kind: ScopeKind) {
        self.st.scopes.push(Scope { kind, owned: vec![] });
    }

    pub(crate) fn release_list(&mut self, owned: &[(String, Ty)]) {
        for (n, t) in owned.iter().rev() {
            if !self.trivial(t) {
                let tn = self.cty(t);
                self.line(&format!("{}_release({});", tn, n));
            }
        }
    }

    pub(crate) fn pop(&mut self) {
        let s = self.st.scopes.pop().unwrap();
        self.release_list(&s.owned);
    }

    // Release (without popping) every scope down to and including the innermost `kind`.
    pub(crate) fn release_to(&mut self, kind: ScopeKind) {
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

    pub(crate) fn reg(&mut self, name: &str, t: &Ty) {
        self.st.scopes.last_mut().unwrap().owned.push((name.to_string(), t.clone()));
    }

    pub(crate) fn reg_local(&mut self, name: &str, t: &Ty) {
        let s = self.st.scopes.iter_mut().rev().find(|s| s.kind != ScopeKind::Stmt).unwrap();
        s.owned.push((name.to_string(), t.clone()));
    }

    pub(crate) fn unreg(&mut self, name: &str) {
        for s in self.st.scopes.iter_mut().rev() {
            if let Some(i) = s.owned.iter().position(|(n, _)| n == name) {
                s.owned.remove(i);
                return;
            }
        }
    }

    // Take ownership of a value: move an owned temp, or retain a borrowed one.
    pub(crate) fn own(&mut self, cv: CV, t: &Ty) -> String {
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

    pub(crate) fn tmp_owned(&mut self, t: &Ty, init: &str) -> CV {
        let tn = self.cty(t);
        let n = self.fresh("t");
        self.line(&format!("{} {} = {};", tn, n, init));
        self.reg(&n, t);
        CV { code: n, owned: true }
    }

    pub(crate) fn tmp_val(&mut self, t: &Ty, init: &str) -> CV {
        let tn = self.cty(t);
        let n = self.fresh("t");
        self.line(&format!("{} {} = {};", tn, n, init));
        bor(n)
    }

    // Evaluate left to right; a value that a later operand could invalidate is retained first.
    pub(crate) fn eval_list(&mut self, es: &[&Expr]) -> Vec<CV> {
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
    pub(crate) fn block_into(&mut self, b: &Block, result: Option<&str>, rt: &Ty) {
        self.push(ScopeKind::Block);
        self.stmts_into(b, result, rt);
        self.pop();
    }

    pub(crate) fn stmts_into(&mut self, b: &Block, result: Option<&str>, rt: &Ty) {
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

    pub(crate) fn stmt(&mut self, s: &Stmt) {
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
                if let StmtKind::Let { els: Some(b), .. } = &s.kind {
                    let v = if cv.owned || is_ident(&cv.code) { cv.code.clone() } else { self.tmp_val(&t, &cv.code).code };
                    let test = self.pat_test(pat, &v, &t);
                    self.line(&format!("if (!({})) {{", test));
                    self.st.indent += 1;
                    self.block_into(b, None, &Ty::unit());
                    self.st.indent -= 1;
                    self.line("}");
                    self.bind(pat, &v, &t, false);
                } else if let PatKind::Bind(n) = &pat.kind {
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

    pub(crate) fn for_loop(&mut self, pat: &Pattern, iter: &ForIter, body: &Block) {
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

    pub(crate) fn place(&mut self, e: &Expr) -> Place {
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
    pub(crate) fn place_ptr(&mut self, p: &Place, n: usize, sp: crate::diag::Span) -> String {
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

    pub(crate) fn assign(&mut self, target: &Expr, op: Option<BinOp>, value: &Expr, s: &Stmt) {
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

    pub(crate) fn result_var(&mut self, t: &Ty) -> Option<String> {
        if t.is("Unit") {
            return None;
        }
        let tn = self.cty(t);
        let r = self.fresh("r");
        self.line(&format!("{} {} = {{0}};", tn, r));
        Some(r)
    }

    pub(crate) fn finish_result(&mut self, res: Option<String>, t: &Ty) -> CV {
        match res {
            Some(r) => {
                self.reg(&r, t);
                CV { code: r, owned: true }
            }
            None => bor("0"),
        }
    }

    pub(crate) fn interp_str(&mut self, segs: &[StrSeg]) -> CV {
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

    pub(crate) fn local_code(&self, n: &str) -> String {
        if n == "self" && self.st.self_ptr { "(*p_self)".into() } else { format!("v_{}", n) }
    }

    pub(crate) fn name_value(&mut self, e: &Expr, t: &Ty) -> CV {
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

    pub(crate) fn call(&mut self, e: &Expr, callee: &Expr, args: &[Expr], t: &Ty) -> CV {
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

    pub(crate) fn method(&mut self, e: &Expr, recv: &Expr, args: &[Expr], t: &Ty) -> CV {
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

    pub(crate) fn binary(&mut self, e: &Expr, op: BinOp, l: &Expr, r: &Expr) -> CV {
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

    pub(crate) fn arith(&mut self, op: BinOp, t: &Ty, a: &str, b: &str, sp: crate::diag::Span) -> CV {
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












}

pub(crate) fn is_ident(s: &str) -> bool {
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


