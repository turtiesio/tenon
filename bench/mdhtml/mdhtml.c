// mdhtml: Markdown subset to HTML, stdin to stdout (plain C11).
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { char *p; size_t len, cap; } Buf;

static void buf_reserve(Buf *b, size_t extra) {
    if (b->len + extra > b->cap) {
        size_t cap = b->cap ? b->cap : 256;
        while (cap < b->len + extra) cap *= 2;
        b->p = realloc(b->p, cap);
        b->cap = cap;
    }
}
static void put(Buf *b, const char *s, size_t n) {
    buf_reserve(b, n);
    memcpy(b->p + b->len, s, n);
    b->len += n;
}
static void puts_(Buf *b, const char *s) { put(b, s, strlen(s)); }
static void putc_(Buf *b, char c) { buf_reserve(b, 1); b->p[b->len++] = c; }

typedef struct { const char *p; size_t n; } Str;

static bool is_space(int b) { return b == ' ' || b == '\t' || b == '\n' || b == '\r'; }
static bool is_ws(int b) { return is_space(b) || b == '\f'; }

static Str trim(Str s) {
    while (s.n && is_ws((unsigned char)s.p[0])) { s.p++; s.n--; }
    while (s.n && is_ws((unsigned char)s.p[s.n - 1])) s.n--;
    return s;
}
static Str sub(Str s, size_t from, size_t to) { return (Str){s.p + from, to - from}; }
static bool starts_with(Str s, const char *pre) {
    size_t k = strlen(pre);
    return s.n >= k && !memcmp(s.p, pre, k);
}
static bool equals(Str s, const char *t) { return s.n == strlen(t) && !memcmp(s.p, t, s.n); }

static void esc(Buf *out, const char *s, size_t n) {
    size_t run = 0;
    for (size_t i = 0; i < n; i++) {
        const char *rep = NULL;
        switch (s[i]) {
        case '&': rep = "&amp;"; break;
        case '<': rep = "&lt;"; break;
        case '>': rep = "&gt;"; break;
        case '"': rep = "&quot;"; break;
        }
        if (rep) {
            put(out, s + run, i - run);
            puts_(out, rep);
            run = i + 1;
        }
    }
    put(out, s + run, n - run);
}

// ---- inline ----

static void inline_(Buf *out, const char *s, size_t n);

// Each matcher returns true and sets the inner text and the end of the construct.
static bool code_span(const char *s, size_t n, size_t i, size_t *stop) {
    size_t j = i + 1;
    while (j < n && s[j] != '`') j++;
    if (j >= n || j == i + 1) return false;
    *stop = j + 1;
    return true;
}

static bool bold(const char *s, size_t n, size_t i, size_t *inner_end, size_t *stop) {
    size_t start = i + 2;
    if (start >= n || is_space((unsigned char)s[start])) return false;
    size_t j = start + 1;
    while (j + 1 < n) {
        if (s[j] == '*' && s[j + 1] == '*' && !is_space((unsigned char)s[j - 1])) {
            while (j + 2 < n && s[j + 2] == '*') j++;
            *inner_end = j;
            *stop = j + 2;
            return true;
        }
        j++;
    }
    return false;
}

static bool em(const char *s, size_t n, size_t i, size_t *inner_end, size_t *stop) {
    size_t start = i + 1;
    if (start >= n || is_space((unsigned char)s[start])) return false;
    size_t j = start + 1;
    while (j < n) {
        if (s[j] == '*') {
            if (j + 1 < n && s[j + 1] == '*') { j += 2; continue; }
            if (!is_space((unsigned char)s[j - 1])) {
                *inner_end = j;
                *stop = j + 1;
                return true;
            }
        }
        j++;
    }
    return false;
}

static bool link(const char *s, size_t n, size_t i, size_t *close, size_t *stop) {
    size_t j = i + 1;
    while (j < n && s[j] != ']') j++;
    if (j == i + 1 || j + 1 >= n || s[j + 1] != '(') return false;
    size_t k = j + 2;
    while (k < n && s[k] != ')' && !is_space((unsigned char)s[k])) k++;
    if (k >= n || k == j + 2 || s[k] != ')') return false;
    *close = j;
    *stop = k + 1;
    return true;
}

static void inline_(Buf *out, const char *s, size_t n) {
    size_t run = 0, i = 0;
    while (i < n) {
        char b = s[i];
        size_t end = 0, stop = 0;
        if (b == '`' && code_span(s, n, i, &stop)) {
            esc(out, s + run, i - run);
            puts_(out, "<code>");
            esc(out, s + i + 1, stop - 1 - (i + 1));
            puts_(out, "</code>");
        } else if (b == '[' && link(s, n, i, &end, &stop)) {
            esc(out, s + run, i - run);
            puts_(out, "<a href=\"");
            esc(out, s + end + 2, stop - 1 - (end + 2));
            puts_(out, "\">");
            inline_(out, s + i + 1, end - (i + 1));
            puts_(out, "</a>");
        } else if (b == '*' && i + 1 < n && s[i + 1] == '*' && bold(s, n, i, &end, &stop)) {
            esc(out, s + run, i - run);
            puts_(out, "<strong>");
            inline_(out, s + i + 2, end - (i + 2));
            puts_(out, "</strong>");
        } else if (b == '*' && !(i + 1 < n && s[i + 1] == '*') && em(s, n, i, &end, &stop)) {
            esc(out, s + run, i - run);
            puts_(out, "<em>");
            inline_(out, s + i + 1, end - (i + 1));
            puts_(out, "</em>");
        } else {
            // an unclosed "**" is literal as a pair
            if (b == '*' && i + 1 < n && s[i + 1] == '*') i += 2; else i++;
            continue;
        }
        i = stop;
        run = stop;
    }
    esc(out, s + run, n - run);
}

