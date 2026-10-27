// calc: tokenizer, recursive-descent parser, tree-walking evaluator (plain C11).
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DEPTH 1000
#define MAX_NESTING 200

typedef enum {
    KNum, KIdent, KLet, KFn, KIf, KThen, KElse,
    KPlus, KMinus, KStar, KSlash, KPercent,
    KLParen, KRParen, KComma, KAssign,
    KEqEq, KNotEq, KLess, KLessEq, KGreater, KGreaterEq,
    KEnd
} Kind;

typedef struct { Kind kind; const char *text; int len; int64_t num; int col; } Token;

typedef enum { Add, Sub, Mul, Div, Mod, Eq, Ne, Lt, Le, Gt, Ge } Op;
typedef enum { ENum, EVar, ENeg, EBin, EIf, ECall } ExprTag;

typedef struct Expr {
    ExprTag tag;
    int64_t num;            // ENum
    char *name;             // EVar, ECall
    Op op;                  // EBin
    struct Expr *a, *b, *c; // ENeg/EBin/EIf operands
    struct Expr **args;     // ECall
    int nargs;
} Expr;

typedef struct { char **params; int nparams; Expr *body; } FnDef;

typedef enum { SDefVar, SDefFn, SShow } StmtTag;
typedef struct { StmtTag tag; char *name; char **params; int nparams; Expr *expr; } Stmt;

