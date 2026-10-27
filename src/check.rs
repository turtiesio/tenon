// Checker: resolves names, infers and checks types, checks places and
// exhaustiveness. Output is the AST plus side tables (types, resolutions)
// shared by both backends.

use crate::ast::*;
use crate::diag::{Diag, Span};
use crate::exhaust;
use crate::types::*;
use std::collections::HashMap;

#[derive(Clone, Debug)]
pub enum Res {
    Local(String),
    Fn(usize, Vec<Ty>),               // function index, type args (all tparams)
    Variant(usize, usize, Vec<Ty>),   // enum, variant, enum type args
    Field(usize),                     // struct field index
    Method(usize, Vec<Ty>),           // method call resolved to function
    Struct(usize),                    // struct literal
    ToStr,                            // derived `x.to_str()`
    CallValue,                        // calling a function value
}

pub struct StructInfo {
    pub name: String,
    pub tparams: Vec<String>,
    pub fields: Vec<(String, Ty)>,
    pub kind: Kind,
    pub file: u16,
    pub public: bool,
    pub pub_fields: Vec<bool>,
}

pub struct EnumInfo {
    pub name: String,
    pub tparams: Vec<String>,
    pub variants: Vec<(String, Vec<Ty>)>,
    pub kind: Kind,
    pub file: u16,
    pub public: bool,
}

pub struct FnInfo {
    pub name: String, // full name, e.g. "List.push"
    pub tparams: Vec<String>,
    pub owner: Option<Ty>,
    pub params: Vec<(String, Ty)>, // includes `self` first for methods
    pub ret: Ty,
    pub self_kind: Option<SelfKind>,
    pub is_extern: bool,
    pub public: bool,
    pub span: Span,
}

pub struct Checked {
    pub prog: Program,
    pub types: HashMap<Id, Ty>,
    pub res: HashMap<Id, Res>,
    pub captures: HashMap<Id, Vec<(String, Ty)>>,
    pub structs: Vec<StructInfo>,
    pub enums: Vec<EnumInfo>,
    pub fns: Vec<FnInfo>,
    pub main: usize,
}

impl Checked {
    pub fn ty(&self, id: Id) -> &Ty {
        &self.types[&id]
    }
    pub fn struct_idx(&self, name: &str) -> Option<usize> {
        self.structs.iter().position(|s| s.name == name)
    }
    pub fn enum_idx(&self, name: &str) -> Option<usize> {
        self.enums.iter().position(|s| s.name == name)
    }
    // Linear (must be consumed exactly once) or unique (never copied), including
    // any type that contains such a value.
    pub fn kind_of(&self, t: &Ty) -> Kind {
        let mut k = Kind::Plain;
        let mut seen = Vec::new();
        self.kind_walk(t, &mut k, &mut seen);
        k
    }
    fn kind_walk(&self, t: &Ty, k: &mut Kind, seen: &mut Vec<Ty>) {
        if seen.contains(t) || *k == Kind::Linear {
            return;
        }
        seen.push(t.clone());
        fn note(k: &mut Kind, d: Kind) {
            if d == Kind::Linear || (d == Kind::Unique && *k == Kind::Plain) {
                *k = d;
            }
        }
        match t {
            Ty::Tuple(ts) => ts.iter().for_each(|t| self.kind_walk(t, k, seen)),
            Ty::Con(n, args) => {
                args.iter().for_each(|t| self.kind_walk(t, k, seen));
                if is_unique_builtin(n) {
                    note(k, Kind::Unique);
                } else if let Some(i) = self.struct_idx(n) {
                    note(k, self.structs[i].kind);
                } else if let Some(i) = self.enum_idx(n) {
                    note(k, self.enums[i].kind);
                }
            }
            _ => {}
        }
    }
    pub fn struct_fields(&self, t: &Ty) -> Option<Vec<(String, Ty)>> {
        let Ty::Con(n, args) = t else { return None };
        let s = &self.structs[self.struct_idx(n)?];
        let m: HashMap<_, _> = s.tparams.iter().cloned().zip(args.iter().cloned()).collect();
        Some(s.fields.iter().map(|(f, t)| (f.clone(), t.subst(&m))).collect())
    }
    pub fn enum_variants(&self, t: &Ty) -> Option<Vec<(String, Vec<Ty>)>> {
        let Ty::Con(n, args) = t else { return None };
        let e = &self.enums[self.enum_idx(n)?];
        let m: HashMap<_, _> = e.tparams.iter().cloned().zip(args.iter().cloned()).collect();
        Some(e.variants.iter().map(|(v, ts)| (v.clone(), ts.iter().map(|t| t.subst(&m)).collect())).collect())
    }
}

#[derive(Clone)]
struct Local {
    ty: Ty,
    mutable: bool,
    depth: usize, // lambda nesting depth where defined
}

struct Ctx {
    ret: Ty,
    loops: usize,
    lambda: Option<Id>,
}

