// Parser: tokens -> AST (recursive descent, precedence climbing for binaries).

use crate::ast::*;
use crate::diag::{Diag, Span};
use crate::lexer::{StrPart, Tok, Token};

pub struct Parser<'a> {
    toks: &'a [Token],
    pos: usize,
    next_id: &'a mut Id,
    no_struct: bool, // inside `if`/`while`/`match`/`for` heads
}

type PResult<T> = Result<T, Diag>;

pub fn parse_program(toks: &[Token], next_id: &mut Id, prog: &mut Program) -> PResult<()> {
    let mut p = Parser { toks, pos: 0, next_id, no_struct: false };
    p.skip_semis();
    while !p.at_eof() {
        p.item(prog)?;
        p.skip_semis();
    }
    Ok(())
}

impl<'a> Parser<'a> {
    fn peek(&self) -> &Tok {
        &self.toks[self.pos].tok
    }
    fn peek_at(&self, n: usize) -> &Tok {
        &self.toks[(self.pos + n).min(self.toks.len() - 1)].tok
    }
    fn span(&self) -> Span {
        self.toks[self.pos].span
    }
    fn at_eof(&self) -> bool {
        matches!(self.peek(), Tok::Eof)
    }
    fn advance(&mut self) -> &Token {
        let t = &self.toks[self.pos];
        if self.pos < self.toks.len() - 1 {
            self.pos += 1;
        }
        t
    }
    fn is_sym(&self, s: &str) -> bool {
        matches!(self.peek(), Tok::Sym(x) if *x == s)
    }
    fn is_kw(&self, s: &str) -> bool {
        matches!(self.peek(), Tok::Kw(x) if *x == s)
    }
    fn eat_sym(&mut self, s: &str) -> bool {
        if self.is_sym(s) {
            self.advance();
            true
        } else {
            false
        }
    }
    fn eat_kw(&mut self, s: &str) -> bool {
        if self.is_kw(s) {
            self.advance();
            true
        } else {
            false
        }
    }
    fn describe(t: &Tok) -> String {
        match t {
            Tok::Ident(s) => format!("'{}'", s),
            Tok::Kw(k) => format!("'{}'", k),
            Tok::Sym(";") => "end of statement".to_string(),
            Tok::Sym(s) => format!("'{}'", s),
            Tok::Int(i) => format!("'{}'", i),
            Tok::Float(f) => format!("'{}'", crate::value::fmt_float(*f)),
            Tok::Str(_) => "string".to_string(),
            Tok::Eof => "end of file".to_string(),
        }
    }
    fn err<T>(&self, what: &str) -> PResult<T> {
        Err(Diag::new(self.span(), &format!("expected {}, found {}", what, Self::describe(self.peek()))))
    }
    fn expect_sym(&mut self, s: &str) -> PResult<()> {
        if self.eat_sym(s) { Ok(()) } else { self.err(&format!("'{}'", s)) }
    }
    fn ident(&mut self) -> PResult<String> {
        match self.peek().clone() {
            Tok::Ident(s) => {
                self.advance();
                Ok(s)
            }
            _ => self.err("a name"),
        }
    }
    fn skip_semis(&mut self) {
        while self.eat_sym(";") {}
    }
    fn skip_seps(&mut self) {
        while self.eat_sym(";") || self.eat_sym(",") {}
    }
    fn id(&mut self) -> Id {
        let i = *self.next_id;
        *self.next_id += 1;
        i
    }
    fn mk(&mut self, span: Span, kind: ExprKind) -> Expr {
        Expr { id: self.id(), span, kind }
    }

    // ---- items ----