static char err[1024];
static bool fail(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#include <stdarg.h>
static bool fail(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(err, sizeof err, fmt, ap);
    va_end(ap);
    return false;
}

// ---- tokens ----

static bool is_digit(int c) { return c >= '0' && c <= '9'; }
static bool is_ident_start(int c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; }
static bool is_ident_char(int c) { return is_ident_start(c) || is_digit(c); }

static int utf8_len(int c) { return c >= 240 ? 4 : c >= 224 ? 3 : c >= 192 ? 2 : 1; }

static Kind keyword(const char *w, int n) {
    if (n == 3 && !memcmp(w, "let", 3)) return KLet;
    if (n == 2 && !memcmp(w, "fn", 2)) return KFn;
    if (n == 2 && !memcmp(w, "if", 2)) return KIf;
    if (n == 4 && !memcmp(w, "then", 4)) return KThen;
    if (n == 4 && !memcmp(w, "else", 4)) return KElse;
    return KIdent;
}

typedef struct { Token *v; int len, cap; } Tokens;

static void push_tok(Tokens *t, Kind kind, const char *text, int len, int64_t num, int col) {
    if (t->len == t->cap) {
        t->cap = t->cap ? t->cap * 2 : 64;
        t->v = realloc(t->v, (size_t)t->cap * sizeof(Token));
    }
    t->v[t->len++] = (Token){kind, text, len, num, col};
}

static bool tokenize(const char *s, int n, Tokens *toks) {
    toks->len = 0;
    int i = 0;
    while (i < n) {
        int c = (unsigned char)s[i];
        int start = i;
        if (c == ' ' || c == '\t' || c == '\r') {
            i++;
        } else if (c == '/' && i + 1 < n && s[i + 1] == '/') {
            i = n;
        } else if (is_digit(c)) {
            int64_t v = 0;
            bool big = false;
            while (i < n && is_digit((unsigned char)s[i])) {
                int d = s[i] - '0';
                if (v > (INT64_MAX - d) / 10) big = true;
                else v = v * 10 + d;
                i++;
            }
            if (big) return fail("integer literal %.*s is too large at column %d", i - start, s + start, start + 1);
            push_tok(toks, KNum, s + start, i - start, v, start + 1);
        } else if (is_ident_start(c)) {
            while (i < n && is_ident_char((unsigned char)s[i])) i++;
            push_tok(toks, keyword(s + start, i - start), s + start, i - start, 0, start + 1);
        } else {
            int next = i + 1 < n ? (unsigned char)s[i + 1] : 0;
            Kind kind = KEnd;
            int width = 1;
            switch (c) {
            case '+': kind = KPlus; break;
            case '-': kind = KMinus; break;
            case '*': kind = KStar; break;
            case '/': kind = KSlash; break;
            case '%': kind = KPercent; break;
            case '(': kind = KLParen; break;
            case ')': kind = KRParen; break;
            case ',': kind = KComma; break;
            case '=': if (next == '=') { kind = KEqEq; width = 2; } else kind = KAssign; break;
            case '!': if (next == '=') { kind = KNotEq; width = 2; } break;
            case '<': if (next == '=') { kind = KLessEq; width = 2; } else kind = KLess; break;
            case '>': if (next == '=') { kind = KGreaterEq; width = 2; } else kind = KGreater; break;
            }
            if (kind == KEnd) {
                int end = i + utf8_len(c);
                if (end > n) end = n;
                return fail("unexpected character '%.*s' at column %d", end - i, s + i, i + 1);
            }
            push_tok(toks, kind, s + i, width, 0, i + 1);
            i += width;
        }
    }
    push_tok(toks, KEnd, "", 0, 0, n + 1);
    return true;
}

// ---- syntax tree ----

static char *dup_name(const char *s, int n) {
    char *p = malloc((size_t)n + 1);
    memcpy(p, s, (size_t)n);
    p[n] = 0;
    return p;
}

static Expr *new_expr(ExprTag tag) {
    Expr *e = calloc(1, sizeof(Expr));
    e->tag = tag;
    return e;
}

static void expr_free(Expr *e) {
    if (!e) return;
    expr_free(e->a); expr_free(e->b); expr_free(e->c);
    for (int i = 0; i < e->nargs; i++) expr_free(e->args[i]);
    free(e->args);
    free(e->name);
    free(e);
}

static Expr *mk_bin(Op op, Expr *l, Expr *r) {
    Expr *e = new_expr(EBin);
    e->op = op; e->a = l; e->b = r;
    return e;
}

// ---- parser ----

typedef struct { Token *toks; int pos, depth; } Parser;

static Token *peek(Parser *p) { return &p->toks[p->pos]; }
static Token *next(Parser *p) {
    Token *t = &p->toks[p->pos];
    if (t->kind != KEnd) p->pos++;
    return t;
}

static void describe(const Token *t, char *buf, size_t n) {
    if (t->kind == KEnd) snprintf(buf, n, "end of line");
    else snprintf(buf, n, "'%.*s'", t->len, t->text);
}

static bool unexpected(const Token *t, const char *wanted) {
    char d[256];
    describe(t, d, sizeof d);
    return fail("expected %s but found %s at column %d", wanted, d, t->col);
}

static Token *expect(Parser *p, Kind kind, const char *wanted) {
    Token *t = peek(p);
    if (t->kind != kind) { unexpected(t, wanted); return NULL; }
    return next(p);
}

static bool enter(Parser *p) {
    if (++p->depth > MAX_NESTING)
        return fail("expression nested too deeply (limit %d) at column %d", MAX_NESTING, peek(p)->col);
    return true;
}

static Expr *parse_expr(Parser *p);

static Expr *parse_primary(Parser *p) {
    Token *t = peek(p);
    switch (t->kind) {
    case KNum: {
        next(p);
        Expr *e = new_expr(ENum);
        e->num = t->num;
        return e;
    }
    case KIdent: {
        next(p);
        if (peek(p)->kind == KLParen) {
            next(p);
            Expr *e = new_expr(ECall);
            e->name = dup_name(t->text, t->len);
            if (peek(p)->kind == KRParen) { next(p); return e; }
            int cap = 4;
            e->args = malloc((size_t)cap * sizeof(Expr *));
            for (;;) {
                Expr *a = parse_expr(p);
                if (!a) { expr_free(e); return NULL; }
                if (e->nargs == cap) { cap *= 2; e->args = realloc(e->args, (size_t)cap * sizeof(Expr *)); }
                e->args[e->nargs++] = a;
                if (peek(p)->kind == KComma) next(p);
                else {
                    if (!expect(p, KRParen, "',' or ')'")) { expr_free(e); return NULL; }
                    break;
                }
            }
            return e;
        }
        Expr *e = new_expr(EVar);
        e->name = dup_name(t->text, t->len);
        return e;
    }
    case KLParen: {
        next(p);
        Expr *inner = parse_expr(p);
        if (!inner) return NULL;
        if (!expect(p, KRParen, "')'")) { expr_free(inner); return NULL; }
        return inner;
    }
    case KIf: {
        next(p);
        Expr *e = new_expr(EIf);
        if (!(e->a = parse_expr(p))) goto bad;
        if (!expect(p, KThen, "'then'")) goto bad;
        if (!(e->b = parse_expr(p))) goto bad;
        if (!expect(p, KElse, "'else'")) goto bad;
        if (!(e->c = parse_expr(p))) goto bad;
        return e;
    bad:
        expr_free(e);
        return NULL;
    }
    default:
        unexpected(t, "an expression");
        return NULL;
    }
}

static Expr *parse_unary(Parser *p) {
    if (peek(p)->kind == KMinus) {
        if (!enter(p)) return NULL;
        next(p);
        Expr *operand = parse_unary(p);
        p->depth--;
        if (!operand) return NULL;
        Expr *e = new_expr(ENeg);
        e->a = operand;
        return e;
    }
    return parse_primary(p);
}

static Expr *parse_term(Parser *p) {
    Expr *left = parse_unary(p);
    if (!left) return NULL;
    for (;;) {
        Op op;
        switch (peek(p)->kind) {
        case KStar: op = Mul; break;
        case KSlash: op = Div; break;
        case KPercent: op = Mod; break;
        default: return left;
        }
        next(p);
        Expr *right = parse_unary(p);
        if (!right) { expr_free(left); return NULL; }
        left = mk_bin(op, left, right);
    }
}

static Expr *parse_additive(Parser *p) {
    Expr *left = parse_term(p);
    if (!left) return NULL;
    while (peek(p)->kind == KPlus || peek(p)->kind == KMinus) {
        Op op = next(p)->kind == KPlus ? Add : Sub;
        Expr *right = parse_term(p);
        if (!right) { expr_free(left); return NULL; }
        left = mk_bin(op, left, right);
    }
    return left;
}

static Expr *parse_relational(Parser *p) {
    Expr *left = parse_additive(p);
    if (!left) return NULL;
    for (;;) {
        Op op;
        switch (peek(p)->kind) {
        case KLess: op = Lt; break;
        case KLessEq: op = Le; break;
        case KGreater: op = Gt; break;
        case KGreaterEq: op = Ge; break;
        default: return left;
        }
        next(p);
        Expr *right = parse_additive(p);
        if (!right) { expr_free(left); return NULL; }
        left = mk_bin(op, left, right);
    }
}

static Expr *parse_equality(Parser *p) {
    Expr *left = parse_relational(p);
    if (!left) return NULL;
    while (peek(p)->kind == KEqEq || peek(p)->kind == KNotEq) {
        Op op = next(p)->kind == KEqEq ? Eq : Ne;
        Expr *right = parse_relational(p);
        if (!right) { expr_free(left); return NULL; }
        left = mk_bin(op, left, right);
    }
    return left;
}

static Expr *parse_expr(Parser *p) {
    if (!enter(p)) return NULL;
    Expr *r = parse_equality(p);
    p->depth--;
    return r;
}

static bool finish(Parser *p) {
    Token *t = peek(p);
    if (t->kind != KEnd) {
        char d[256];
        describe(t, d, sizeof d);
        return fail("unexpected %s at column %d", d, t->col);
    }
    return true;
}

static void free_names(char **names, int n) {
    for (int i = 0; i < n; i++) free(names[i]);
    free(names);
}

static bool parse_params(Parser *p, char ***out, int *nout) {
    char **names = NULL;
    int n = 0, cap = 0;
    if (peek(p)->kind == KRParen) { next(p); *out = names; *nout = 0; return true; }
    for (;;) {
        Token *t = expect(p, KIdent, "a parameter name");
        if (!t) goto bad;
        for (int i = 0; i < n; i++)
            if ((int)strlen(names[i]) == t->len && !memcmp(names[i], t->text, (size_t)t->len)) {
                fail("duplicate parameter '%.*s' at column %d", t->len, t->text, t->col);
                goto bad;
            }
        if (n == cap) { cap = cap ? cap * 2 : 4; names = realloc(names, (size_t)cap * sizeof(char *)); }
        names[n++] = dup_name(t->text, t->len);
        if (peek(p)->kind == KComma) next(p);
        else {
            if (!expect(p, KRParen, "',' or ')'")) goto bad;
            break;
        }
    }
    *out = names; *nout = n;
    return true;
bad:
    free_names(names, n);
    return false;
}

// Returns 0 on error, 1 for a statement, 2 for a blank line.
static int parse_line(const char *line, int len, Tokens *toks, Stmt *st) {
    if (!tokenize(line, len, toks)) return 0;
    if (toks->len == 1) return 2;
    Parser p = {toks->v, 0, 0};
    Token *first = peek(&p);
    memset(st, 0, sizeof *st);
    if (first->kind == KLet) {
        next(&p);
        Token *name = expect(&p, KIdent, "a variable name");
        if (!name) return 0;
        if (!expect(&p, KAssign, "'='")) return 0;
        Expr *e = parse_expr(&p);
        if (!e) return 0;
        if (!finish(&p)) { expr_free(e); return 0; }
        st->tag = SDefVar; st->name = dup_name(name->text, name->len); st->expr = e;
    } else if (first->kind == KFn) {
        next(&p);
        Token *name = expect(&p, KIdent, "a function name");
        if (!name) return 0;
        if (!expect(&p, KLParen, "'('")) return 0;
        char **params; int np;
        if (!parse_params(&p, &params, &np)) return 0;
        if (!expect(&p, KAssign, "'='")) { free_names(params, np); return 0; }
        Expr *body = parse_expr(&p);
        if (!body) { free_names(params, np); return 0; }
        if (!finish(&p)) { free_names(params, np); expr_free(body); return 0; }
        st->tag = SDefFn; st->name = dup_name(name->text, name->len);
        st->params = params; st->nparams = np; st->expr = body;
    } else {
        Expr *e = parse_expr(&p);
        if (!e) return 0;
        if (!finish(&p)) { expr_free(e); return 0; }
        st->tag = SShow; st->expr = e;
    }
    return 1;
}

// ---- checked arithmetic ----

static bool op_add(int64_t a, int64_t b, int64_t *r) {
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b))
        return fail("integer overflow in %lld + %lld", (long long)a, (long long)b);
    *r = a + b;
    return true;
}