pub struct Checker {
    out: Checked,
    sub: Subst,
    scopes: Vec<Vec<(String, Local)>>,
    ctx: Vec<Ctx>,
    pending_types: Vec<(Id, Ty)>,
    pending_res: Vec<(Id, Res)>,
    lambda_stack: Vec<(Id, usize)>, // (lambda id, scope index where it starts)
    tparams: Vec<String>,
    self_mut: bool,
    cur: u16,                          // file (module) being checked
    modules: Vec<String>,              // module name per file
    imports: HashMap<u16, Vec<String>>, // modules imported by each file
}

type CResult<T> = Result<T, Diag>;

fn err<T>(span: Span, msg: impl AsRef<str>) -> CResult<T> {
    Err(Diag::new(span, msg.as_ref()))
}

// Type parameters are `T`, `K`, `V2`, ...; type names are longer, so the two never collide.
pub fn is_tparam_name(s: &str) -> bool {
    let b = s.as_bytes();
    !b.is_empty() && b[0].is_ascii_uppercase() && b[1..].iter().all(|c| c.is_ascii_digit())
}

fn upper(s: &str) -> bool {
    s.chars().next().map(|c| c.is_ascii_uppercase()).unwrap_or(false)
}

// `Value.member` parses as a type path when the name is capitalized (a unit
// variant such as `Red.name()`); turn those back into field/method access.
fn fix_paths(prog: &mut Program) {
    let mut types: Vec<String> = BUILTIN_TYPES.iter().map(|(n, _, _)| n.to_string()).collect();
    types.extend(prog.structs.iter().map(|s| s.name.clone()));
    types.extend(prog.enums.iter().map(|e| e.name.clone()));
    let aliases: HashMap<u16, Vec<String>> = prog.imports.iter().fold(HashMap::new(), |mut m, im| {
        m.entry(im.file).or_default().push(im.name.clone());
        m
    });
    fn fix(e: &mut Expr, types: &[String], aliases: &HashMap<u16, Vec<String>>) {
        let is_mod = |n: &str| aliases.get(&e.span.file).map(|v| v.iter().any(|m| m == n)).unwrap_or(false);
        // `module.f(..)` and `module.Type.f(..)`
        let module_call = match &mut e.kind {
            ExprKind::Method(recv, f, args) => match &recv.kind {
                ExprKind::Name(m) if is_mod(m) => Some((format!("@{}", m), f.clone(), std::mem::take(args), recv.id, recv.span)),
                ExprKind::Field(b, t) => match &b.kind {
                    ExprKind::Name(m) if is_mod(m) && upper(t) => Some((format!("{}.{}", m, t), f.clone(), std::mem::take(args), recv.id, recv.span)),
                    _ => None,
                },
                _ => None,
            },
            _ => None,
        };
        if let Some((t, f, args, id, span)) = module_call {
            let callee = Expr { id, span, kind: ExprKind::Path(t, f) };
            e.kind = ExprKind::Call(Box::new(callee), args);
        }
        let replace = match &mut e.kind {
            ExprKind::Call(callee, args) => match &callee.kind {
                ExprKind::Path(t, m) if !types.contains(t) && !t.starts_with('@') && !t.contains('.') => {
                    let recv = Expr { id: callee.id, span: callee.span, kind: ExprKind::Name(t.clone()) };
                    Some(ExprKind::Method(Box::new(recv), m.clone(), std::mem::take(args)))
                }
                _ => None,
            },
            ExprKind::Path(t, m) if !types.contains(t) && !t.starts_with('@') && !t.contains('.') => {
                let recv = Expr { id: u32::MAX - e.id, span: e.span, kind: ExprKind::Name(t.clone()) };
                Some(ExprKind::Field(Box::new(recv), m.clone()))
            }
            _ => None,
        };
        if let Some(k) = replace {
            e.kind = k;
        }
        crate::interp::visit_children_mut(e, &mut |x| fix(x, types, aliases));
    }
    for f in &mut prog.fns {
        if let Some(b) = &mut f.body {
            for s in &mut b.stmts {
                crate::interp::visit_stmt_mut(s, &mut |x| fix(x, &types, &aliases));
            }
        }
    }
}

