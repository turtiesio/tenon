// Checker, part 2: expressions (types, names, methods, calls, matches).

use crate::ast::*;
use crate::check::*;
use crate::diag::{Diag, Span};
use crate::exhaust;
use crate::types::*;
use std::collections::HashMap;

impl Checker {
    pub(crate) fn expr(&mut self, e: &Expr, exp: &Ty) -> CResult<Ty> {
        let t = self.expr_inner(e, exp)?;
        self.unify_at(e.span, exp, &t)?;
        self.record(e.id, &t);
        Ok(t)
    }
    pub(crate) fn arith_ok(&self, op: BinOp, t: &Ty, span: Span) -> CResult<()> {
        let ok = match op {
            BinOp::Add => t.is("Int") || t.is("Float") || t.is("Str") || t.is("List"),
            BinOp::Sub | BinOp::Mul | BinOp::Div | BinOp::Rem => t.is("Int") || t.is("Float"),
            _ => true,
        };
        if ok { Ok(()) } else { err(span, format!("operator {:?} is not defined for {}", op, self.sub.resolve(t))) }
    }
    pub(crate) fn comparable(&self, t: &Ty, span: Span) -> CResult<()> {
        let t = self.sub.resolve(t);
        if t.any(&|t| matches!(t, Ty::Fn(..)) || matches!(t, Ty::Con(n, _) if is_capability(n))) {
            return err(span, format!("values of type {} cannot be compared", t));
        }
        Ok(())
    }
    pub(crate) fn instantiate(&mut self, fi: usize) -> (Vec<Ty>, HashMap<String, Ty>) {
        let tps = self.out.fns[fi].tparams.clone();
        let targs: Vec<Ty> = tps.iter().map(|_| self.sub.fresh()).collect();
        let m = tps.into_iter().zip(targs.iter().cloned()).collect();
        (targs, m)
    }
    pub(crate) fn call_args(&mut self, span: Span, params: &[Ty], args: &[Expr], what: &str) -> CResult<()> {
        if params.len() != args.len() {
            return err(span, format!("{} expects {} argument(s), found {}", what, params.len(), args.len()));
        }
        for (a, p) in args.iter().zip(params) {
            self.expr(a, p)?;
        }
        Ok(())
    }
    pub(crate) fn variant_by_name(&self, v: &str, span: Span) -> CResult<Option<(usize, usize)>> {
        let mut found = Vec::new();
        for (ei, e) in self.out.enums.iter().enumerate() {
            let vis = e.file == self.cur || e.file == 0 || (e.public && self.imported(&self.modules[e.file as usize]));
            if !vis {
                continue;
            }
            if let Some(vi) = e.variants.iter().position(|(n, _)| n == v) {
                found.push((ei, vi));
            }
        }
        match found.len() {
            0 => Ok(None),
            1 => Ok(Some(found[0])),
            _ => {
                let names: Vec<String> = found.iter().map(|(e, _)| self.out.enums[*e].name.clone()).collect();
                err(span, format!("variant '{}' is ambiguous ({}); qualify it, e.g. {}.{}", v, names.join(", "), names[0], v))
            }
        }
    }
    pub(crate) fn variant_value(&mut self, e: &Expr, callee_id: Id, ei: usize, vi: usize, args: Option<&[Expr]>) -> CResult<Ty> {
        let tps = self.out.enums[ei].tparams.clone();
        let targs: Vec<Ty> = tps.iter().map(|_| self.sub.fresh()).collect();
        let m: HashMap<_, _> = tps.into_iter().zip(targs.iter().cloned()).collect();
        let (vname, fts) = self.out.enums[ei].variants[vi].clone();
        let fts: Vec<Ty> = fts.iter().map(|t| t.subst(&m)).collect();
        let ety = Ty::Con(self.out.enums[ei].name.clone(), targs.clone());
        self.pending_res.push((callee_id, Res::Variant(ei, vi, targs)));
        match args {
            None if fts.is_empty() => Ok(ety),
            None => Ok(Ty::Fn(fts, Box::new(ety))),
            Some(args) => {
                if fts.is_empty() {
                    return err(e.span, format!("variant '{}' takes no arguments", vname));
                }
                self.call_args(e.span, &fts, args, &format!("variant '{}'", vname))?;
                Ok(ety)
            }
        }
    }
    pub(crate) fn expr_inner(&mut self, e: &Expr, exp: &Ty) -> CResult<Ty> {
        match &e.kind {
            ExprKind::Int(_) => Ok(Ty::int()),
            ExprKind::Float(_) => Ok(Ty::float()),
            ExprKind::Bool(_) => Ok(Ty::bool()),
            ExprKind::Unit => Ok(Ty::unit()),
            ExprKind::Str(segs) => {
                for s in segs {
                    if let StrSeg::Expr(x) = s {
                        let t = self.sub.fresh();
                        let t = self.expr(x, &t)?;
                        if let Ty::Fn(..) = self.sub.shallow(&t) {
                            return err(x.span, "functions cannot be converted to strings");
                        }
                    }
                }
                Ok(Ty::str())
            }
            ExprKind::Name(n) => {
                if let Some((si, l)) = self.lookup(n) {
                    let ty = l.ty.clone();
                    self.note_use(n, si, &ty);
                    self.pending_res.push((e.id, Res::Local(n.clone())));
                    return Ok(ty);
                }
                if let Some(fi) = self.lookup_fn(n) {
                    if self.out.fns[fi].is_const {
                        self.pending_res.push((e.id, Res::Const(fi)));
                        return Ok(self.out.fns[fi].ret.clone());
                    }
                    let (targs, m) = self.instantiate(fi);
                    let f = &self.out.fns[fi];
                    let t = Ty::Fn(f.params.iter().map(|(_, t)| t.subst(&m)).collect(), Box::new(f.ret.subst(&m)));
                    self.pending_res.push((e.id, Res::Fn(fi, targs)));
                    return Ok(t);
                }
                if upper(n) {
                    if let Some((ei, vi)) = self.variant_by_name(n, e.span)? {
                        return self.variant_value(e, e.id, ei, vi, None);
                    }
                }
                err(e.span, format!("unknown name '{}'", n))
            }
            ExprKind::Path(t0, m) => {
                let t = if let Some(md) = t0.strip_prefix('@') {
                    if !self.imported(md) {
                        return err(e.span, format!("unknown module '{}'", md));
                    }
                    md.to_string()
                } else {
                    self.resolve_type(t0, e.span)?
                };
                if let Some(ei) = self.out.enum_idx(&t) {
                    if let Some(vi) = self.out.enums[ei].variants.iter().position(|(n, _)| n == m) {
                        return self.variant_value(e, e.id, ei, vi, None);
                    }
                }
                let Some(fi) = self.find_fn(&format!("{}.{}", t, m)) else {
                    return err(e.span, format!("'{}' has no member '{}'", t, m));
                };
                self.visible(fi, e.span)?;
                if self.out.fns[fi].is_const {
                    self.pending_res.push((e.id, Res::Const(fi)));
                    return Ok(self.out.fns[fi].ret.clone());
                }
                let (targs, mm) = self.instantiate(fi);
                let f = &self.out.fns[fi];
                let ty = Ty::Fn(f.params.iter().map(|(_, t)| t.subst(&mm)).collect(), Box::new(f.ret.subst(&mm)));
                self.pending_res.push((e.id, Res::Fn(fi, targs)));
                Ok(ty)
            }
            ExprKind::Call(callee, args) => {
                // Variant constructors get their arguments checked directly.
                let variant = match &callee.kind {
                    ExprKind::Name(n) if upper(n) && self.lookup(n).is_none() && self.lookup_fn(n).is_none() => {
                        self.variant_by_name(n, callee.span)?
                    }
                    ExprKind::Path(t, m) if !t.starts_with('@') => self.resolve_type(t, callee.span).ok().and_then(|t| self.out.enum_idx(&t)).and_then(|ei| {
                        self.out.enums[ei].variants.iter().position(|(n, _)| n == m).map(|vi| (ei, vi))
                    }),
                    _ => None,
                };
                if let Some((ei, vi)) = variant {
                    let t = self.variant_value(e, callee.id, ei, vi, Some(args))?;
                    self.record(callee.id, &t);
                    return Ok(t);
                }
                let ct = self.sub.fresh();
                let ct = self.expr(callee, &ct)?;
                let ct = self.known(&ct, callee.span, "the called value")?;
                let Ty::Fn(ps, r) = ct else {
                    return err(callee.span, format!("cannot call a value of type {}", self.sub.resolve(&ct)));
                };
                if !matches!(callee.kind, ExprKind::Name(_) | ExprKind::Path(..)) || matches!(self.res_of(callee.id), Some(Res::Local(_))) {
                    self.pending_res.push((e.id, Res::CallValue));
                }
                self.call_args(e.span, &ps, args, "this function")?;
                Ok(*r)
            }
            ExprKind::Method(recv, m, args) => self.method(e, recv, m, args),
            ExprKind::Field(b, f) => {
                let t = self.sub.fresh();
                let t = self.expr(b, &t)?;
                let t = self.known(&t, b.span, "this value")?;
                let Some(fields) = self.out.struct_fields(&t) else {
                    return err(e.span, format!("type {} has no fields", self.sub.resolve(&t)));
                };
                let Some(fi) = fields.iter().position(|(n, _)| n == f) else {
                    return err(e.span, format!("type {} has no field '{}'", self.sub.resolve(&t), f));
                };
                if let Ty::Con(sn, _) = &t {
                    let si = self.out.struct_idx(sn).unwrap();
                    let st = &self.out.structs[si];
                    if st.file != self.cur && !st.pub_fields[fi] {
                        return err(e.span, format!("field '{}' of '{}' is private to its module", f, sn));
                    }
                }
                self.pending_res.push((e.id, Res::Field(fi)));
                Ok(fields[fi].1.clone())
            }
            ExprKind::TupleField(b, i) => {
                let t = self.sub.fresh();
                let t = self.expr(b, &t)?;
                let t = self.known(&t, b.span, "this value")?;
                match t {
                    Ty::Tuple(ts) if *i < ts.len() => Ok(ts[*i].clone()),
                    _ => err(e.span, format!("type {} has no element {}", self.sub.resolve(&t), i)),
                }
            }
            ExprKind::Index(b, i) => {
                let t = self.sub.fresh();
                let t = self.expr(b, &t)?;
                let t = self.known(&t, b.span, "the indexed value")?;
                match &t {
                    Ty::Con(n, a) if n == "List" => {
                        self.expr(i, &Ty::int())?;
                        Ok(a[0].clone())
                    }
                    Ty::Con(n, a) if n == "Map" => {
                        self.expr(i, &a[0])?;
                        Ok(a[1].clone())
                    }
                    _ => err(e.span, format!("cannot index a value of type {}", self.sub.resolve(&t))),
                }
            }
            ExprKind::Unary(op, x) => match op {
                UnOp::Not => {
                    self.expr(x, &Ty::bool())?;
                    Ok(Ty::bool())
                }
                UnOp::Neg => {
                    let t = self.sub.fresh();
                    let t = self.expr(x, &t)?;
                    let t = self.known(&t, x.span, "the operand")?;
                    if !(t.is("Int") || t.is("Float")) {
                        return err(e.span, format!("cannot negate {}", self.sub.resolve(&t)));
                    }
                    Ok(t)
                }
            },
            ExprKind::Binary(op, l, r) => {
                use BinOp::*;
                match op {
                    And | Or => {
                        self.expr(l, &Ty::bool())?;
                        self.expr(r, &Ty::bool())?;
                        Ok(Ty::bool())
                    }
                    Eq | Ne | Lt | Le | Gt | Ge => {
                        let t = self.sub.fresh();
                        let t = self.expr(l, &t)?;
                        self.expr(r, &t)?;
                        self.comparable(&t, e.span)?;
                        Ok(Ty::bool())
                    }
                    _ => {
                        let t = if let Ty::Var(_) = self.sub.shallow(exp) { self.sub.fresh() } else { exp.clone() };
                        let lt = self.expr(l, &t)?;
                        self.expr(r, &lt)?;
                        let lt = self.known(&lt, l.span, "the operand")?;
                        self.arith_ok(*op, &lt, e.span)?;
                        Ok(lt)
                    }
                }
            }
            ExprKind::If(c, then, els) => {
                self.expr(c, &Ty::bool())?;
                match els {
                    None => {
                        self.block(then, &Ty::unit(), true).map_err(|d| {
                            if d.msg.starts_with("type mismatch") {
                                Diag::new(d.span, &format!("{} ('if' without 'else' must produce Unit)", d.msg))
                            } else {
                                d
                            }
                        })?;
                        Ok(Ty::unit())
                    }
                    Some(x) => {
                        let t = self.block(then, exp, true)?;
                        self.expr(x, &t)?;
                        Ok(t)
                    }
                }
            }
            ExprKind::Block(b) => self.block(b, exp, true),
            ExprKind::Match(s, arms) => {
                let st = self.sub.fresh();
                let st = self.expr(s, &st)?;
                let res = exp.clone();
                for a in arms {
                    self.scopes.push(vec![]);
                    self.pattern(&a.pat, &st, false)?;
                    if let Some(g) = &a.guard {
                        self.expr(g, &Ty::bool())?;
                    }
                    self.expr(&a.body, &res)?;
                    self.scopes.pop();
                }
                let rst = self.sub.resolve(&st);
                self.exhaustive(e.span, &rst, arms)?;
                Ok(res)
            }
            ExprKind::List(elems) => {
                let et = match self.sub.shallow(exp) {
                    Ty::Con(n, a) if n == "List" => a[0].clone(),
                    _ => self.sub.fresh(),
                };
                for x in elems {
                    self.expr(x, &et)?;
                }
                Ok(Ty::list(et))
            }
            ExprKind::MapLit(pairs) => {
                let (kt, vt) = match self.sub.shallow(exp) {
                    Ty::Con(n, a) if n == "Map" => (a[0].clone(), a[1].clone()),
                    _ => (self.sub.fresh(), self.sub.fresh()),
                };
                for (k, v) in pairs {
                    self.expr(k, &kt)?;
                    self.expr(v, &vt)?;
                }
                Ok(Ty::Con("Map".into(), vec![kt, vt]))
            }
            ExprKind::Tuple(elems) => {
                let ets: Vec<Ty> = match self.sub.shallow(exp) {
                    Ty::Tuple(ts) if ts.len() == elems.len() => ts,
                    _ => elems.iter().map(|_| self.sub.fresh()).collect(),
                };
                for (x, t) in elems.iter().zip(&ets) {
                    self.expr(x, t)?;
                }
                Ok(Ty::Tuple(ets))
            }
            ExprKind::StructLit(name0, fields, base) => {
                let name = &self.resolve_type(name0, e.span)?;
                let Some(si) = self.out.struct_idx(name) else {
                    return err(e.span, format!("'{}' is not a struct", name0));
                };
                let sd = &self.out.structs[si];
                if sd.file != self.cur && sd.pub_fields.iter().any(|p| !p) {
                    return err(e.span, format!("'{}' has private fields; it can only be built inside its module", name0));
                }
                self.pending_res.push((e.id, Res::Struct(si)));
                let tps = self.out.structs[si].tparams.clone();
                let targs: Vec<Ty> = match self.sub.shallow(exp) {
                    Ty::Con(n, a) if n == *name => a,
                    _ => tps.iter().map(|_| self.sub.fresh()).collect(),
                };
                let st = Ty::Con(name.clone(), targs);
                let decl = self.out.struct_fields(&st).unwrap();
                for (i, (f, v)) in fields.iter().enumerate() {
                    let Some((_, ft)) = decl.iter().find(|(n, _)| n == f) else {
                        return err(v.span, format!("struct '{}' has no field '{}'", name, f));
                    };
                    if fields[..i].iter().any(|(g, _)| g == f) {
                        return err(v.span, format!("field '{}' is given twice", f));
                    }
                    self.expr(v, ft)?;
                }
                match base {
                    Some(b) => {
                        self.expr(b, &st)?;
                    }
                    None => {
                        for (f, _) in &decl {
                            if !fields.iter().any(|(g, _)| g == f) {
                                return err(e.span, format!("missing field '{}' in '{}'", f, name));
                            }
                        }
                    }
                }
                Ok(st)
            }
            ExprKind::Try(x) => {
                let t = self.sub.fresh();
                let t = self.expr(x, &t)?;
                let t = self.known(&t, x.span, "the operand of '?'")?;
                let ret = self.ctx.last().unwrap().ret.clone();
                match &t {
                    Ty::Con(n, a) if n == "Result" => {
                        let ok = self.sub.fresh();
                        let want = Ty::Con("Result".into(), vec![ok, a[1].clone()]);
                        if !self.sub.unify(&ret, &want) {
                            return err(e.span, format!(
                                "'?' on {} needs the function to return Result[_, {}], but it returns {}",
                                self.sub.resolve(&t), self.sub.resolve(&a[1]), self.sub.resolve(&ret)
                            ));
                        }
                        Ok(a[0].clone())
                    }
                    Ty::Con(n, a) if n == "Option" => {
                        let ok = self.sub.fresh();
                        if !self.sub.unify(&ret, &Ty::Con("Option".into(), vec![ok])) {
                            return err(e.span, format!(
                                "'?' on an Option needs the function to return an Option, but it returns {}",
                                self.sub.resolve(&ret)
                            ));
                        }
                        Ok(a[0].clone())
                    }
                    _ => err(e.span, format!("'?' needs a Result or Option, found {}", self.sub.resolve(&t))),
                }
            }
            ExprKind::Lambda(params, ret, body) => {
                let (pts, rt) = match self.sub.shallow(exp) {
                    Ty::Fn(ps, r) if ps.len() == params.len() => (ps, *r),
                    _ => (params.iter().map(|_| self.sub.fresh()).collect(), self.sub.fresh()),
                };
                let tps = self.tparams.clone();
                for ((_, ann), pt) in params.iter().zip(&pts) {
                    if let Some(a) = ann {
                        let at = self.lower_type(a, &tps)?;
                        self.unify_at(e.span, pt, &at)?;
                    }
                }
                if let Some(r) = ret {
                    let r = self.lower_type(r, &tps)?;
                    self.unify_at(e.span, &rt, &r)?;
                }
                self.out.captures.entry(e.id).or_default();
                self.lambda_stack.push((e.id, self.scopes.len()));
                self.scopes.push(vec![]);
                for ((n, _), pt) in params.iter().zip(&pts) {
                    self.bind(n, pt.clone(), false, e.span)?;
                }
                self.ctx.push(Ctx { ret: rt.clone(), loops: 0, lambda: Some(e.id) });
                self.expr(body, &rt)?;
                self.ctx.pop();
                self.scopes.pop();
                self.lambda_stack.pop();
                let _ = self.ctx.last().unwrap().lambda;
                Ok(Ty::Fn(pts, Box::new(rt)))
            }
        }
    }
    pub(crate) fn res_of(&self, id: Id) -> Option<&Res> {
        self.pending_res.iter().rev().find(|(i, _)| *i == id).map(|(_, r)| r)
    }
    pub(crate) fn method(&mut self, e: &Expr, recv: &Expr, m: &str, args: &[Expr]) -> CResult<Ty> {
        let rt = self.sub.fresh();
        let rt = self.expr(recv, &rt)?;
        let rt = self.known(&rt, recv.span, "the receiver")?;
        if m == "to_str" && args.is_empty() {
            self.comparable(&rt, e.span)?;
            self.pending_res.push((e.id, Res::ToStr));
            return Ok(Ty::str());
        }
        let owner = match &rt {
            Ty::Con(n, _) => n.clone(),
            Ty::Param(p) => return err(e.span, format!("no methods are available on generic type '{}'", p)),
            _ => return err(e.span, format!("type {} has no method '{}'", self.sub.resolve(&rt), m)),
        };
        let Some(fi) = self.find_fn(&format!("{}.{}", owner, m)) else {
            let hint = match self.out.struct_fields(&rt) {
                Some(fs) if fs.iter().any(|(n, _)| n == m) => format!("; to call the field, write ({}.{})(...)", "x", m),
                _ => String::new(),
            };
            return err(e.span, format!("type {} has no method '{}'{}", self.sub.resolve(&rt), m, hint));
        };
        self.visible(fi, e.span)?;
        let Some(sk) = self.out.fns[fi].self_kind else {
            return err(e.span, format!("'{}.{}' is not a method; call it as {}.{}(...)", owner, m, owner, m));
        };
        let (targs, mm) = self.instantiate(fi);
        let f = &self.out.fns[fi];
        let own = f.owner.as_ref().unwrap().subst(&mm);
        let params: Vec<Ty> = f.params[1..].iter().map(|(_, t)| t.subst(&mm)).collect();
        let ret = f.ret.subst(&mm);
        if !self.sub.unify(&own, &rt) {
            return err(e.span, format!("method '{}' requires {}, found {}", m, self.sub.resolve(&own), self.sub.resolve(&rt)));
        }
        if sk == SelfKind::Mut {
            self.place(recv, false).map_err(|d| {
                Diag::new(d.span, &format!("'{}' mutates its receiver: {}", m, d.msg))
            })?;
        }
        self.pending_res.push((e.id, Res::Method(fi, targs)));
        self.call_args(e.span, &params, args, &format!("method '{}'", m))?;
        Ok(ret)
    }
    // `let PAT = v else ...` with a pattern that always matches is a mistake.
    pub(crate) fn exhaustive_or_refutable(&mut self, pat: &Pattern, t: &Ty) -> CResult<()> {
        let arm = Arm { pat: pat.clone(), guard: None, body: Expr { id: u32::MAX, span: pat.span, kind: ExprKind::Unit } };
        if self.exhaustive(pat.span, t, &[arm]).is_ok() {
            return err(pat.span, "this pattern always matches, so the 'else' block can never run; use plain 'let'");
        }
        Ok(())
    }

    pub(crate) fn exhaustive(&mut self, span: Span, st: &Ty, arms: &[Arm]) -> CResult<()> {
        // Variant resolutions are still pending; expose them to the analysis.
        let mut res: HashMap<Id, (usize, usize)> = HashMap::new();
        for (id, r) in &self.pending_res {
            if let Res::Variant(e, v, _) = r {
                res.insert(*id, (*e, *v));
            }
        }
        let resolved = |t: &Ty| self.sub.resolve(t);
        exhaust::check(&self.out, &res, &resolved, span, st, arms)
    }
}