static bool op_sub(int64_t a, int64_t b, int64_t *r) {
    if ((b > 0 && a < INT64_MIN + b) || (b < 0 && a > INT64_MAX + b))
        return fail("integer overflow in %lld - %lld", (long long)a, (long long)b);
    *r = a - b;
    return true;
}

static bool op_neg(int64_t a, int64_t *r) {
    if (a == INT64_MIN) return fail("integer overflow in -(%lld)", (long long)a);
    *r = -a;
    return true;
}

static bool op_mul(int64_t a, int64_t b, int64_t *r) {
    if (a == 0 || b == 0) { *r = 0; return true; }
    bool too_big;
    if (a == -1) too_big = b == INT64_MIN;
    else if (b == -1) too_big = a == INT64_MIN;
    else if (a > 0) too_big = b > 0 ? b > INT64_MAX / a : b < INT64_MIN / a;
    else too_big = b > 0 ? a < INT64_MIN / b : a < INT64_MAX / b;
    if (too_big) return fail("integer overflow in %lld * %lld", (long long)a, (long long)b);
    *r = a * b;
    return true;
}

static bool op_div(int64_t a, int64_t b, int64_t *r) {
    if (b == 0) return fail("division by zero");
    if (b == -1) {
        if (a == INT64_MIN) return fail("integer overflow in %lld / -1", (long long)a);
        *r = -a;
        return true;
    }
    *r = a / b;
    return true;
}