pub fn check(mut prog: Program) -> CResult<Checked> {
    fix_paths(&mut prog);
    let mut c = Checker {
        out: Checked {
            prog: Program { structs: vec![], enums: vec![], fns: vec![], imports: vec![], modules: vec![] },
            types: HashMap::new(),
            res: HashMap::new(),
            captures: HashMap::new(),
            structs: vec![],
            enums: vec![],
            fns: vec![],
            main: 0,
        },
        sub: Subst::default(),
        scopes: vec![],
        ctx: vec![],
        pending_types: vec![],
        pending_res: vec![],
        lambda_stack: vec![],
        tparams: vec![],
        self_mut: false,
        cur: 1,
        modules: prog.modules.clone(),
        imports: HashMap::new(),
    };
    for im in &prog.imports {
        c.imports.entry(im.file).or_default().push(im.name.clone());
    }
    c.declare(&prog)?;
    for i in 0..prog.fns.len() {
        c.check_fn(&prog.fns[i], i)?;
    }
    let main = prog.fns.iter().position(|f| f.name == "main" && f.owner.is_none());
    let Some(main) = main else {
        return err(Span { file: 1, line: 1, col: 1 }, "program has no 'fn main'");
    };
    c.check_main(main)?;
    for i in 0..prog.fns.len() {
        crate::linear::check_fn(&c.out, &prog, i)?;
    }
    c.out.main = main;
    c.out.prog = prog;
    Ok(c.out)
}

impl Checker {
    // ---- declarations ----

    // Internal name of item `n` declared in `file`: modules prefix their items.
    fn internal(&self, file: u16, n: &str) -> String {
        match self.modules.get(file as usize) {
            Some(m) if !m.is_empty() => format!("{}.{}", m, n),
            _ => n.to_string(),
        }
    }

    fn imported(&self, m: &str) -> bool {
        self.imports.get(&self.cur).map(|v| v.iter().any(|x| x == m)).unwrap_or(false)
    }

    fn type_decl(&self, internal: &str) -> Option<(u16, bool)> {
        if let Some(s) = self.out.structs.iter().find(|s| s.name == internal) {
            return Some((s.file, s.public));
        }
        self.out.enums.iter().find(|e| e.name == internal).map(|e| (e.file, e.public))
    }

    // Resolve a type name as written in the current module to its internal name.
    fn resolve_type(&self, n: &str, sp: Span) -> CResult<String> {
        if BUILTIN_TYPES.iter().any(|(b, _, _)| *b == n) {
            return Ok(n.to_string());
        }
        if let Some((m, _)) = n.split_once('.') {
            if !self.imported(m) {
                return err(sp, format!("unknown module '{}'; add 'import {}'", m, m));
            }
            return match self.type_decl(n) {
                Some((_, true)) => Ok(n.to_string()),
                Some(_) => err(sp, format!("type '{}' is private to module '{}'", n, m)),
                None => err(sp, format!("module '{}' has no type '{}'", m, &n[m.len() + 1..])),
            };
        }
        let own = self.internal(self.cur, n);
        if self.type_decl(&own).is_some() {
            return Ok(own);
        }
        match self.type_decl(n) {
            Some((0, _)) => Ok(n.to_string()),
            _ => err(sp, format!("unknown type '{}'", n)),
        }
    }

    fn arity(&self, n: &str) -> Option<usize> {
        if let Some((_, a, _)) = BUILTIN_TYPES.iter().find(|(b, _, _)| *b == n) {
            return Some(*a);
        }
        if let Some(s) = self.out.structs.iter().find(|s| s.name == n) {
            return Some(s.tparams.len());
        }
        self.out.enums.iter().find(|e| e.name == n).map(|e| e.tparams.len())
    }

    fn lower_type(&self, t: &TypeExpr, params: &[String]) -> CResult<Ty> {
        match &t.kind {
            TypeExprKind::Named(n, args) => {
                if params.contains(n) {
                    if !args.is_empty() {
                        return err(t.span, format!("type parameter '{}' takes no arguments", n));
                    }
                    return Ok(Ty::Param(n.clone()));
                }
                let n = self.resolve_type(n, t.span)?;
                let ar = self.arity(&n).unwrap();
                if ar != args.len() {
                    return err(t.span, format!("type '{}' expects {} type argument(s), found {}", n, ar, args.len()));
                }
                let a = args.iter().map(|a| self.lower_type(a, params)).collect::<CResult<Vec<_>>>()?;
                Ok(Ty::Con(n, a))
            }
            TypeExprKind::Fn(a, r) => Ok(Ty::Fn(
                a.iter().map(|a| self.lower_type(a, params)).collect::<CResult<Vec<_>>>()?,
                Box::new(self.lower_type(r, params)?),
            )),
            TypeExprKind::Tuple(a) => {
                Ok(Ty::Tuple(a.iter().map(|a| self.lower_type(a, params)).collect::<CResult<Vec<_>>>()?))
            }
        }
    }