// ---- blocks ----

static size_t heading_level(Str line) {
    size_t k = 0;
    while (k < line.n && line.p[k] == '#') k++;
    return (k >= 1 && k <= 6 && (k == line.n || line.p[k] == ' ')) ? k : 0;
}

// kind 0 = not an item, 1 = bullet, 2 = ordered; *marker is the marker length
static int item_marker(Str line, size_t *marker) {
    if (starts_with(line, "- ") || starts_with(line, "* ")) { *marker = 2; return 1; }
    size_t k = 0;
    while (k < line.n && line.p[k] >= '0' && line.p[k] <= '9') k++;
    if (k >= 1 && k + 1 < line.n && line.p[k] == '.' && line.p[k + 1] == ' ') { *marker = k + 2; return 2; }
    return 0;
}

static bool is_fence(Str line) {
    return starts_with(line, "```") && !memchr(line.p + 3, '`', line.n - 3);
}

static bool starts_block(Str line) {
    size_t m;
    return is_fence(line) || heading_level(line) > 0 || equals(line, "---") || starts_with(line, ">") ||
           item_marker(line, &m) > 0;
}

// Over 80 lines: the block loop, one branch per Markdown block kind, as in the other versions of the benchmark.
static void render(Buf *out, const Str *lines, size_t n) {
    Buf para = {0};
    size_t i = 0;
    while (i < n) {
        Str line = trim(lines[i]);
        size_t m;
        if (line.n == 0) {
            i++;
        } else if (is_fence(line)) {
            Str info = trim(sub(line, 3, line.n));
            size_t lang_len = 0;
            while (lang_len < info.n && info.p[lang_len] != ' ') lang_len++;
            i++;
            puts_(out, "<pre><code");
            if (lang_len) {
                puts_(out, " class=\"language-");
                esc(out, info.p, lang_len);
                putc_(out, '"');
            }
            putc_(out, '>');
            while (i < n && !equals(trim(lines[i]), "```")) {
                esc(out, lines[i].p, lines[i].n);
                putc_(out, '\n');
                i++;
            }
            if (i < n) i++;
            puts_(out, "</code></pre>\n");
        } else if (heading_level(line) > 0) {
            size_t lvl = heading_level(line);
            Str text = trim(sub(line, lvl, line.n));
            char tag[16];
            snprintf(tag, sizeof tag, "<h%zu>", lvl);
            puts_(out, tag);
            inline_(out, text.p, text.n);
            snprintf(tag, sizeof tag, "</h%zu>\n", lvl);
            puts_(out, tag);
            i++;
        } else if (equals(line, "---")) {
            puts_(out, "<hr>\n");
            i++;
        } else if (starts_with(line, ">")) {
            size_t cap = 8, cnt = 0;
            Str *inner = malloc(cap * sizeof(Str));
            while (i < n && starts_with(trim(lines[i]), ">")) {
                Str t = trim(lines[i]);
                Str rest = sub(t, 1, t.n);
                if (starts_with(rest, " ")) rest = sub(rest, 1, rest.n);
                if (cnt == cap) { cap *= 2; inner = realloc(inner, cap * sizeof(Str)); }
                inner[cnt++] = rest;
                i++;
            }
            puts_(out, "<blockquote>\n");
            render(out, inner, cnt);
            puts_(out, "</blockquote>\n");
            free(inner);
        } else if (item_marker(line, &m) > 0) {
            int kind = item_marker(line, &m);
            const char *tag = kind == 1 ? "ul" : "ol";
            puts_(out, "<"); puts_(out, tag); puts_(out, ">\n");
            while (i < n) {
                Str t = trim(lines[i]);
                int k = item_marker(t, &m);
                if (k != kind) break;
                Str text = trim(sub(t, m, t.n));
                puts_(out, "<li>");
                inline_(out, text.p, text.n);
                puts_(out, "</li>\n");
                i++;
            }
            puts_(out, "</"); puts_(out, tag); puts_(out, ">\n");
        } else {
            para.len = 0;
            put(&para, line.p, line.n);
            i++;
            while (i < n) {
                Str t = trim(lines[i]);
                if (t.n == 0 || starts_block(t)) break;
                putc_(&para, '\n');
                put(&para, t.p, t.n);
                i++;
            }
            puts_(out, "<p>");
            inline_(out, para.p, para.len);
            puts_(out, "</p>\n");
        }
    }
    free(para.p);
}

int main(void) {
    Buf in = {0};
    for (;;) {
        buf_reserve(&in, 1 << 16);
        size_t got = fread(in.p + in.len, 1, in.cap - in.len, stdin);
        if (got == 0) break;
        in.len += got;
    }
    // split at "\n", dropping a final empty piece and a trailing "\r" on each line
    size_t cap = 1024, n = 0;
    Str *lines = malloc(cap * sizeof(Str));
    size_t start = 0;
    for (size_t i = 0; i <= in.len; i++) {
        if (i == in.len || in.p[i] == '\n') {
            if (i == in.len && start == i) break;
            size_t end = i;
            if (end > start && in.p[end - 1] == '\r') end--;
            if (n == cap) { cap *= 2; lines = realloc(lines, cap * sizeof(Str)); }
            lines[n++] = (Str){in.p + start, end - start};
            start = i + 1;
        }
    }
    Buf out = {0};
    render(&out, lines, n);
    fwrite(out.p, 1, out.len, stdout);
    return 0;
}