static bool op_rem(int64_t a, int64_t b, int64_t *r) {
    if (b == 0) return fail("division by zero");
    *r = b == -1 ? 0 : a % b;
    return true;
}

static bool apply(Op op, int64_t a, int64_t b, int64_t *r) {
    switch (op) {
    case Add: return op_add(a, b, r);
    case Sub: return op_sub(a, b, r);
    case Mul: return op_mul(a, b, r);
    case Div: return op_div(a, b, r);
    case Mod: return op_rem(a, b, r);
    case Eq: *r = a == b; return true;
    case Ne: *r = a != b; return true;
    case Lt: *r = a < b; return true;
    case Le: *r = a <= b; return true;
    case Gt: *r = a > b; return true;
    case Ge: *r = a >= b; return true;
    }
    return true;
}

// ---- name tables (open addressing, string keys) ----

typedef struct { char *key; int64_t num; FnDef *fn; } Entry;
typedef struct { Entry *slots; size_t cap, len; } Table;

static uint64_t hash_str(const char *s) {
    uint64_t h = 1469598103934665603ULL;
    for (; *s; s++) h = (h ^ (unsigned char)*s) * 1099511628211ULL;
    return h;
}

static Entry *table_find(const Table *t, const char *key) {
    if (!t->cap) return NULL;
    size_t i = hash_str(key) & (t->cap - 1);
    while (t->slots[i].key) {
        if (!strcmp(t->slots[i].key, key)) return &t->slots[i];
        i = (i + 1) & (t->cap - 1);
    }
    return NULL;
}