    fn declare(&mut self, prog: &Program) -> CResult<()> {
        let mut seen: HashMap<String, Span> = HashMap::new();
        let names = prog.structs.iter().map(|s| (&s.name, s.span, &s.kind))
            .chain(prog.enums.iter().map(|e| (&e.name, e.span, &e.kind)));
        for (n0, sp, _) in names {
            let full = self.internal(sp.file, n0);
            let n = &full;
            if !upper(n0) {
                return err(sp, format!("type names start with an uppercase letter: '{}'", n0));
            }
            if is_tparam_name(n0) {
                return err(sp, format!("'{}' is reserved for type parameters (one capital letter, optional digits); use a longer type name", n));
            }
            if seen.contains_key(n) || BUILTIN_TYPES.iter().any(|(b, _, _)| b == n) {
                return err(sp, format!("type '{}' is already defined", n));
            }
            seen.insert(n.clone(), sp);
        }
        for (n, sp, ps) in prog.structs.iter().map(|s| (&s.name, s.span, &s.tparams)).chain(prog.enums.iter().map(|e| (&e.name, e.span, &e.tparams))) {
            if let Some(p) = ps.iter().find(|p| !is_tparam_name(p)) {
                return err(sp, format!("type parameter '{}' of '{}' must be one capital letter, optionally followed by digits", p, n));
            }
        }
        for s in &prog.structs {
            self.out.structs.push(StructInfo {
                name: self.internal(s.span.file, &s.name),
                tparams: s.tparams.clone(),
                fields: vec![],
                kind: s.kind,
                file: s.span.file,
                public: s.public,
                pub_fields: s.pub_fields.clone(),
            });
        }
        for e in &prog.enums {
            self.out.enums.push(EnumInfo {
                name: self.internal(e.span.file, &e.name),
                tparams: e.tparams.clone(),
                variants: vec![],
                kind: e.kind,
                file: e.span.file,
                public: e.public,
            });
        }
        for (i, s) in prog.structs.iter().enumerate() {
            self.cur = s.span.file;
            let mut fields = Vec::new();
            for (f, t) in &s.fields {
                if fields.iter().any(|(g, _)| g == f) {
                    return err(t.span, format!("duplicate field '{}'", f));
                }
                fields.push((f.clone(), self.lower_type(t, &s.tparams)?));
            }
            self.out.structs[i].fields = fields;
        }
        let mut vseen: HashMap<String, Span> = HashMap::new();
        for (i, e) in prog.enums.iter().enumerate() {
            self.cur = e.span.file;
            let mut vs: Vec<(String, Vec<Ty>)> = Vec::new();
            for v in &e.variants {
                if !upper(&v.name) {
                    return err(v.span, format!("variant names start with an uppercase letter: '{}'", v.name));
                }
                if vs.iter().any(|(n, _)| *n == v.name) {
                    return err(v.span, format!("duplicate variant '{}'", v.name));
                }
                let ts = v.fields.iter().map(|t| self.lower_type(t, &e.tparams)).collect::<CResult<Vec<_>>>()?;
                vs.push((v.name.clone(), ts));
                vseen.entry(v.name.clone()).or_insert(v.span);
            }
            self.out.enums[i].variants = vs;
        }
        self.check_recursion()?;
        crate::linear::check_decls(&self.out, prog)?;
        // functions
        let mut fseen: HashMap<String, Span> = HashMap::new();
        for f in &prog.fns {
            self.cur = f.span.file;
            let mut tparams = Vec::new();
            let owner = match &f.owner {
                None => None,
                Some(o) => {
                    let TypeExprKind::Named(_, args) = &o.kind else { unreachable!() };
                    for a in args {
                        if let TypeExprKind::Named(an, aa) = &a.kind {
                            if aa.is_empty() && is_tparam_name(an) {
                                tparams.push(an.clone());
                            }
                        }
                    }
                    let ot = self.lower_type(o, &tparams)?;
                    if let Ty::Con(on, _) = &ot {
                        if let Some((file, _)) = self.type_decl(on) {
                            if file != f.span.file {
                                return err(o.span, format!("methods of '{}' can only be defined in the module that defines it", on));
                            }
                        }
                    }
                    Some(ot)
                }
            };
            let full = match &owner {
                Some(Ty::Con(on, _)) => format!("{}.{}", on, f.name),
                _ => self.internal(f.span.file, &f.name),
            };
            if fseen.contains_key(&full) {
                return err(f.span, format!("function '{}' is already defined", full));
            }
            fseen.insert(full.clone(), f.span);
            if upper(&f.name) {
                return err(f.span, format!("function names start with a lowercase letter: '{}'", f.name));
            }
            if f.body.is_none() && f.span.file != 0 {
                return err(f.span, "'extern' is reserved for the prelude");
            }
            for t in &f.tparams {
                if !is_tparam_name(t) {
                    return err(f.span, format!("type parameter '{}' must be one capital letter, optionally followed by digits", t));
                }
                if tparams.contains(t) {
                    return err(f.span, format!("type parameter '{}' shadows another type", t));
                }
                tparams.push(t.clone());
            }
            let mut params = Vec::new();
            if let (Some(_), Some(o)) = (f.self_kind, &owner) {
                params.push(("self".to_string(), o.clone()));
            }
            for p in &f.params {
                if params.iter().any(|(n, _)| *n == p.name) {
                    return err(p.span, format!("duplicate parameter '{}'", p.name));
                }
                if upper(&p.name) {
                    return err(p.span, "parameter names start with a lowercase letter");
                }
                params.push((p.name.clone(), self.lower_type(&p.ty, &tparams)?));
            }
            let ret = match &f.ret {
                Some(t) => self.lower_type(t, &tparams)?,
                None => Ty::unit(),
            };
            self.out.fns.push(FnInfo {
                name: full,
                tparams,
                owner,
                params,
                ret,
                self_kind: f.self_kind,
                is_extern: f.body.is_none(),
                public: f.public,
                span: f.span,
            });
        }
        Ok(())
    }