    fn item(&mut self, prog: &mut Program) -> PResult<()> {
        if self.is_kw("import") {
            let span = self.span();
            self.advance();
            let name = self.ident()?;
            prog.imports.push(Import { file: span.file, name, span });
            return Ok(());
        }
        let public = self.eat_kw("pub");
        let kind = if self.eat_kw("linear") {
            Kind::Linear
        } else if self.eat_kw("unique") {
            Kind::Unique
        } else {
            Kind::Plain
        };
        if self.is_kw("struct") {
            let mut d = self.struct_decl(kind)?;
            d.public = public;
            prog.structs.push(d);
        } else if self.is_kw("enum") {
            let mut d = self.enum_decl(kind)?;
            d.public = public;
            prog.enums.push(d);
        } else if self.is_kw("fn") && kind == Kind::Plain {
            let mut d = self.fn_decl(false)?;
            d.public = public;
            prog.fns.push(d);
        } else if self.is_kw("const") && kind == Kind::Plain {
            let span = self.span();
            self.advance();
            let name = self.ident()?;
            self.expect_sym(":")?;
            let ret = self.type_expr()?;
            self.expect_sym("=")?;
            let bspan = self.span();
            let value = self.expr()?;
            let body = Block { stmts: vec![Stmt { kind: StmtKind::Expr(value), span: bspan }], span: bspan };
            prog.fns.push(FnDecl {
                name, owner: None, tparams: vec![], self_kind: None, params: vec![], ret: Some(ret),
                body: Some(body), public, is_const: true, span,
            });
        } else if self.is_kw("extern") && kind == Kind::Plain {
            self.advance();
            if !self.is_kw("fn") {
                return self.err("'fn'");
            }
            prog.fns.push(self.fn_decl(true)?);
        } else {
            return self.err("'fn', 'const', 'struct' or 'enum'");
        }
        Ok(())
    }

    fn tparams(&mut self) -> PResult<Vec<String>> {
        let mut v = Vec::new();
        if self.eat_sym("[") {
            while !self.eat_sym("]") {
                v.push(self.ident()?);
                if !self.is_sym("]") {
                    self.expect_sym(",")?;
                }
            }
        }
        Ok(v)
    }

    fn struct_decl(&mut self, kind: Kind) -> PResult<StructDecl> {
        let span = self.span();
        self.advance();
        let name = self.ident()?;
        let tparams = self.tparams()?;
        self.expect_sym("{")?;
        let mut fields = Vec::new();
        let mut pub_fields = Vec::new();
        self.skip_seps();
        while !self.eat_sym("}") {
            pub_fields.push(self.eat_kw("pub"));
            let f = self.ident()?;
            self.expect_sym(":")?;
            let t = self.type_expr()?;
            fields.push((f, t));
            if !self.is_sym("}") && !self.is_sym(",") && !self.is_sym(";") {
                return self.err("',' or '}'");
            }
            self.skip_seps();
        }
        Ok(StructDecl { name, tparams, fields, pub_fields, kind, public: false, span })
    }

    fn enum_decl(&mut self, kind: Kind) -> PResult<EnumDecl> {
        let span = self.span();
        self.advance();
        let name = self.ident()?;
        let tparams = self.tparams()?;
        self.expect_sym("{")?;
        let mut variants = Vec::new();
        self.skip_seps();
        while !self.eat_sym("}") {
            let vspan = self.span();
            let vname = self.ident()?;
            let mut fields = Vec::new();
            if self.eat_sym("(") {
                while !self.eat_sym(")") {
                    fields.push(self.type_expr()?);
                    if !self.is_sym(")") {
                        self.expect_sym(",")?;
                    }
                }
            }
            variants.push(VariantDecl { name: vname, fields, span: vspan });
            if !self.is_sym("}") && !self.is_sym(",") && !self.is_sym(";") {
                return self.err("',' or '}'");
            }
            self.skip_seps();
        }
        Ok(EnumDecl { name, tparams, variants, kind, public: false, span })
    }

    fn fn_decl(&mut self, is_extern: bool) -> PResult<FnDecl> {
        let span = self.span();
        self.advance();
        let first_span = self.span();
        let first = self.ident()?;
        let (owner, name, tparams) = if self.is_sym("[") && self.owner_follows() {
            self.advance();
            let mut args = Vec::new();
            while !self.eat_sym("]") {
                args.push(self.type_expr()?);
                if !self.is_sym("]") {
                    self.expect_sym(",")?;
                }
            }
            self.expect_sym(".")?;
            let n = self.ident()?;
            let own = TypeExpr { kind: TypeExprKind::Named(first, args), span: first_span };
            (Some(own), n, self.tparams()?)
        } else if self.eat_sym(".") {
            let n = self.ident()?;
            if self.is_sym(".") {
                return Err(Diag::new(first_span, "methods can only be defined in the module that defines the type"));
            }
            let own = TypeExpr { kind: TypeExprKind::Named(first, vec![]), span: first_span };
            (Some(own), n, self.tparams()?)
        } else {
            (None, first, self.tparams()?)
        };
        self.expect_sym("(")?;
        let mut self_kind = None;
        let mut params = Vec::new();
        if owner.is_some() {
            if self.is_kw("mut") && matches!(self.peek_at(1), Tok::Kw("self")) {
                self.advance();
                self.advance();
                self_kind = Some(SelfKind::Mut);
            } else if self.eat_kw("self") {
                self_kind = Some(SelfKind::Value);
            }
            if self_kind.is_some() && !self.is_sym(")") {
                self.expect_sym(",")?;
            }
        }
        while !self.eat_sym(")") {
            let pspan = self.span();
            let pname = self.ident()?;
            self.expect_sym(":")?;
            let by_ref = self.eat_kw("ref");
            let ty = self.type_expr()?;
            params.push(Param { name: pname, by_ref, ty, span: pspan });
            if !self.is_sym(")") {
                self.expect_sym(",")?;
            }
        }
        let ret = if self.eat_sym("->") { Some(self.type_expr()?) } else { None };
        let body = if is_extern { None } else { Some(self.block()?) };
        Ok(FnDecl { name, owner, tparams, self_kind, params, ret, body, public: false, is_const: false, span })
    }