static Entry *table_slot(Table *t, const char *key);

static void table_grow(Table *t) {
    Table n = {calloc(t->cap ? t->cap * 2 : 64, sizeof(Entry)), t->cap ? t->cap * 2 : 64, 0};
    for (size_t i = 0; i < t->cap; i++)
        if (t->slots[i].key) {
            size_t j = hash_str(t->slots[i].key) & (n.cap - 1);
            while (n.slots[j].key) j = (j + 1) & (n.cap - 1);
            n.slots[j] = t->slots[i];
            n.len++;
        }
    free(t->slots);
    *t = n;
}

// The entry for key, inserted (with a copy of the key) if absent.
static Entry *table_slot(Table *t, const char *key) {
    Entry *e = table_find(t, key);
    if (e) return e;
    if ((t->len + 1) * 2 > t->cap) table_grow(t);
    size_t i = hash_str(key) & (t->cap - 1);
    while (t->slots[i].key) i = (i + 1) & (t->cap - 1);
    t->slots[i].key = dup_name(key, (int)strlen(key));
    t->len++;
    return &t->slots[i];
}

// ---- evaluator ----

typedef struct { Table vars, fns; } Interp;
typedef struct { char *const *names; const int64_t *vals; int n; } Env;

static bool env_get(const Env *env, const char *name, int64_t *out) {
    for (int i = 0; i < env->n; i++)
        if (!strcmp(env->names[i], name)) { *out = env->vals[i]; return true; }
    return false;
}

static bool eval(Interp *in, const Expr *e, const Env *env, int depth, int64_t *out);

static bool call(Interp *in, const Expr *e, const Env *env, int depth, int64_t *out) {
    Entry *fe = table_find(&in->fns, e->name);
    if (!fe) {
        int64_t tmp;
        if (table_find(&in->vars, e->name) || env_get(env, e->name, &tmp))
            return fail("'%s' is not a function", e->name);
        return fail("unknown function '%s'", e->name);
    }
    FnDef *f = fe->fn;
    if (e->nargs != f->nparams)
        return fail("function '%s' takes %d argument%s, got %d", e->name, f->nparams,
                    f->nparams == 1 ? "" : "s", e->nargs);
    int64_t small[8];
    int64_t *vals = f->nparams <= 8 ? small : malloc((size_t)f->nparams * sizeof(int64_t));
    bool ok = true;
    for (int i = 0; i < e->nargs && ok; i++) ok = eval(in, e->args[i], env, depth, &vals[i]);
    if (ok && depth >= MAX_DEPTH) ok = fail("call depth limit (%d) exceeded in '%s'", MAX_DEPTH, e->name);
    if (ok) {
        Env inner = {f->params, vals, f->nparams};
        ok = eval(in, f->body, &inner, depth + 1, out);
    }
    if (vals != small) free(vals);
    return ok;
}