    // A struct may not contain itself by value (it would be infinitely large).
    fn check_recursion(&self) -> CResult<()> {
        fn contains(c: &Checker, t: &Ty, target: &str, seen: &mut Vec<String>) -> bool {
            match t {
                Ty::Con(n, a) => {
                    if n == target {
                        return true;
                    }
                    if n == "List" || n == "Map" || seen.contains(n) {
                        return false;
                    }
                    seen.push(n.clone());
                    if a.iter().any(|t| contains(c, t, target, seen)) {
                        return true;
                    }
                    if let Some(s) = c.out.structs.iter().find(|s| s.name == *n) {
                        return s.fields.iter().any(|(_, t)| contains(c, t, target, seen));
                    }
                    false
                }
                Ty::Tuple(a) => a.iter().any(|t| contains(c, t, target, seen)),
                _ => false,
            }
        }
        for s in &self.out.structs {
            for (f, t) in &s.fields {
                if contains(self, t, &s.name, &mut vec![]) {
                    return err(Span::default(), format!(
                        "struct '{}' contains itself through field '{}'; use an enum or List to break the cycle",
                        s.name, f
                    ));
                }
            }
        }
        Ok(())
    }

    fn check_main(&self, i: usize) -> CResult<()> {
        let f = &self.out.fns[i];
        if !f.tparams.is_empty() {
            return err(f.span, "'main' cannot be generic");
        }
        match f.params.as_slice() {
            [] => {}
            [(_, t)] if t.is("Sys") => {}
            _ => return err(f.span, "'main' takes no parameters or a single 'Sys'"),
        }
        let ok = f.ret.is("Unit") || (f.ret.is("Result") && f.ret.args()[0].is("Unit"));
        if !ok {
            return err(f.span, "'main' returns Unit or Result[Unit, E]");
        }
        Ok(())
    }

    // ---- functions ----

    fn check_fn(&mut self, f: &FnDecl, idx: usize) -> CResult<()> {
        let Some(body) = &f.body else { return Ok(()) };
        self.cur = f.span.file;
        self.sub = Subst::default();
        let info = &self.out.fns[idx];
        self.tparams = info.tparams.clone();
        self.self_mut = f.self_kind == Some(SelfKind::Mut);
        let ret = info.ret.clone();
        let params = info.params.clone();
        self.scopes = vec![params
            .into_iter()
            .map(|(n, ty)| (n, Local { ty, mutable: false, depth: 0 }))
            .collect()];
        self.ctx = vec![Ctx { ret: ret.clone(), loops: 0, lambda: None }];
        self.lambda_stack.clear();
        self.block(body, &ret, true)?;
        self.flush();
        Ok(())
    }

    fn flush(&mut self) {
        for (id, t) in std::mem::take(&mut self.pending_types) {
            self.out.types.insert(id, self.sub.finish(&t));
        }
        for (id, r) in std::mem::take(&mut self.pending_res) {
            let r = match r {
                Res::Fn(i, ts) => Res::Fn(i, ts.iter().map(|t| self.sub.finish(t)).collect()),
                Res::Variant(e, v, ts) => Res::Variant(e, v, ts.iter().map(|t| self.sub.finish(t)).collect()),
                Res::Method(i, ts) => Res::Method(i, ts.iter().map(|t| self.sub.finish(t)).collect()),
                r => r,
            };
            self.out.res.insert(id, r);
        }
        let caps: Vec<Id> = self.out.captures.keys().cloned().collect();
        for id in caps {
            let v = self.out.captures.get_mut(&id).unwrap();
            for (_, t) in v.iter_mut() {
                *t = self.sub.finish(t);
            }
        }
    }

    fn record(&mut self, id: Id, t: &Ty) {
        self.pending_types.push((id, t.clone()));
    }

    fn unify_at(&mut self, span: Span, expected: &Ty, found: &Ty) -> CResult<()> {
        if self.sub.unify(expected, found) {
            Ok(())
        } else {
            err(span, format!(
                "type mismatch: expected {}, found {}",
                self.sub.resolve(expected),
                self.sub.resolve(found)
            ))
        }
    }

    fn known(&self, t: &Ty, span: Span, what: &str) -> CResult<Ty> {
        let t = self.sub.shallow(t);
        if let Ty::Var(_) = t {
            return err(span, format!("the type of {} must be known here; add a type annotation", what));
        }
        Ok(t)
    }