    // After `fn Name`, is `[...]` followed by `.`? (owner type args vs fn type params)
    fn owner_follows(&self) -> bool {
        let mut depth = 0;
        let mut i = self.pos;
        loop {
            match &self.toks[i].tok {
                Tok::Sym("[") => depth += 1,
                Tok::Sym("]") => {
                    depth -= 1;
                    if depth == 0 {
                        return matches!(self.toks.get(i + 1).map(|t| &t.tok), Some(Tok::Sym(".")));
                    }
                }
                Tok::Eof => return false,
                _ => {}
            }
            i += 1;
        }
    }

    fn type_expr(&mut self) -> PResult<TypeExpr> {
        let span = self.span();
        if self.eat_kw("fn") {
            self.expect_sym("(")?;
            let mut args = Vec::new();
            while !self.eat_sym(")") {
                args.push(self.type_expr()?);
                if !self.is_sym(")") {
                    self.expect_sym(",")?;
                }
            }
            let ret = if self.eat_sym("->") {
                self.type_expr()?
            } else {
                TypeExpr { kind: TypeExprKind::Named("Unit".into(), vec![]), span }
            };
            return Ok(TypeExpr { kind: TypeExprKind::Fn(args, Box::new(ret)), span });
        }
        if self.eat_sym("(") {
            let mut elems = Vec::new();
            while !self.eat_sym(")") {
                elems.push(self.type_expr()?);
                if !self.is_sym(")") {
                    self.expect_sym(",")?;
                }
            }
            if elems.is_empty() {
                return Ok(TypeExpr { kind: TypeExprKind::Named("Unit".into(), vec![]), span });
            }
            if elems.len() == 1 {
                return Ok(elems.pop().unwrap());
            }
            return Ok(TypeExpr { kind: TypeExprKind::Tuple(elems), span });
        }
        let mut name = self.ident()?;
        if self.is_sym(".") {
            if let Tok::Ident(t) = self.peek_at(1).clone() {
                self.advance();
                self.advance();
                name = format!("{}.{}", name, t);
            }
        }
        let mut args = Vec::new();
        if self.eat_sym("[") {
            while !self.eat_sym("]") {
                args.push(self.type_expr()?);
                if !self.is_sym("]") {
                    self.expect_sym(",")?;
                }
            }
        }
        Ok(TypeExpr { kind: TypeExprKind::Named(name, args), span })
    }

    // ---- statements ----

    pub fn block(&mut self) -> PResult<Block> {
        let span = self.span();
        let save = self.no_struct;
        self.no_struct = false;
        self.expect_sym("{")?;
        let mut stmts = Vec::new();
        self.skip_semis();
        while !self.eat_sym("}") {
            if self.at_eof() {
                return self.err("'}'");
            }
            stmts.push(self.stmt()?);
            if !self.is_sym("}") && !self.eat_sym(";") {
                return self.err("end of statement");
            }
            self.skip_semis();
        }
        self.no_struct = save;
        Ok(Block { stmts, span })
    }