static bool eval(Interp *in, const Expr *e, const Env *env, int depth, int64_t *out) {
    switch (e->tag) {
    case ENum: *out = e->num; return true;
    case EVar: {
        if (env_get(env, e->name, out)) return true;
        Entry *v = table_find(&in->vars, e->name);
        if (v) { *out = v->num; return true; }
        if (table_find(&in->fns, e->name)) return fail("'%s' is a function, not a variable", e->name);
        return fail("unknown variable '%s'", e->name);
    }
    case ENeg: {
        int64_t x;
        return eval(in, e->a, env, depth, &x) && op_neg(x, out);
    }
    case EBin: {
        int64_t a, b;
        if (!eval(in, e->a, env, depth, &a)) return false;
        if (!eval(in, e->b, env, depth, &b)) return false;
        return apply(e->op, a, b, out);
    }
    case EIf: {
        int64_t c;
        if (!eval(in, e->a, env, depth, &c)) return false;
        return eval(in, c != 0 ? e->b : e->c, env, depth, out);
    }
    case ECall: return call(in, e, env, depth, out);
    }
    return false;
}

// Runs one statement; on success *shown tells whether *value is to be printed.
static bool run(Interp *in, Stmt *st, bool *shown, int64_t *value) {
    static const Env empty = {NULL, NULL, 0};
    *shown = false;
    switch (st->tag) {
    case SDefVar: {
        if (table_find(&in->fns, st->name)) return fail("'%s' is already defined as a function", st->name);
        int64_t v;
        if (!eval(in, st->expr, &empty, 0, &v)) return false;
        table_slot(&in->vars, st->name)->num = v;
        return true;
    }
    case SDefFn: {
        if (table_find(&in->vars, st->name)) return fail("'%s' is already defined as a variable", st->name);
        FnDef *f = malloc(sizeof *f);
        f->params = st->params; f->nparams = st->nparams; f->body = st->expr;
        Entry *e = table_slot(&in->fns, st->name);
        if (e->fn) { free_names(e->fn->params, e->fn->nparams); expr_free(e->fn->body); free(e->fn); }
        e->fn = f;
        st->params = NULL; st->nparams = 0; st->expr = NULL;   // owned by the function now
        return true;
    }
    case SShow:
        if (!eval(in, st->expr, &empty, 0, value)) return false;
        *shown = true;
        return true;
    }
    return false;
}

int main(void) {
    Interp in = {{0}, {0}};
    Tokens toks = {0};
    char *line = NULL;
    size_t cap = 0;
    long statements = 0, errors = 0;
    ssize_t n;
    while ((n = getline(&line, &cap, stdin)) >= 0) {
        if (n > 0 && line[n - 1] == '\n') {
            n--;
            if (n > 0 && line[n - 1] == '\r') n--;
        }
        Stmt st;
        int r = parse_line(line, (int)n, &toks, &st);
        if (r == 2) continue;
        statements++;
        if (r == 1) {
            bool shown = false;
            int64_t v = 0;
            if (run(&in, &st, &shown, &v)) {
                if (shown) printf("%lld\n", (long long)v);
            } else {
                r = 0;
            }
            free(st.name);
            free_names(st.params, st.nparams);
            expr_free(st.expr);
        }
        if (r == 0) {
            errors++;
            printf("error: %s\n", err);
        }
    }
    printf("bye (%ld statements, %ld errors)\n", statements, errors);
    return errors > 0 ? 1 : 0;
}