    // ---- scopes ----

    fn lookup(&self, n: &str) -> Option<(usize, &Local)> {
        for (i, s) in self.scopes.iter().enumerate().rev() {
            if let Some((_, l)) = s.iter().rev().find(|(m, _)| m == n) {
                return Some((i, l));
            }
        }
        None
    }

    fn bind(&mut self, n: &str, ty: Ty, mutable: bool, span: Span) -> CResult<()> {
        if self.lookup(n).is_some() {
            return err(span, format!("'{}' is already defined in this function (shadowing is not allowed)", n));
        }
        if self.imported(n) {
            return err(span, format!("'{}' is the name of an imported module", n));
        }
        let depth = self.lambda_stack.len();
        self.scopes.last_mut().unwrap().push((n.to_string(), Local { ty, mutable, depth }));
        Ok(())
    }

    // Record captures for every lambda between the use and the definition.
    fn note_use(&mut self, n: &str, scope_idx: usize, ty: &Ty) {
        for (lam, start) in self.lambda_stack.clone() {
            if scope_idx < start {
                let caps = self.out.captures.entry(lam).or_default();
                if !caps.iter().any(|(m, _)| m == n) {
                    caps.push((n.to_string(), ty.clone()));
                }
            }
        }
    }

    // ---- statements ----

    // Checks a block; the value is the trailing expression statement, if any.
    fn block(&mut self, b: &Block, exp: &Ty, value_used: bool) -> CResult<Ty> {
        self.scopes.push(vec![]);
        let n = b.stmts.len();
        let mut result = None;
        for (i, s) in b.stmts.iter().enumerate() {
            let last = i + 1 == n;
            if last {
                match &s.kind {
                    StmtKind::Expr(e) if value_used && !self.sub.shallow(exp).is("Unit") => {
                        result = Some(self.expr(e, exp)?);
                    }
                    StmtKind::Return(_) | StmtKind::Break | StmtKind::Continue => {
                        self.stmt(s)?;
                        result = Some(self.sub.fresh());
                    }
                    _ => self.stmt(s)?,
                }
            } else {
                self.stmt(s)?;
            }
        }
        self.scopes.pop();
        match result {
            Some(t) => Ok(t),
            None => {
                let sp = b.stmts.last().map(|s| s.span).unwrap_or(b.span);
                if !self.sub.unify(exp, &Ty::unit()) {
                    return err(sp, format!("this block must end with a value of type {}", self.sub.resolve(exp)));
                }
                Ok(Ty::unit())
            }
        }
    }

    fn stmt(&mut self, s: &Stmt) -> CResult<()> {
        match &s.kind {
            StmtKind::Expr(e) => {
                let t = self.sub.fresh();
                let t = self.expr(e, &t)?;
                let t = self.sub.resolve(&t);
                if !(t.is("Unit") || matches!(t, Ty::Var(_))) {
                    return err(e.span, format!(
                        "unused value of type {}; handle it, or discard explicitly with 'let _ = ...'",
                        t
                    ));
                }
                if let Ty::Var(_) = t {
                    self.sub.unify(&t, &Ty::unit());
                }
            }
            StmtKind::Let { pat, mutable, ty, value } => {
                let t = match ty {
                    Some(t) => self.lower_type(t, &self.tparams.clone())?,
                    None => self.sub.fresh(),
                };
                self.expr(value, &t)?;
                if !self.irrefutable(pat) {
                    return err(pat.span, "'let' needs a pattern that always matches; use 'match'");
                }
                self.pattern(pat, &t, *mutable)?;
            }
            StmtKind::Assign { target, op, value } => {
                let t = self.sub.fresh();
                let t = self.expr(target, &t)?;
                self.place(target, true)?;
                self.expr(value, &t)?;
                if let Some(op) = op {
                    let rt = self.known(&t, target.span, "this operand")?;
                    self.arith_ok(*op, &rt, s.span)?;
                }
            }
            StmtKind::While { cond, body } => {
                self.expr(cond, &Ty::bool())?;
                self.ctx.last_mut().unwrap().loops += 1;
                self.block(body, &Ty::unit(), false)?;
                self.ctx.last_mut().unwrap().loops -= 1;
            }
            StmtKind::For { pat, iter, body } => {
                self.scopes.push(vec![]);
                let elem = match iter {
                    ForIter::Range(a, b) => {
                        self.expr(a, &Ty::int())?;
                        self.expr(b, &Ty::int())?;
                        Ty::int()
                    }
                    ForIter::Each(e) => {
                        let t = self.sub.fresh();
                        let t = self.expr(e, &t)?;
                        let t = self.known(&t, e.span, "the loop source")?;
                        match &t {
                            Ty::Con(n, a) if n == "List" => a[0].clone(),
                            Ty::Con(n, a) if n == "Map" => Ty::Tuple(vec![a[0].clone(), a[1].clone()]),
                            _ => return err(e.span, format!("cannot iterate over {}; expected a List or Map", self.sub.resolve(&t))),
                        }
                    }
                };
                if !self.irrefutable(pat) {
                    return err(pat.span, "loop variables need a pattern that always matches");
                }
                self.pattern(pat, &elem, false)?;
                self.ctx.last_mut().unwrap().loops += 1;
                self.block(body, &Ty::unit(), false)?;
                self.ctx.last_mut().unwrap().loops -= 1;
                self.scopes.pop();
            }
            StmtKind::Return(v) => {
                let ret = self.ctx.last().unwrap().ret.clone();
                match v {
                    Some(e) => {
                        self.expr(e, &ret)?;
                    }
                    None => {
                        if !self.sub.unify(&ret, &Ty::unit()) {
                            return err(s.span, format!("'return' needs a value of type {}", self.sub.resolve(&ret)));
                        }
                    }
                }
            }
            StmtKind::Break | StmtKind::Continue => {
                if self.ctx.last().unwrap().loops == 0 {
                    return err(s.span, "'break'/'continue' outside of a loop");
                }
            }
        }
        Ok(())
    }