    pub fn stmt(&mut self) -> PResult<Stmt> {
        let span = self.span();
        let kind = if self.is_kw("let") || self.is_kw("var") {
            let mutable = self.is_kw("var");
            self.advance();
            let pat = self.pattern()?;
            let ty = if self.eat_sym(":") { Some(self.type_expr()?) } else { None };
            self.expect_sym("=")?;
            let value = self.expr()?;
            let els = if self.eat_kw("else") { Some(self.block()?) } else { None };
            StmtKind::Let { pat, mutable, ty, value, els }
        } else if self.eat_kw("while") {
            let cond = self.head_expr()?;
            let body = self.block()?;
            StmtKind::While { cond, body }
        } else if self.eat_kw("for") {
            let pat = self.pattern()?;
            if !self.eat_kw("in") {
                return self.err("'in'");
            }
            let a = self.head_expr()?;
            let iter = if self.eat_sym("..") {
                ForIter::Range(a, self.head_expr()?)
            } else {
                ForIter::Each(a)
            };
            let body = self.block()?;
            StmtKind::For { pat, iter, body }
        } else if self.eat_kw("return") {
            if self.is_sym(";") || self.is_sym("}") {
                StmtKind::Return(None)
            } else {
                StmtKind::Return(Some(self.expr()?))
            }
        } else if self.eat_kw("break") {
            StmtKind::Break
        } else if self.eat_kw("continue") {
            StmtKind::Continue
        } else {
            let e = self.expr()?;
            let op = match self.peek() {
                Tok::Sym("=") => Some(None),
                Tok::Sym("+=") => Some(Some(BinOp::Add)),
                Tok::Sym("-=") => Some(Some(BinOp::Sub)),
                Tok::Sym("*=") => Some(Some(BinOp::Mul)),
                Tok::Sym("/=") => Some(Some(BinOp::Div)),
                Tok::Sym("%=") => Some(Some(BinOp::Rem)),
                _ => None,
            };
            match op {
                Some(op) => {
                    self.advance();
                    let value = self.expr()?;
                    StmtKind::Assign { target: e, op, value }
                }
                None => StmtKind::Expr(e),
            }
        };
        Ok(Stmt { kind, span })
    }

    fn head_expr(&mut self) -> PResult<Expr> {
        let save = self.no_struct;
        self.no_struct = true;
        let e = self.expr();
        self.no_struct = save;
        e
    }

    // ---- patterns ----

    fn pattern(&mut self) -> PResult<Pattern> {
        let first = self.pattern1()?;
        if !self.is_sym("|") {
            return Ok(first);
        }
        let span = first.span;
        let mut alts = vec![first];
        while self.eat_sym("|") {
            alts.push(self.pattern1()?);
        }
        Ok(Pattern { id: self.id(), span, kind: PatKind::Or(alts) })
    }

    fn pattern1(&mut self) -> PResult<Pattern> {
        let span = self.span();
        let kind = match self.peek().clone() {
            Tok::Sym("_") => {
                self.advance();
                PatKind::Wild
            }
            Tok::Int(i) => {
                self.advance();
                PatKind::Int(i)
            }
            Tok::Sym("-") => {
                self.advance();
                match self.peek().clone() {
                    Tok::Int(i) => {
                        self.advance();
                        PatKind::Int(-i)
                    }
                    _ => return self.err("integer"),
                }
            }
            Tok::Kw("true") => {
                self.advance();
                PatKind::Bool(true)
            }
            Tok::Kw("false") => {
                self.advance();
                PatKind::Bool(false)
            }
            Tok::Str(parts) => {
                self.advance();
                match parts.as_slice() {
                    [StrPart::Lit(s)] => PatKind::Str(s.clone()),
                    _ => return Err(Diag::new(span, "string patterns cannot interpolate")),
                }
            }
            Tok::Sym("(") => {
                self.advance();
                let mut elems = Vec::new();
                while !self.eat_sym(")") {
                    elems.push(self.pattern()?);
                    if !self.is_sym(")") {
                        self.expect_sym(",")?;
                    }
                }
                if elems.len() == 1 {
                    return Ok(elems.pop().unwrap());
                }
                PatKind::Tuple(elems)
            }
            Tok::Ident(name) => {
                self.advance();
                let starts_upper = name.chars().next().unwrap().is_ascii_uppercase();
                if !starts_upper {
                    PatKind::Bind(name)
                } else {
                    let (qual, vname) = if self.eat_sym(".") {
                        (Some(name), self.ident()?)
                    } else {
                        (None, name)
                    };
                    let mut args = Vec::new();
                    if self.eat_sym("(") {
                        while !self.eat_sym(")") {
                            args.push(self.pattern()?);
                            if !self.is_sym(")") {
                                self.expect_sym(",")?;
                            }
                        }
                    }
                    PatKind::Variant(qual, vname, args)
                }
            }
            _ => return self.err("a pattern"),
        };
        Ok(Pattern { id: self.id(), span, kind })
    }

