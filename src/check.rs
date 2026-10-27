// Checker: resolves names, infers and checks types, checks places and
// exhaustiveness. Output is the AST plus side tables (types, resolutions)
// shared by both backends.

use crate::ast::*;
use crate::diag::{Diag, Span};
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
    pub(crate) fn kind_walk(&self, t: &Ty, k: &mut Kind, seen: &mut Vec<Ty>) {
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
pub(crate) struct Local {
    pub(crate) ty: Ty,
    pub(crate) mutable: bool,
    pub(crate) depth: usize, // lambda nesting depth where defined
}

pub(crate) struct Ctx {
    pub(crate) ret: Ty,
    pub(crate) loops: usize,
    pub(crate) lambda: Option<Id>,
}

pub struct Checker {
    pub(crate) out: Checked,
    pub(crate) sub: Subst,
    pub(crate) scopes: Vec<Vec<(String, Local)>>,
    pub(crate) ctx: Vec<Ctx>,
    pub(crate) pending_types: Vec<(Id, Ty)>,
    pub(crate) pending_res: Vec<(Id, Res)>,
    pub(crate) lambda_stack: Vec<(Id, usize)>, // (lambda id, scope index where it starts)
    pub(crate) tparams: Vec<String>,
    pub(crate) self_mut: bool,
    pub(crate) cur: u16,                          // file (module) being checked
    pub(crate) modules: Vec<String>,              // module name per file
    pub(crate) imports: HashMap<u16, Vec<String>>, // modules imported by each file
}

pub(crate) type CResult<T> = Result<T, Diag>;

pub(crate) fn err<T>(span: Span, msg: impl AsRef<str>) -> CResult<T> {
    Err(Diag::new(span, msg.as_ref()))
}

// Type parameters are `T`, `K`, `V2`, ...; type names are longer, so the two never collide.
pub fn is_tparam_name(s: &str) -> bool {
    let b = s.as_bytes();
    !b.is_empty() && b[0].is_ascii_uppercase() && b[1..].iter().all(|c| c.is_ascii_digit())
}

// Does this block always leave (return, break, continue, or panic)?
fn leaves(b: &Block) -> bool {
    match b.stmts.last().map(|s| &s.kind) {
        Some(StmtKind::Return(_) | StmtKind::Break | StmtKind::Continue) => true,
        Some(StmtKind::Expr(Expr { kind: ExprKind::Call(f, _), .. })) => matches!(&f.kind, ExprKind::Name(n) if n == "panic"),
        Some(StmtKind::Expr(Expr { kind: ExprKind::Block(inner), .. })) => leaves(inner),
        _ => false,
    }
}

// Does this loop body contain a `break` for its own loop (not a nested one)?
fn breaks(stmts: &[Stmt]) -> bool {
    fn in_expr(e: &Expr) -> bool {
        let mut found = false;
        if let ExprKind::Block(b) = &e.kind {
            if breaks(&b.stmts) {
                return true;
            }
        }
        if let ExprKind::If(_, b, _) = &e.kind {
            if breaks(&b.stmts) {
                return true;
            }
        }
        if let ExprKind::Lambda(..) = &e.kind {
            return false;
        }
        crate::interp::visit_children(e, &mut |x| found = found || in_expr(x));
        found
    }
    stmts.iter().any(|s| match &s.kind {
        StmtKind::Break => true,
        StmtKind::While { .. } | StmtKind::For { .. } => false,
        _ => {
            let mut found = false;
            crate::interp::visit_stmt(s, &mut |x| found = found || in_expr(x));
            found
        }
    })
}

pub(crate) fn upper(s: &str) -> bool {
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
    pub(crate) fn fix(e: &mut Expr, types: &[String], aliases: &HashMap<u16, Vec<String>>) {
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
    pub(crate) fn internal(&self, file: u16, n: &str) -> String {
        match self.modules.get(file as usize) {
            Some(m) if !m.is_empty() => format!("{}.{}", m, n),
            _ => n.to_string(),
        }
    }

    pub(crate) fn imported(&self, m: &str) -> bool {
        self.imports.get(&self.cur).map(|v| v.iter().any(|x| x == m)).unwrap_or(false)
    }

    pub(crate) fn type_decl(&self, internal: &str) -> Option<(u16, bool)> {
        if let Some(s) = self.out.structs.iter().find(|s| s.name == internal) {
            return Some((s.file, s.public));
        }
        self.out.enums.iter().find(|e| e.name == internal).map(|e| (e.file, e.public))
    }

    // Resolve a type name as written in the current module to its internal name.
    pub(crate) fn resolve_type(&self, n: &str, sp: Span) -> CResult<String> {
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

    pub(crate) fn arity(&self, n: &str) -> Option<usize> {
        if let Some((_, a, _)) = BUILTIN_TYPES.iter().find(|(b, _, _)| *b == n) {
            return Some(*a);
        }
        if let Some(s) = self.out.structs.iter().find(|s| s.name == n) {
            return Some(s.tparams.len());
        }
        self.out.enums.iter().find(|e| e.name == n).map(|e| e.tparams.len())
    }

    pub(crate) fn lower_type(&self, t: &TypeExpr, params: &[String]) -> CResult<Ty> {
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

    pub(crate) fn declare(&mut self, prog: &Program) -> CResult<()> {
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
                return err(sp, format!("'{}' is reserved for type parameters (one capital letter, optional digits); use a longer type name", n0));
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
    pub(crate) fn check_recursion(&self) -> CResult<()> {
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

    pub(crate) fn check_main(&self, i: usize) -> CResult<()> {
        let f = &self.out.fns[i];
        if !f.tparams.is_empty() {
            return err(f.span, "'main' cannot be generic");
        }
        match f.params.as_slice() {
            [] => {}
            [(_, t)] if t.is("Sys") => {}
            _ => return err(f.span, "'main' takes no parameters or a single 'Sys'"),
        }
        let ok = f.ret.is("Unit") || f.ret.is("Int") || (f.ret.is("Result") && f.ret.args()[0].is("Unit"));
        if !ok {
            return err(f.span, "'main' returns Unit, Int (the exit status) or Result[Unit, E]");
        }
        Ok(())
    }

    // ---- functions ----

    pub(crate) fn check_fn(&mut self, f: &FnDecl, idx: usize) -> CResult<()> {
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

    pub(crate) fn flush(&mut self) {
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

    pub(crate) fn record(&mut self, id: Id, t: &Ty) {
        self.pending_types.push((id, t.clone()));
    }

    pub(crate) fn unify_at(&mut self, span: Span, expected: &Ty, found: &Ty) -> CResult<()> {
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

    pub(crate) fn known(&self, t: &Ty, span: Span, what: &str) -> CResult<Ty> {
        let t = self.sub.shallow(t);
        if let Ty::Var(_) = t {
            return err(span, format!("the type of {} must be known here; add a type annotation", what));
        }
        Ok(t)
    }

    // ---- scopes ----

    pub(crate) fn lookup(&self, n: &str) -> Option<(usize, &Local)> {
        for (i, s) in self.scopes.iter().enumerate().rev() {
            if let Some((_, l)) = s.iter().rev().find(|(m, _)| m == n) {
                return Some((i, l));
            }
        }
        None
    }

    pub(crate) fn bind(&mut self, n: &str, ty: Ty, mutable: bool, span: Span) -> CResult<()> {
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
    pub(crate) fn note_use(&mut self, n: &str, scope_idx: usize, ty: &Ty) {
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
    pub(crate) fn block(&mut self, b: &Block, exp: &Ty, value_used: bool) -> CResult<Ty> {
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
                    // `while true` without a `break` never finishes: it needs no value after it.
                    StmtKind::While { cond: Expr { kind: ExprKind::Bool(true), .. }, body } if !breaks(&body.stmts) => {
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

    pub(crate) fn stmt(&mut self, s: &Stmt) -> CResult<()> {
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
            StmtKind::Let { pat, mutable, ty, value, els } => {
                let t = match ty {
                    Some(t) => self.lower_type(t, &self.tparams.clone())?,
                    None => self.sub.fresh(),
                };
                self.expr(value, &t)?;
                match els {
                    None if !self.irrefutable(pat) => {
                        return err(pat.span, "'let' needs a pattern that always matches; use 'let ... else' or 'match'");
                    }
                    Some(b) => {
                        if matches!(pat.kind, PatKind::Or(_)) {
                            return err(pat.span, "'let ... else' cannot use '|' patterns; use 'match'");
                        }
                        if !leaves(b) {
                            return err(b.span, "the 'else' block of 'let ... else' must leave: end it with return, break, continue or panic");
                        }
                        // Checked before the pattern binds: the else block cannot see its names.
                        self.block(b, &Ty::unit(), false)?;
                    }
                    None => {}
                }
                self.pattern(pat, &t, *mutable)?;
                if els.is_some() {
                    let rt = self.sub.resolve(&t);
                    self.exhaustive_or_refutable(pat, &rt)?;
                }
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

    pub(crate) fn irrefutable(&self, p: &Pattern) -> bool {
        match &p.kind {
            PatKind::Wild | PatKind::Bind(_) => true,
            PatKind::Tuple(ps) => ps.iter().all(|p| self.irrefutable(p)),
            _ => false,
        }
    }

    // Is `e` a place rooted in a `var` (or `mut self`)? Needed for mutation.
    pub(crate) fn place(&mut self, e: &Expr, assign: bool) -> CResult<()> {
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

    pub(crate) fn pattern(&mut self, p: &Pattern, t: &Ty, mutable: bool) -> CResult<()> {
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






    pub(crate) fn find_fn(&self, full: &str) -> Option<usize> {
        self.out.fns.iter().position(|f| f.name == full)
    }

    // A free function visible by its plain name: the current module's, else the prelude's.
    pub(crate) fn lookup_fn(&self, n: &str) -> Option<usize> {
        let own = self.internal(self.cur, n);
        self.find_fn(&own).or_else(|| self.find_fn(n).filter(|&i| self.out.fns[i].span.file == 0))
    }

    pub(crate) fn visible(&self, fi: usize, sp: Span) -> CResult<()> {
        let f = &self.out.fns[fi];
        if f.span.file != self.cur && f.span.file != 0 && !f.public {
            return err(sp, format!("'{}' is private to its module", f.name));
        }
        Ok(())
    }







}