    fn irrefutable(&self, p: &Pattern) -> bool {
        match &p.kind {
            PatKind::Wild | PatKind::Bind(_) => true,
            PatKind::Tuple(ps) => ps.iter().all(|p| self.irrefutable(p)),
            _ => false,
        }
    }

    // Is `e` a place rooted in a `var` (or `mut self`)? Needed for mutation.
    fn place(&mut self, e: &Expr, assign: bool) -> CResult<()> {
        match &e.kind {
            ExprKind::Name(n) => {
                if n == "self" {
                    if self.self_mut && self.lambda_stack.is_empty() {
                        return Ok(());
                    }
                    return err(e.span, "cannot mutate 'self'; declare the method with 'mut self'");
                }
                match self.lookup(n) {
                    Some((_, l)) if l.mutable && l.depth == self.lambda_stack.len() => Ok(()),
                    Some((_, l)) if l.mutable => err(e.span, format!("'{}' is captured by a closure as a copy and cannot be mutated", n)),
                    Some(_) => err(e.span, format!("cannot mutate '{}'; declare it with 'var'", n)),
                    None => err(e.span, "this is not a mutable variable"),
                }
            }
            ExprKind::Field(b, _) | ExprKind::TupleField(b, _) => self.place(b, assign),
            ExprKind::Index(b, _) => self.place(b, assign),
            _ => err(e.span, if assign { "cannot assign to this expression" } else { "cannot mutate a temporary value; store it in a 'var' first" }),
        }
    }

    // ---- patterns ----

    fn pattern(&mut self, p: &Pattern, t: &Ty, mutable: bool) -> CResult<()> {
        self.record(p.id, t);
        match &p.kind {
            PatKind::Wild => {}
            PatKind::Bind(n) => self.bind(n, t.clone(), mutable, p.span)?,
            PatKind::Int(_) => self.unify_at(p.span, t, &Ty::int())?,
            PatKind::Str(_) => self.unify_at(p.span, t, &Ty::str())?,
            PatKind::Bool(_) => self.unify_at(p.span, t, &Ty::bool())?,
            PatKind::Tuple(ps) => {
                let ts: Vec<Ty> = ps.iter().map(|_| self.sub.fresh()).collect();
                self.unify_at(p.span, t, &Ty::Tuple(ts.clone()))?;
                for (p, t) in ps.iter().zip(&ts) {
                    self.pattern(p, t, mutable)?;
                }
            }
            PatKind::Variant(q, v, args) => {
                let st = self.known(t, p.span, "the matched value")?;
                let Ty::Con(tn, targs) = &st else {
                    return err(p.span, format!("pattern '{}' cannot match a value of type {}", v, self.sub.resolve(&st)));
                };
                let Some(ei) = self.out.enum_idx(tn) else {
                    return err(p.span, format!("pattern '{}' cannot match a value of type {}", v, self.sub.resolve(&st)));
                };
                if let Some(q) = q {
                    if self.resolve_type(q, p.span)? != *tn {
                        return err(p.span, format!("pattern is for '{}' but the value has type {}", q, tn));
                    }
                }
                let Some(vi) = self.out.enums[ei].variants.iter().position(|(n, _)| n == v) else {
                    return err(p.span, format!("'{}' has no variant '{}'", tn, v));
                };
                let m: HashMap<_, _> =
                    self.out.enums[ei].tparams.iter().cloned().zip(targs.iter().cloned()).collect();
                let fts: Vec<Ty> = self.out.enums[ei].variants[vi].1.iter().map(|t| t.subst(&m)).collect();
                if fts.len() != args.len() {
                    return err(p.span, format!("variant '{}' has {} field(s), pattern has {}", v, fts.len(), args.len()));
                }
                self.pending_res.push((p.id, Res::Variant(ei, vi, targs.clone())));
                for (a, ft) in args.iter().zip(&fts) {
                    self.pattern(a, ft, mutable)?;
                }
            }
            PatKind::Or(alts) => {
                let before = self.scopes.last().unwrap().len();
                self.pattern(&alts[0], t, mutable)?;
                let names: Vec<String> = self.scopes.last().unwrap()[before..].iter().map(|(n, _)| n.clone()).collect();
                for a in &alts[1..] {
                    let mut tmp = Vec::new();
                    std::mem::swap(&mut tmp, self.scopes.last_mut().unwrap());
                    self.scopes.last_mut().unwrap().extend(tmp[..before].iter().cloned());
                    self.pattern(a, t, mutable)?;
                    let got: Vec<(String, Local)> = self.scopes.last().unwrap()[before..].to_vec();
                    let mut gn: Vec<&String> = got.iter().map(|(n, _)| n).collect();
                    let mut en: Vec<&String> = names.iter().collect();
                    gn.sort();
                    en.sort();
                    if gn != en {
                        return err(a.span, "every alternative of '|' must bind the same names");
                    }
                    for (n, l) in &got {
                        let orig = tmp[before..].iter().find(|(m, _)| m == n).unwrap().1.ty.clone();
                        self.unify_at(a.span, &orig, &l.ty)?;
                    }
                    *self.scopes.last_mut().unwrap() = tmp;
                }
            }
        }
        Ok(())
    }