    // ---- expressions ----

    pub fn expr(&mut self) -> PResult<Expr> {
        self.binary(0)
    }

    fn binop(&self) -> Option<(BinOp, u8)> {
        let op = match self.peek() {
            Tok::Kw("or") => (BinOp::Or, 1),
            Tok::Kw("and") => (BinOp::And, 2),
            Tok::Sym("==") => (BinOp::Eq, 3),
            Tok::Sym("!=") => (BinOp::Ne, 3),
            Tok::Sym("<") => (BinOp::Lt, 3),
            Tok::Sym("<=") => (BinOp::Le, 3),
            Tok::Sym(">") => (BinOp::Gt, 3),
            Tok::Sym(">=") => (BinOp::Ge, 3),
            Tok::Sym("+") => (BinOp::Add, 4),
            Tok::Sym("-") => (BinOp::Sub, 4),
            Tok::Sym("*") => (BinOp::Mul, 5),
            Tok::Sym("/") => (BinOp::Div, 5),
            Tok::Sym("%") => (BinOp::Rem, 5),
            _ => return None,
        };
        Some(op)
    }

    fn binary(&mut self, min: u8) -> PResult<Expr> {
        let mut lhs = self.unary()?;
        while let Some((op, prec)) = self.binop() {
            if prec < min {
                break;
            }
            let span = self.span();
            self.advance();
            let rhs = self.binary(prec + 1)?;
            if prec == 3 && self.binop().map(|(_, p)| p == 3).unwrap_or(false) {
                return Err(Diag::new(self.span(), "comparisons cannot be chained; use 'and'"));
            }
            lhs = self.mk(span, ExprKind::Binary(op, Box::new(lhs), Box::new(rhs)));
        }
        Ok(lhs)
    }

    fn unary(&mut self) -> PResult<Expr> {
        let span = self.span();
        if self.is_sym("-") && matches!(self.peek_at(1), Tok::Int(_) | Tok::Float(_)) {
            // A negative literal binds tighter than postfix: `-2.abs()` is `(-2).abs()`.
            self.advance();
            let lit = match self.peek().clone() {
                Tok::Int(i) => ExprKind::Int(i.wrapping_neg()),
                Tok::Float(f) => ExprKind::Float(-f),
                _ => unreachable!(),
            };
            self.advance();
            let e = self.mk(span, lit);
            return self.postfix_from(e);
        }
        if self.eat_sym("-") {
            let e = self.unary()?;
            if let ExprKind::Int(i) = e.kind {
                return Ok(self.mk(span, ExprKind::Int(i.wrapping_neg())));
            }
            if let ExprKind::Float(f) = e.kind {
                return Ok(self.mk(span, ExprKind::Float(-f)));
            }
            return Ok(self.mk(span, ExprKind::Unary(UnOp::Neg, Box::new(e))));
        }
        if self.eat_kw("not") {
            let e = self.unary()?;
            return Ok(self.mk(span, ExprKind::Unary(UnOp::Not, Box::new(e))));
        }
        self.postfix()
    }

    fn args(&mut self, close: &str) -> PResult<Vec<Expr>> {
        let save = self.no_struct;
        self.no_struct = false;
        let mut args = Vec::new();
        while !self.eat_sym(close) {
            args.push(self.expr()?);
            if !self.is_sym(close) {
                self.expect_sym(",")?;
            }
        }
        self.no_struct = save;
        Ok(args)
    }

    fn postfix(&mut self) -> PResult<Expr> {
        let e = self.primary()?;
        self.postfix_from(e)
    }

    fn postfix_from(&mut self, mut e: Expr) -> PResult<Expr> {
        loop {
            let span = self.span();
            if self.eat_sym("(") {
                let args = self.args(")")?;
                e = self.mk(span, ExprKind::Call(Box::new(e), args));
            } else if self.eat_sym("[") {
                let save = self.no_struct;
                self.no_struct = false;
                let i = self.expr()?;
                self.no_struct = save;
                self.expect_sym("]")?;
                e = self.mk(span, ExprKind::Index(Box::new(e), Box::new(i)));
            } else if self.eat_sym("?") {
                e = self.mk(span, ExprKind::Try(Box::new(e)));
            } else if self.eat_sym(".") {
                if let Tok::Int(i) = self.peek().clone() {
                    self.advance();
                    e = self.mk(span, ExprKind::TupleField(Box::new(e), i as usize));
                    continue;
                }
                let name = self.ident()?;
                if self.eat_sym("(") {
                    let args = self.args(")")?;
                    e = self.mk(span, ExprKind::Method(Box::new(e), name, args));
                } else {
                    e = self.mk(span, ExprKind::Field(Box::new(e), name));
                }
            } else {
                return Ok(e);
            }
        }
    }

    fn primary(&mut self) -> PResult<Expr> {
        let span = self.span();
        match self.peek().clone() {
            Tok::Int(i) => {
                self.advance();
                Ok(self.mk(span, ExprKind::Int(i)))
            }
            Tok::Float(f) => {
                self.advance();
                Ok(self.mk(span, ExprKind::Float(f)))
            }
            Tok::Kw("true") => {
                self.advance();
                Ok(self.mk(span, ExprKind::Bool(true)))
            }
            Tok::Kw("false") => {
                self.advance();
                Ok(self.mk(span, ExprKind::Bool(false)))
            }
            Tok::Kw("self") => {
                self.advance();
                Ok(self.mk(span, ExprKind::Name("self".into())))
            }
            Tok::Str(parts) => {
                self.advance();
                let mut segs = Vec::new();
                for p in parts {
                    match p {
                        StrPart::Lit(s) => segs.push(StrSeg::Lit(s)),
                        StrPart::Expr(toks) => {
                            let mut sub = Parser { toks: &toks, pos: 0, next_id: &mut *self.next_id, no_struct: false };
                            let e = sub.expr()?;
                            if !sub.at_eof() {
                                return sub.err("'}' to close interpolation");
                            }
                            segs.push(StrSeg::Expr(e));
                        }
                    }
                }
                Ok(self.mk(span, ExprKind::Str(segs)))
            }
            Tok::Sym("(") => {
                self.advance();
                let mut elems = self.args(")")?;
                if elems.is_empty() {
                    return Ok(self.mk(span, ExprKind::Unit));
                }
                if elems.len() == 1 {
                    return Ok(elems.pop().unwrap());
                }
                Ok(self.mk(span, ExprKind::Tuple(elems)))
            }
            Tok::Sym("[") => {
                self.advance();
                if self.eat_sym(":") {
                    self.expect_sym("]")?;
                    return Ok(self.mk(span, ExprKind::MapLit(vec![])));
                }
                if self.eat_sym("]") {
                    return Ok(self.mk(span, ExprKind::List(vec![])));
                }
                let save = self.no_struct;
                self.no_struct = false;
                let first = self.expr()?;
                let r = if self.eat_sym(":") {
                    let v = self.expr()?;
                    let mut pairs = vec![(first, v)];
                    while self.eat_sym(",") {
                        if self.is_sym("]") {
                            break;
                        }
                        let k = self.expr()?;
                        self.expect_sym(":")?;
                        pairs.push((k, self.expr()?));
                    }
                    self.expect_sym("]")?;
                    ExprKind::MapLit(pairs)
                } else {
                    let mut elems = vec![first];
                    while self.eat_sym(",") {
                        if self.is_sym("]") {
                            break;
                        }
                        elems.push(self.expr()?);
                    }
                    self.expect_sym("]")?;
                    ExprKind::List(elems)
                };
                self.no_struct = save;
                Ok(self.mk(span, r))
            }
            Tok::Sym("{") => {
                let b = self.block()?;
                Ok(self.mk(span, ExprKind::Block(b)))
            }
            Tok::Kw("if") => self.if_expr(),
            // `return`/`break`/`continue` in expression position, e.g. a match arm
            Tok::Kw("return") | Tok::Kw("break") | Tok::Kw("continue") => {
                let st = self.stmt()?;
                Ok(self.mk(span, ExprKind::Block(Block { stmts: vec![st], span })))
            }
            Tok::Kw("match") => {
                self.advance();
                let scrut = self.head_expr()?;
                self.expect_sym("{")?;
                let save = self.no_struct;
                self.no_struct = false;
                let mut arms = Vec::new();
                self.skip_seps();
                while !self.eat_sym("}") {
                    let pat = self.pattern()?;
                    let guard = if self.eat_kw("if") { Some(self.expr()?) } else { None };
                    self.expect_sym("=>")?;
                    // An arm body is an expression or an assignment (`None => n += 1`).
                    let bspan = self.span();
                    let st = self.stmt()?;
                    let body = match st.kind {
                        StmtKind::Expr(e) => e,
                        _ => self.mk(bspan, ExprKind::Block(Block { stmts: vec![st], span: bspan })),
                    };
                    arms.push(Arm { pat, guard, body });
                    if !self.is_sym("}") && !self.is_sym(",") && !self.is_sym(";") {
                        return self.err("',' or '}' after match arm");
                    }
                    self.skip_seps();
                }
                self.no_struct = save;
                Ok(self.mk(span, ExprKind::Match(Box::new(scrut), arms)))
            }
            Tok::Kw("fn") => {
                self.advance();
                self.expect_sym("(")?;
                let mut params = Vec::new();
                while !self.eat_sym(")") {
                    let n = if self.eat_sym("_") { "_".to_string() } else { self.ident()? };
                    let t = if self.eat_sym(":") { Some(self.type_expr()?) } else { None };
                    params.push((n, t));
                    if !self.is_sym(")") {
                        self.expect_sym(",")?;
                    }
                }
                let ret = if self.eat_sym("->") { Some(self.type_expr()?) } else { None };
                let body = if self.eat_sym("=>") {
                    let save = self.no_struct;
                    self.no_struct = false;
                    let e = self.expr()?;
                    self.no_struct = save;
                    e
                } else {
                    let bspan = self.span();
                    let b = self.block()?;
                    self.mk(bspan, ExprKind::Block(b))
                };
                Ok(self.mk(span, ExprKind::Lambda(params, ret, Box::new(body))))
            }
            Tok::Ident(name) => {
                self.advance();
                let upper = name.chars().next().unwrap().is_ascii_uppercase();
                if upper && self.is_sym(".") {
                    if let Tok::Ident(m) = self.peek_at(1).clone() {
                        self.advance();
                        self.advance();
                        return Ok(self.mk(span, ExprKind::Path(name, m)));
                    }
                }
                if upper && !self.no_struct && self.is_sym("{") {
                    return self.struct_lit(span, name);
                }
                // module.Type { ... }
                if !upper && !self.no_struct && self.is_sym(".") && matches!(self.peek_at(2), Tok::Sym("{")) {
                    if let Tok::Ident(t) = self.peek_at(1).clone() {
                        if t.chars().next().unwrap().is_ascii_uppercase() {
                            self.advance();
                            self.advance();
                            return self.struct_lit(span, format!("{}.{}", name, t));
                        }
                    }
                }
                Ok(self.mk(span, ExprKind::Name(name)))
            }
            _ => self.err("an expression"),
        }
    }