    // ---- expressions ----

    fn expr(&mut self, e: &Expr, exp: &Ty) -> CResult<Ty> {
        let t = self.expr_inner(e, exp)?;
        self.unify_at(e.span, exp, &t)?;
        self.record(e.id, &t);
        Ok(t)
    }

    fn arith_ok(&self, op: BinOp, t: &Ty, span: Span) -> CResult<()> {
        let ok = match op {
            BinOp::Add => t.is("Int") || t.is("Float") || t.is("Str") || t.is("List"),
            BinOp::Sub | BinOp::Mul | BinOp::Div | BinOp::Rem => t.is("Int") || t.is("Float"),
            _ => true,
        };
        if ok { Ok(()) } else { err(span, format!("operator {:?} is not defined for {}", op, self.sub.resolve(t))) }
    }

    fn comparable(&self, t: &Ty, span: Span) -> CResult<()> {
        let t = self.sub.resolve(t);
        if t.any(&|t| matches!(t, Ty::Fn(..)) || matches!(t, Ty::Con(n, _) if is_capability(n))) {
            return err(span, format!("values of type {} cannot be compared", t));
        }
        Ok(())
    }

    fn instantiate(&mut self, fi: usize) -> (Vec<Ty>, HashMap<String, Ty>) {
        let tps = self.out.fns[fi].tparams.clone();
        let targs: Vec<Ty> = tps.iter().map(|_| self.sub.fresh()).collect();
        let m = tps.into_iter().zip(targs.iter().cloned()).collect();
        (targs, m)
    }

    fn find_fn(&self, full: &str) -> Option<usize> {
        self.out.fns.iter().position(|f| f.name == full)
    }

    // A free function visible by its plain name: the current module's, else the prelude's.
    fn lookup_fn(&self, n: &str) -> Option<usize> {
        let own = self.internal(self.cur, n);
        self.find_fn(&own).or_else(|| self.find_fn(n).filter(|&i| self.out.fns[i].span.file == 0))
    }

    fn visible(&self, fi: usize, sp: Span) -> CResult<()> {
        let f = &self.out.fns[fi];
        if f.span.file != self.cur && f.span.file != 0 && !f.public {
            return err(sp, format!("'{}' is private to its module", f.name));
        }
        Ok(())
    }

    fn call_args(&mut self, span: Span, params: &[Ty], args: &[Expr], what: &str) -> CResult<()> {
        if params.len() != args.len() {
            return err(span, format!("{} expects {} argument(s), found {}", what, params.len(), args.len()));
        }
        for (a, p) in args.iter().zip(params) {
            self.expr(a, p)?;
        }
        Ok(())
    }

    fn variant_by_name(&self, v: &str, span: Span) -> CResult<Option<(usize, usize)>> {
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

    fn variant_value(&mut self, e: &Expr, callee_id: Id, ei: usize, vi: usize, args: Option<&[Expr]>) -> CResult<Ty> {
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

    fn expr_inner(&mut self, e: &Expr, exp: &Ty) -> CResult<Ty> {
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

    fn res_of(&self, id: Id) -> Option<&Res> {
        self.pending_res.iter().rev().find(|(i, _)| *i == id).map(|(_, r)| r)
    }

    fn method(&mut self, e: &Expr, recv: &Expr, m: &str, args: &[Expr]) -> CResult<Ty> {
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

    fn exhaustive(&mut self, span: Span, st: &Ty, arms: &[Arm]) -> CResult<()> {
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