    fn struct_lit(&mut self, span: Span, name: String) -> PResult<Expr> {
        self.expect_sym("{")?;
        let mut fields = Vec::new();
        let mut base = None;
        self.skip_seps();
        while !self.eat_sym("}") {
            if self.eat_sym("..") {
                base = Some(Box::new(self.expr()?));
                self.skip_seps();
                self.expect_sym("}")?;
                break;
            }
            let fspan = self.span();
            let f = self.ident()?;
            let v = if self.eat_sym(":") { self.expr()? } else { self.mk(fspan, ExprKind::Name(f.clone())) };
            fields.push((f, v));
            if !self.is_sym("}") && !self.is_sym(",") && !self.is_sym(";") {
                return self.err("',' or '}'");
            }
            self.skip_seps();
        }
        Ok(self.mk(span, ExprKind::StructLit(name, fields, base)))
    }

    fn if_expr(&mut self) -> PResult<Expr> {
        let span = self.span();
        self.advance(); // if
        let cond = self.head_expr()?;
        let then = self.block()?;
        let els = if self.eat_kw("else") {
            if self.is_kw("if") {
                Some(Box::new(self.if_expr()?))
            } else {
                let bspan = self.span();
                let b = self.block()?;
                Some(Box::new(self.mk(bspan, ExprKind::Block(b))))
            }
        } else {
            None
        };
        Ok(self.mk(span, ExprKind::If(Box::new(cond), then, els)))
    }
}
