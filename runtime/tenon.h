/* Tenon C runtime: the only C the compiler relies on. Depends on libc only.
 * Every type N used by generated code has helpers N_retain, N_release, N_eq,
 * N_cmp, N_hash and N_show; the list/map macros below build on that.
 * Semantics must match the reference interpreter (bootstrap/src/interp.rs, bootstrap/src/value.rs). */
#ifndef TENON_H
#define TENON_H
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <ctype.h>
#include <math.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <spawn.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define TN_UNUSED __attribute__((unused))
#define TN_NORETURN __attribute__((noreturn))
#define TN_UNLIKELY(x) __builtin_expect(!!(x), 0)

/* Reserved exit codes (also in bootstrap/src/interp.rs). */
#define TN_EXIT_ERR 1
#define TN_EXIT_TRAP 70
#define TN_EXIT_OOM 71
#define TN_EXIT_STACK 72
#define TN_EXIT_OUTPUT 74

typedef int64_t tn_Int;
typedef double tn_Float;
typedef bool tn_Bool;
typedef uint8_t tn_Unit;
typedef uint8_t tn_Console;
typedef uint8_t tn_Clock;
/* ---------- output, traps, memory ---------- */

/* Workers (v2: lib/v2/prelude.tn) are OS threads, each with its own heap.
 * A program that starts workers is compiled with TN_MT defined (the compiler
 * puts `#define TN_MT 1` before this file): the allocator's free lists, the
 * release queue and the trap location become thread-local (and recursive
 * enums use the free lists instead of per-type pools), and the output and
 * input buffers are locked. Without TN_MT none of this costs anything.
 * Reference counts stay plain integers in both cases: values move between
 * workers only as deep copies (section "workers and channels"). */
/* The runtime's state (the variables marked TN_STATE). A program is one C
 * file, where the state is static; `tenonc build` compiles a large program
 * as several translation units (selfhost/tenonc.tn): the state is then
 * defined in the unit with TN_SPLIT 1 and extern in those with TN_SPLIT 2. */
#if !defined(TN_SPLIT)
#define TN_STATE static
#define TN_INIT(...) = __VA_ARGS__
#elif TN_SPLIT == 1
#define TN_STATE
#define TN_INIT(...) = __VA_ARGS__
#else
#define TN_STATE extern
#define TN_INIT(...)
#endif

#define TN_SMALL_MAX 512
typedef struct { void *p; void (*f)(void *); } tn_deferred;
#ifdef TN_MT
/* A thread's runtime state, in one thread-local struct: on macOS finding a
 * thread-local variable is a call, and one struct needs it once per function
 * (separate variables made bench/trees 25% slower, the struct 4%). */
struct tn_thread_s {
    const char *cur_loc;
    void *freelist[TN_SMALL_MAX / 16 + 1];
    int64_t free_bytes;
    int rel_depth;
    tn_deferred *defer_q;
    int64_t defer_n, defer_cap;
    bool in_worker;
};
TN_STATE _Thread_local struct tn_thread_s tn_th TN_INIT({.cur_loc = "?"});
#define tn_cur_loc (tn_th.cur_loc)
#define tn_freelist (tn_th.freelist)
#define tn_free_bytes (tn_th.free_bytes)
#define tn_rel_depth (tn_th.rel_depth)
#define tn_defer_q (tn_th.defer_q)
#define tn_defer_n (tn_th.defer_n)
#define tn_defer_cap (tn_th.defer_cap)
#define tn_in_worker (tn_th.in_worker)
TN_STATE pthread_mutex_t tn_out_mu TN_INIT(PTHREAD_MUTEX_INITIALIZER);
TN_STATE pthread_mutex_t tn_in_mu TN_INIT(PTHREAD_MUTEX_INITIALIZER);
TN_STATE pthread_mutex_t tn_trap_mu TN_INIT(PTHREAD_MUTEX_INITIALIZER);
#define TN_LOCK(m) pthread_mutex_lock(&(m))
#define TN_UNLOCK(m) pthread_mutex_unlock(&(m))
#else
TN_STATE const char *tn_cur_loc TN_INIT("?");
TN_STATE void *tn_freelist[TN_SMALL_MAX / 16 + 1];
TN_STATE int tn_rel_depth;
TN_STATE tn_deferred *tn_defer_q;
TN_STATE int64_t tn_defer_n, tn_defer_cap;
TN_STATE bool tn_in_worker;
#define TN_LOCK(m) ((void)0)
#define TN_UNLOCK(m) ((void)0)
#endif

TN_STATE char tn_out_buf[1 << 16];
TN_STATE size_t tn_out_len;

static void tn_write_fd(int fd, const char *p, size_t n, bool fatal) {
    while (n > 0) {
        ssize_t w = write(fd, p, n);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) {
            if (fatal) _exit(TN_EXIT_OUTPUT);
            return;
        }
        p += w;
        n -= (size_t)w;
    }
}
static void tn_flush_u(void) {
    tn_write_fd(1, tn_out_buf, tn_out_len, true);
    tn_out_len = 0;
}
static void tn_flush(void) {
    TN_LOCK(tn_out_mu);
    tn_flush_u();
    TN_UNLOCK(tn_out_mu);
}
static void tn_write_u(const char *p, size_t n) {
    if (tn_out_len + n > sizeof tn_out_buf) {
        tn_flush_u();
        if (n > sizeof tn_out_buf) {
            tn_write_fd(1, p, n, true);
            return;
        }
    }
    memcpy(tn_out_buf + tn_out_len, p, n);
    tn_out_len += n;
}
static TN_UNUSED void tn_write(const char *p, size_t n) {
    TN_LOCK(tn_out_mu);
    tn_write_u(p, n);
    TN_UNLOCK(tn_out_mu);
}
/* println in a program with workers: the line and its "\n" in one piece, so
 * lines printed by different workers never mix. */
static TN_UNUSED void tn_writeln(const char *p, size_t n) {
    TN_LOCK(tn_out_mu);
    tn_write_u(p, n);
    tn_write_u("\n", 1);
    TN_UNLOCK(tn_out_mu);
}
static void tn_ewrite(const char *s) { tn_write_fd(2, s, strlen(s), false); }

TN_NORETURN static void tn_trap(const char *msg, const char *loc) {
    TN_LOCK(tn_trap_mu); /* one trap message; a second trapping worker waits for the exit */
    tn_flush();
    tn_ewrite("trap: ");
    tn_ewrite(msg);
    tn_ewrite("\n  at ");
    tn_ewrite(loc);
    tn_ewrite("\n");
    _exit(TN_EXIT_TRAP);
}
TN_NORETURN static TN_UNUSED void tn_trapf(const char *loc, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
#include <stdarg.h>
TN_NORETURN static TN_UNUSED void tn_trapf(const char *loc, const char *fmt, ...) {
    char msg[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(msg, sizeof msg, fmt, ap);
    va_end(ap);
    tn_trap(msg, loc);
}
TN_NORETURN static TN_UNUSED void tn_trap_bytes(const char *p, int64_t n, const char *loc) {
    char msg[1024];
    if (n > (int64_t)sizeof msg - 1) n = sizeof msg - 1;
    memcpy(msg, p, (size_t)n);
    msg[n] = 0;
    tn_trap(msg, loc);
}
TN_NORETURN static void tn_oom(void) {
    TN_LOCK(tn_trap_mu);
    tn_flush();
    tn_ewrite("trap: out of memory\n");
    _exit(TN_EXIT_OOM);
}
/* Allocation: blocks of up to 512 bytes come from per-size free lists (16-byte
 * classes); every block carries a 16-byte header with its class. Larger blocks
 * use malloc. Sanitizer builds (TN_POOL_MAX=0) bypass the lists. With workers
 * the lists are per thread; a block freed by another worker than the one that
 * allocated it joins the freeing worker's lists, which keep at most
 * TN_FREE_MAX bytes (the rest goes back to malloc), so a worker that only
 * receives does not hoard memory. */
#ifdef TN_MT
#define TN_FREE_MAX (64 << 20)
#endif
static inline void *tn_alloc(size_t n) {
    size_t c = (n + 15) >> 4;
    if (c == 0) c = 1;
    if (c <= TN_SMALL_MAX / 16) {
#if !defined(TN_POOL_MAX) || TN_POOL_MAX > 0
        void *h = tn_freelist[c];
        if (h) {
            tn_freelist[c] = *(void **)((char *)h + 16);
#ifdef TN_MT
            tn_free_bytes -= (int64_t)c * 16;
#endif
            return (char *)h + 16;
        }
#endif
        uint64_t *h2 = malloc(16 + c * 16);
        if (!h2) tn_oom();
        h2[0] = c;
        return (char *)h2 + 16;
    }
    uint64_t *h = malloc(16 + n);
    if (!h) tn_oom();
    h[0] = 0;
    h[1] = n;
    return (char *)h + 16;
}
static inline void tn_free(void *p) {
    if (!p) return;
    uint64_t *h = (uint64_t *)((char *)p - 16);
#if !defined(TN_POOL_MAX) || TN_POOL_MAX > 0
#ifdef TN_MT
    if (h[0] && tn_free_bytes < TN_FREE_MAX) {
        tn_free_bytes += (int64_t)h[0] * 16;
#else
    if (h[0]) {
#endif
        *(void **)p = tn_freelist[h[0]];
        tn_freelist[h[0]] = h;
        return;
    }
#endif
    free(h);
}
static TN_UNUSED void *tn_realloc(void *p, size_t n) {
    if (!p) return tn_alloc(n);
    uint64_t *h = (uint64_t *)((char *)p - 16);
    size_t have = h[0] ? h[0] * 16 : h[1];
    if (n <= have) return p;
    if (!h[0] && n > TN_SMALL_MAX) {
        h = realloc(h, 16 + n);
        if (!h) tn_oom();
        h[1] = n;
        return (char *)h + 16;
    }
    void *q = tn_alloc(n);
    memcpy(q, p, have);
    tn_free(p);
    return q;
}

static void tn_on_segv(int sig) {
    (void)sig;
    /* Generated code is memory-safe, so a fault means the stack ran out. */
    static const char m[] = "trap: stack overflow\n";
    tn_write_fd(1, tn_out_buf, tn_out_len, false);
    tn_write_fd(2, m, sizeof m - 1, false);
    _exit(TN_EXIT_STACK);
}

TN_STATE int tn_argc;
TN_STATE char **tn_argv;
TN_STATE struct timespec tn_mono0;

/* The program runs on a thread with a 1 GB stack (reserved, committed only as
 * used), like the interpreter, so deep recursion behaves the same in both. */
TN_STATE void (*tn_main_fn)(void);
static void *tn_main_thread(void *arg) {
    (void)arg;
    static char altstack[1 << 16]; /* the overflow handler runs here */
    stack_t ss = {.ss_sp = altstack, .ss_size = sizeof altstack, .ss_flags = 0};
    sigaltstack(&ss, NULL);
    tn_main_fn();
    return NULL;
}
static TN_UNUSED void tn_run_main(void (*f)(void)) {
    tn_main_fn = f;
    pthread_attr_t at;
    pthread_attr_init(&at);
    pthread_attr_setstacksize(&at, (size_t)1 << 30);
    pthread_t th;
    if (pthread_create(&th, &at, tn_main_thread, NULL) != 0) {
        tn_main_thread(NULL); /* fall back to the process stack */
        return;
    }
    pthread_join(th, NULL);
}
static TN_UNUSED void tn_init(int argc, char **argv) {
    tn_argc = argc;
    tn_argv = argv;
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = tn_on_segv;
    sa.sa_flags = SA_ONSTACK;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);
    clock_gettime(CLOCK_MONOTONIC, &tn_mono0);
}
TN_NORETURN static TN_UNUSED void tn_exit(int code) {
    tn_flush();
#ifdef TN_MT
    TN_LOCK(tn_trap_mu); /* workers still running end here too, without exit handlers under them */
    _exit(code);
#else
    exit(code);
#endif
}

/* Capabilities and functions are not comparable (the checker rejects it);
 * these exist only so derived helpers of enclosing types are complete. */
#define TN_INCOMPARABLE(T)                                                      \
    static inline TN_UNUSED bool T##_dec(void *d, T *out) { (void)d; (void)out; return false; } \
    static inline TN_UNUSED bool T##_eq(T a, T b) { (void)a; (void)b; return false; } \
    static inline TN_UNUSED int T##_cmp(T a, T b) { (void)a; (void)b; return 0; }     \
    static inline TN_UNUSED uint64_t T##_hash(T a) { (void)a; return 0; }             \
    static inline TN_UNUSED bool T##_same(T a, T b) { (void)a; (void)b; return false; }

/* Releasing deeply nested recursive values (a million-long chain of enum
 * nodes) must not overflow the C stack: past a nesting depth, frees are
 * queued and drained iteratively. */
/* Freed nodes of recursive enums are reused, up to this many per type.
 * Sanitizer builds set it to 0 so that use-after-free stays detectable. */
#ifndef TN_MAP_SMALL
#define TN_MAP_SMALL 8
#endif
#ifndef TN_POOL_MAX
#define TN_POOL_MAX 65536
#endif
static TN_UNUSED void tn_defer(void *p, void (*f)(void *)) {
    if (tn_defer_n == tn_defer_cap) {
        tn_defer_cap = tn_defer_cap ? tn_defer_cap * 2 : 256;
        tn_defer_q = realloc(tn_defer_q, sizeof(tn_deferred) * (size_t)tn_defer_cap);
        if (!tn_defer_q) _exit(TN_EXIT_OOM);
    }
    tn_defer_q[tn_defer_n++] = (tn_deferred){p, f};
}
static TN_UNUSED void tn_drain(void) {
    while (tn_defer_n) {
        tn_deferred d = tn_defer_q[--tn_defer_n];
        d.f(d.p);
    }
}

/* ---------- checked arithmetic ---------- */

static inline tn_Int tn_add(tn_Int a, tn_Int b, const char *loc) {
    tn_Int r;
    if (TN_UNLIKELY(__builtin_add_overflow(a, b, &r))) tn_trap("integer overflow", loc);
    return r;
}
static inline tn_Int tn_sub(tn_Int a, tn_Int b, const char *loc) {
    tn_Int r;
    if (TN_UNLIKELY(__builtin_sub_overflow(a, b, &r))) tn_trap("integer overflow", loc);
    return r;
}
static inline tn_Int tn_mul(tn_Int a, tn_Int b, const char *loc) {
    tn_Int r;
    if (TN_UNLIKELY(__builtin_mul_overflow(a, b, &r))) tn_trap("integer overflow", loc);
    return r;
}
static inline tn_Int tn_div(tn_Int a, tn_Int b, const char *loc) {
    if (TN_UNLIKELY(b == 0)) tn_trap("division by zero", loc);
    if (TN_UNLIKELY(a == INT64_MIN && b == -1)) tn_trap("integer overflow", loc);
    return a / b;
}
static inline tn_Int tn_rem(tn_Int a, tn_Int b, const char *loc) {
    if (TN_UNLIKELY(b == 0)) tn_trap("division by zero", loc);
    if (TN_UNLIKELY(a == INT64_MIN && b == -1)) tn_trap("integer overflow", loc);
    return a % b;
}
static inline tn_Int tn_neg(tn_Int a, const char *loc) {
    if (TN_UNLIKELY(a == INT64_MIN)) tn_trap("integer overflow", loc);
    return -a;
}

/* ---------- strings: refcounted buffers with views ---------- */

typedef struct { int64_t rc, cap; } tn_rc; /* cap: bytes available after the header */
typedef struct { const char *p; int64_t len; tn_rc *o; } tn_Str;

static inline tn_Str tn_Str_retain(tn_Str s) {
    if (s.o) s.o->rc++;
    return s;
}
static inline void tn_Str_release(tn_Str s) {
    if (s.o && --s.o->rc == 0) tn_free(s.o);
}
static inline tn_Str tn_str_lit(const char *p, int64_t n) { return (tn_Str){p, n, NULL}; }
static TN_UNUSED tn_Str tn_str_new(const char *p, int64_t n) {
    tn_rc *o = tn_alloc(sizeof(tn_rc) + (size_t)n);
    o->rc = 1;
    o->cap = n;
    memcpy(o + 1, p, (size_t)n);
    return (tn_Str){(const char *)(o + 1), n, o};
}
static inline tn_Str tn_str_view(tn_Str s, int64_t a, int64_t b) {
    if (s.o) s.o->rc++;
    return (tn_Str){s.p + a, b - a, s.o};
}

/* String builder; tn_buf_finish hands the bytes over as a tn_Str. */
typedef struct { char *p; int64_t len, cap; } tn_buf;
static TN_UNUSED tn_buf tn_buf_new(void) {
    tn_buf b;
    b.cap = 64;
    b.p = tn_alloc(sizeof(tn_rc) + 64);
    b.len = 0;
    return b;
}
static inline void tn_buf_grow(tn_buf *b, int64_t extra) {
    if (b->len + extra > b->cap) {
        while (b->len + extra > b->cap) b->cap *= 2;
        b->p = tn_realloc(b->p, sizeof(tn_rc) + (size_t)b->cap);
    }
}
static inline void tn_buf_add(tn_buf *b, const char *p, int64_t n) {
    tn_buf_grow(b, n);
    memcpy(b->p + sizeof(tn_rc) + b->len, p, (size_t)n);
    b->len += n;
}
static inline void tn_buf_str(tn_buf *b, tn_Str s) { tn_buf_add(b, s.p, s.len); }
static inline void tn_buf_cstr(tn_buf *b, const char *s) { tn_buf_add(b, s, (int64_t)strlen(s)); }
static TN_UNUSED tn_Str tn_buf_finish(tn_buf *b) {
    tn_rc *o = (tn_rc *)b->p;
    o->rc = 1;
    o->cap = b->cap;
    return (tn_Str){b->p + sizeof(tn_rc), b->len, o};
}

/* Identity: same view of the same bytes (cheap, conservative equality). */
static inline bool tn_Str_same(tn_Str a, tn_Str b) { return a.p == b.p && a.len == b.len; }
static inline bool tn_str_eq_c(tn_Str a, const char *c) {
    size_t n = strlen(c);
    return (size_t)a.len == n && memcmp(a.p, c, n) == 0;
}
static inline bool tn_Str_eq(tn_Str a, tn_Str b) {
    if (a.len != b.len) return false;
    if (a.p == b.p) return true;
    if (a.len <= 16) { /* short strings: compare inline instead of calling memcmp */
        for (int64_t i = 0; i < a.len; i++)
            if (a.p[i] != b.p[i]) return false;
        return true;
    }
    return memcmp(a.p, b.p, (size_t)a.len) == 0;
}
static inline int tn_Str_cmp(tn_Str a, tn_Str b) {
    int64_t n = a.len < b.len ? a.len : b.len;
    int c = n ? memcmp(a.p, b.p, (size_t)n) : 0;
    if (c) return c < 0 ? -1 : 1;
    return a.len < b.len ? -1 : a.len > b.len ? 1 : 0;
}
static inline uint64_t tn_mix(uint64_t h) {
    h ^= h >> 33;
    h *= 0xff51afd7ed558ccdULL;
    h ^= h >> 33;
    h *= 0xc4ceb9fe1a85ec53ULL;
    h ^= h >> 33;
    return h;
}
static inline uint64_t tn_Str_hash(tn_Str s) {
    uint64_t h = 0x9E3779B97F4A7C15ULL ^ (uint64_t)s.len;
    const char *p = s.p;
    int64_t n = s.len;
    for (; n >= 8; p += 8, n -= 8) {
        uint64_t w;
        memcpy(&w, p, 8);
        h = (h ^ w) * 0xbf58476d1ce4e5b9ULL;
        h ^= h >> 31;
    }
    uint64_t w = 0;
    for (int64_t i = 0; i < n; i++) w |= (uint64_t)(uint8_t)p[i] << (8 * i); /* no memcpy call */
    return tn_mix(h ^ w);
}
/* mode: TN_TOP (a top-level string prints raw), TN_FULL (encode: show every field) */
#define TN_TOP 1
#define TN_FULL 2
static TN_UNUSED void tn_Str_show(tn_buf *b, tn_Str s, int mode) {
    if (mode & TN_TOP) {
        tn_buf_str(b, s);
        return;
    }
    tn_buf_add(b, "\"", 1);
    for (int64_t i = 0; i < s.len; i++) {
        unsigned char c = (unsigned char)s.p[i];
        switch (c) {
        case '"': tn_buf_add(b, "\\\"", 2); break;
        case '\\': tn_buf_add(b, "\\\\", 2); break;
        case '\n': tn_buf_add(b, "\\n", 2); break;
        case '\t': tn_buf_add(b, "\\t", 2); break;
        case '\r': tn_buf_add(b, "\\r", 2); break;
        default:
            if (c < 0x20) {
                char t[16];
                snprintf(t, sizeof t, "\\u{%x}", c);
                tn_buf_cstr(b, t);
            } else {
                tn_buf_add(b, (const char *)&c, 1);
            }
        }
    }
    tn_buf_add(b, "\"", 1);
}

/* ---------- scalar helpers ---------- */

#define TN_TRIVIAL(T)                                                     \
    static inline T T##_retain(T x) { return x; }                         \
    static inline void T##_release(T x) { (void)x; }
TN_TRIVIAL(tn_Int)
TN_TRIVIAL(tn_Float)
TN_TRIVIAL(tn_Bool)
TN_TRIVIAL(tn_Unit)
TN_TRIVIAL(tn_Console)
TN_TRIVIAL(tn_Clock)

static inline bool tn_Int_eq(tn_Int a, tn_Int b) { return a == b; }
static inline bool tn_Int_same(tn_Int a, tn_Int b) { return a == b; }
static inline bool tn_Float_same(tn_Float a, tn_Float b) { (void)a; (void)b; return false; }
static inline bool tn_Bool_same(tn_Bool a, tn_Bool b) { return a == b; }
static inline bool tn_Unit_same(tn_Unit a, tn_Unit b) { (void)a; (void)b; return true; }
static inline int tn_Int_cmp(tn_Int a, tn_Int b) { return a < b ? -1 : a > b; }
static inline uint64_t tn_Int_hash(tn_Int a) { return tn_mix((uint64_t)a); }
static TN_UNUSED void tn_Int_show(tn_buf *b, tn_Int x, int mode) {
    (void)mode;
    char t[24];
    int n = snprintf(t, sizeof t, "%lld", (long long)x);
    tn_buf_add(b, t, n);
}
static inline bool tn_Float_eq(tn_Float a, tn_Float b) { return a == b; }
static inline int tn_Float_cmp(tn_Float a, tn_Float b) { return a < b ? -1 : a > b; }
static inline uint64_t tn_Float_hash(tn_Float a) {
    if (a == 0.0) a = 0.0;
    uint64_t u;
    memcpy(&u, &a, 8);
    return tn_mix(u);
}
/* Shortest round-trip digits; layout matches value.rs layout_float. */
static TN_UNUSED void tn_Float_show(tn_buf *b, tn_Float x, int mode) {
    (void)mode;
    if (isnan(x)) { tn_buf_cstr(b, "nan"); return; }
    if (isinf(x)) { tn_buf_cstr(b, x > 0 ? "inf" : "-inf"); return; }
    if (signbit(x)) tn_buf_add(b, "-", 1);
    double a = fabs(x);
    char t[40];
    int prec;
    for (prec = 0; prec < 17; prec++) {
        snprintf(t, sizeof t, "%.*e", prec, a);
        if (strtod(t, NULL) == a) break;
    }
    char digits[24];
    int nd = 0;
    char *p = t;
    for (; *p && *p != 'e'; p++)
        if (*p != '.') digits[nd++] = *p;
    int exp = atoi(p + 1);
    while (nd > 1 && digits[nd - 1] == '0') nd--;
    if (exp >= -5 && exp < 16) {
        if (exp >= 0) {
            for (int i = 0; i <= exp; i++) tn_buf_add(b, i < nd ? &digits[i] : "0", 1);
            tn_buf_add(b, ".", 1);
            if (nd > exp + 1) tn_buf_add(b, digits + exp + 1, nd - exp - 1);
            else tn_buf_add(b, "0", 1);
        } else {
            tn_buf_add(b, "0.", 2);
            for (int i = 0; i < -exp - 1; i++) tn_buf_add(b, "0", 1);
            tn_buf_add(b, digits, nd);
        }
    } else {
        tn_buf_add(b, digits, 1);
        if (nd > 1) {
            tn_buf_add(b, ".", 1);
            tn_buf_add(b, digits + 1, nd - 1);
        }
        char e[12];
        int n = snprintf(e, sizeof e, "e%d", exp);
        tn_buf_add(b, e, n);
    }
}
static inline bool tn_Bool_eq(tn_Bool a, tn_Bool b) { return a == b; }
static inline int tn_Bool_cmp(tn_Bool a, tn_Bool b) { return (int)a - (int)b; }
static inline uint64_t tn_Bool_hash(tn_Bool a) { return a; }
static TN_UNUSED void tn_Bool_show(tn_buf *b, tn_Bool x, int mode) {
    (void)mode;
    tn_buf_cstr(b, x ? "true" : "false");
}
static inline bool tn_Unit_eq(tn_Unit a, tn_Unit b) { (void)a; (void)b; return true; }
static inline int tn_Unit_cmp(tn_Unit a, tn_Unit b) { (void)a; (void)b; return 0; }
static inline uint64_t tn_Unit_hash(tn_Unit a) { (void)a; return 0; }
static TN_UNUSED void tn_Unit_show(tn_buf *b, tn_Unit x, int mode) { (void)x; (void)mode; tn_buf_cstr(b, "()"); }

/* Float.to_fixed text into t (512 bytes: "-", 309 digits, ".", 100 decimals
   fit); decimals clamped to 0..100. Matches value.rs float_fixed. */
static TN_UNUSED int tn_float_fixed_into(char *t, tn_Float x, tn_Int d) {
    if (isnan(x)) { memcpy(t, "nan", 3); return 3; }
    if (isinf(x)) { memcpy(t, x > 0 ? "inf" : "-inf", x > 0 ? 3 : 4); return x > 0 ? 3 : 4; }
    if (d < 0) d = 0;
    if (d > 100) d = 100;
    return snprintf(t, 512, "%.*f", (int)d, x);
}

/* Format specs "{x:SPEC}" (ast.rs FmtSpec): the value is written straight
   into the output buffer, then padded in place. prec -1: none; align and
   radix 0: none. */
typedef struct { const char *fill; int fill_len; char align, zero, group; int width, prec; char radix; } tn_fmt_spec;
/* ',' grouping of the integer digits after the sign, in place (ast.rs
   FmtSpec::group_digits): with '0' the padding zeros are grouped digits too,
   so the result is at least the width and never starts with ','. The text
   after the digits is ASCII ('.', digits, 'e'), so bytes count as code points. */
static TN_UNUSED void tn_fmt_group(tn_buf *b, int64_t start, const tn_fmt_spec *f) {
    char *body = b->p + sizeof(tn_rc) + start;
    int64_t n = b->len - start;
    int64_t sign = n > 0 && body[0] == '-', d = 0;
    while (sign + d < n && body[sign + d] >= '0' && body[sign + d] <= '9') d++;
    if (d == 0) return;
    int64_t tail = n - sign - d, k = d;
    if (f->zero) while (sign + k + (k - 1) / 3 + tail < f->width) k++;
    int64_t g = k + (k - 1) / 3;
    tn_buf_grow(b, g - d);
    body = b->p + sizeof(tn_rc) + start;
    memmove(body + sign + g, body + sign + d, (size_t)tail);
    int64_t src = sign + d - 1, dst = sign + g - 1;
    for (int64_t j = 0; j < k; j++) { /* right to left; dst >= src throughout */
        if (j > 0 && j % 3 == 0) body[dst--] = ',';
        body[dst--] = j < d ? body[src--] : '0';
    }
    b->len += g - d;
}
static TN_UNUSED void tn_fmt_pad(tn_buf *b, int64_t start, int numeric, const tn_fmt_spec *f) {
    char *body = b->p + sizeof(tn_rc) + start;
    int64_t n = b->len - start, cps = 0;
    for (int64_t i = 0; i < n; i++) cps += ((unsigned char)body[i] & 0xC0) != 0x80;
    if (cps >= f->width) return;
    int64_t pad = f->width - cps;
    if (f->zero) {
        int64_t sign = n > 0 && body[0] == '-';
        tn_buf_grow(b, pad);
        body = b->p + sizeof(tn_rc) + start;
        memmove(body + sign + pad, body + sign, (size_t)(n - sign));
        memset(body + sign, '0', (size_t)pad);
        b->len += pad;
        return;
    }
    char a = f->align ? f->align : (numeric ? '>' : '<');
    int64_t left = a == '<' ? 0 : a == '^' ? pad / 2 : pad;
    tn_buf_grow(b, pad * f->fill_len);
    body = b->p + sizeof(tn_rc) + start;
    memmove(body + left * f->fill_len, body, (size_t)n);
    for (int64_t i = 0; i < left; i++) memcpy(body + i * f->fill_len, f->fill, (size_t)f->fill_len);
    b->len += left * f->fill_len;
    for (int64_t i = left; i < pad; i++) tn_buf_add(b, f->fill, f->fill_len);
}
static TN_UNUSED void tn_Int_fmt(tn_buf *b, tn_Int x, const tn_fmt_spec *f) {
    int64_t start = b->len;
    if (!f->radix) {
        tn_Int_show(b, x, 0);
    } else {
        int base = f->radix == 'b' ? 2 : f->radix == 'o' ? 8 : 16;
        const char *dg = f->radix == 'X' ? "0123456789ABCDEF" : "0123456789abcdef";
        uint64_t m = x < 0 ? (uint64_t)0 - (uint64_t)x : (uint64_t)x;
        char r[72];
        int k = 72;
        do { r[--k] = dg[m % (uint64_t)base]; m /= (uint64_t)base; } while (m);
        if (x < 0) r[--k] = '-';
        tn_buf_add(b, r + k, 72 - k);
    }
    if (f->group) tn_fmt_group(b, start, f);
    tn_fmt_pad(b, start, 1, f);
}
static TN_UNUSED void tn_Float_fmt(tn_buf *b, tn_Float x, const tn_fmt_spec *f) {
    int64_t start = b->len;
    if (f->prec >= 0) {
        char t[512];
        tn_buf_add(b, t, tn_float_fixed_into(t, x, f->prec));
    } else {
        tn_Float_show(b, x, 0);
    }
    if (f->group) tn_fmt_group(b, start, f);
    tn_fmt_pad(b, start, 1, f);
}
static TN_UNUSED void tn_Str_fmt(tn_buf *b, tn_Str s, const tn_fmt_spec *f) {
    int64_t start = b->len;
    tn_buf_str(b, s);
    tn_fmt_pad(b, start, 0, f);
}
static TN_UNUSED void tn_Bool_fmt(tn_buf *b, tn_Bool x, const tn_fmt_spec *f) {
    int64_t start = b->len;
    tn_Bool_show(b, x, 0);
    tn_fmt_pad(b, start, 0, f);
}
static TN_UNUSED void tn_Console_show(tn_buf *b, tn_Console x, int mode) { (void)x; (void)mode; tn_buf_cstr(b, "<Console>"); }
static TN_UNUSED void tn_Clock_show(tn_buf *b, tn_Clock x, int mode) { (void)x; (void)mode; tn_buf_cstr(b, "<Clock>"); }
TN_INCOMPARABLE(tn_Console)
TN_INCOMPARABLE(tn_Clock)

/* ---------- derived codec: strict decoding (see bootstrap/src/codec.rs) ---------- */

typedef struct { const char *p; int64_t n, pos, err; } tn_dec;
static bool tn_utf8_lossy(const char *p, int64_t n, tn_buf *out);
static bool tn_str_to_int(tn_Str s, tn_Int *out);
static bool tn_str_to_float(tn_Str s, tn_Float *out);
static inline bool tn_dec_fail(tn_dec *d, int64_t at) {
    if (d->err < 0) d->err = at;
    return false;
}
static inline bool tn_dec_lit(tn_dec *d, const char *l) {
    int64_t n = (int64_t)strlen(l);
    if (d->pos + n <= d->n && memcmp(d->p + d->pos, l, (size_t)n) == 0) {
        d->pos += n;
        return true;
    }
    return false;
}
static inline bool tn_dec_expect(tn_dec *d, const char *l) { return tn_dec_lit(d, l) || tn_dec_fail(d, d->pos); }
/* class 0: [-0-9]  1: [-+.A-Za-z0-9]  2: [A-Za-z0-9_] */
static TN_UNUSED tn_Str tn_dec_run(tn_dec *d, int cls) {
    int64_t st = d->pos;
    while (d->pos < d->n) {
        char c = d->p[d->pos];
        bool dig = c >= '0' && c <= '9', alpha = (c | 0x20) >= 'a' && (c | 0x20) <= 'z';
        bool ok = cls == 0 ? (dig || c == '-') : cls == 1 ? (dig || alpha || c == '-' || c == '+' || c == '.') : (dig || alpha || c == '_');
        if (!ok) break;
        d->pos++;
    }
    return (tn_Str){d->p + st, d->pos - st, NULL};
}
/* The consumed text must be exactly the canonical encoding of the value. */
static TN_UNUSED bool tn_dec_canon(tn_dec *d, tn_buf *b, tn_Str text, int64_t start) {
    bool ok = b->len == text.len && memcmp(b->p + sizeof(tn_rc), text.p, (size_t)text.len) == 0;
    tn_free(b->p);
    return ok || tn_dec_fail(d, start);
}

TN_NORETURN static TN_UNUSED void tn_trap_str(tn_Str s, const char *loc) { tn_trap_bytes(s.p, s.len, loc); }
TN_NORETURN static TN_UNUSED void tn_trap_buf(tn_buf *b, const char *loc) {
    tn_trap_bytes(b->p + sizeof(tn_rc), b->len, loc);
}

/* Stable merge sort of an index permutation; cmp compares the items at two indices. */
static TN_UNUSED void tn_msort_idx(int64_t *idx, int64_t *tmp, int64_t n, int (*cmp)(void *, int64_t, int64_t), void *ctx) {
    if (n < 2) return;
    int64_t h = n / 2;
    tn_msort_idx(idx, tmp, h, cmp, ctx);
    tn_msort_idx(idx + h, tmp, n - h, cmp, ctx);
    if (cmp(ctx, idx[h - 1], idx[h]) <= 0) return;
    memcpy(tmp, idx, sizeof(int64_t) * (size_t)h);
    int64_t i = 0, j = h, k = 0;
    while (i < h && j < n) idx[k++] = cmp(ctx, idx[j], tmp[i]) < 0 ? idx[j++] : tmp[i++];
    while (i < h) idx[k++] = tmp[i++];
}

static TN_UNUSED bool tn_Int_dec(tn_dec *d, tn_Int *out) {
    int64_t st = d->pos;
    tn_Str t = tn_dec_run(d, 0);
    if (!tn_str_to_int(t, out)) return tn_dec_fail(d, st);
    tn_buf b = tn_buf_new();
    tn_Int_show(&b, *out, 0);
    return tn_dec_canon(d, &b, t, st);
}
static TN_UNUSED bool tn_Float_dec(tn_dec *d, tn_Float *out) {
    int64_t st = d->pos;
    tn_Str t = tn_dec_run(d, 1);
    if (!tn_str_to_float(t, out)) return tn_dec_fail(d, st);
    tn_buf b = tn_buf_new();
    tn_Float_show(&b, *out, 0);
    return tn_dec_canon(d, &b, t, st);
}
static TN_UNUSED bool tn_Bool_dec(tn_dec *d, tn_Bool *out) {
    if (tn_dec_lit(d, "true")) { *out = true; return true; }
    if (tn_dec_lit(d, "false")) { *out = false; return true; }
    return tn_dec_fail(d, d->pos);
}
static TN_UNUSED bool tn_Unit_dec(tn_dec *d, tn_Unit *out) { *out = 0; return tn_dec_expect(d, "()"); }
static TN_UNUSED bool tn_Str_dec(tn_dec *d, tn_Str *out) {
    int64_t st = d->pos;
    if (!tn_dec_expect(d, "\"")) return false;
    tn_buf b = tn_buf_new();
    for (;;) {
        if (d->pos >= d->n) { tn_free(b.p); return tn_dec_fail(d, d->pos); }
        char c = d->p[d->pos++];
        if (c == '"') break;
        if (c != '\\') { tn_buf_add(&b, &c, 1); continue; }
        if (d->pos >= d->n) { tn_free(b.p); return tn_dec_fail(d, d->pos); }
        char e = d->p[d->pos++], v;
        switch (e) {
        case '"': v = '"'; break;
        case '\\': v = '\\'; break;
        case 'n': v = '\n'; break;
        case 't': v = '\t'; break;
        case 'r': v = '\r'; break;
        case 'u': {
            if (!tn_dec_expect(d, "{")) { tn_free(b.p); return false; }
            int64_t hs = d->pos, x = 0;
            while (d->pos < d->n && isxdigit((unsigned char)d->p[d->pos])) {
                char h = d->p[d->pos++];
                x = x * 16 + (h <= '9' ? h - '0' : (h | 0x20) - 'a' + 10);
                if (x > 255) x = 256;
            }
            if (d->pos == hs || x > 255) { tn_free(b.p); return tn_dec_fail(d, st); }
            if (!tn_dec_expect(d, "}")) { tn_free(b.p); return false; }
            v = (char)x;
            break;
        }
        default: tn_free(b.p); return tn_dec_fail(d, st);
        }
        tn_buf_add(&b, &v, 1);
    }
    tn_Str r = tn_buf_finish(&b);
    tn_buf chk = tn_buf_new();
    bool valid = tn_utf8_lossy(r.p, r.len, &chk);
    tn_free(chk.p);
    if (!valid) { tn_Str_release(r); return tn_dec_fail(d, st); }
    tn_buf q = tn_buf_new();
    tn_Str_show(&q, r, 0);
    if (!tn_dec_canon(d, &q, (tn_Str){d->p + st, d->pos - st, NULL}, st)) { tn_Str_release(r); return false; }
    *out = r;
    return true;
}
static TN_UNUSED tn_Str tn_dec_msg(tn_dec *d, const char *type) {
    char m[256];
    int n = snprintf(m, sizeof m, "cannot decode %s at byte %lld", type, (long long)(d->err >= 0 ? d->err : d->pos));
    return tn_str_new(m, n);
}

/* ---------- closures ---------- */

#ifdef TN_MT
/* copy: a deep copy of the closure's captures (or a dyn box), for sending */
typedef struct tn_env { int64_t rc; void (*drop)(struct tn_env *); struct tn_env *(*copy)(struct tn_env *); } tn_env;
#else
typedef struct tn_env { int64_t rc; void (*drop)(struct tn_env *); } tn_env;
#endif
typedef struct { void *f; tn_env *env; } tn_fn;
static inline tn_fn tn_fn_retain(tn_fn f) {
    if (f.env) f.env->rc++;
    return f;
}
static inline void tn_fn_release(tn_fn f) {
    if (f.env && --f.env->rc == 0) f.env->drop(f.env);
}
static TN_UNUSED void tn_fn_show(tn_buf *b, tn_fn f, int mode) { (void)f; (void)mode; tn_buf_cstr(b, "<fn>"); }
TN_INCOMPARABLE(tn_fn)

/* ---------- lists: NULL is the empty list ---------- */

#define TN_LIST_TYPE(L, T) struct L##_s { int64_t rc, len, cap; T data[]; };
#define TN_LIST_FUNCS(L, T)                                                              \
    static TN_UNUSED L L##_retain(L l) { if (l) l->rc++; return l; }                     \
    static TN_UNUSED void L##_release(L l) {                                             \
        if (l && --l->rc == 0) {                                                         \
            for (int64_t i = 0; i < l->len; i++) T##_release(l->data[i]);               \
            tn_free(l);                                                                     \
        }                                                                                \
    }                                                                                    \
    static TN_UNUSED L L##_alloc(int64_t cap) {                                          \
        if (cap < 4) cap = 4;                                                            \
        L l = tn_alloc(sizeof(struct L##_s) + sizeof(T) * (size_t)cap);                  \
        l->rc = 1; l->len = 0; l->cap = cap;                                             \
        return l;                                                                        \
    }                                                                                    \
    static inline int64_t L##_len(L l) { return l ? l->len : 0; }                        \
    static inline bool L##_same(L a, L b) { return a == b; }                             \
    static TN_UNUSED void L##_unique(L *p) {                                             \
        L l = *p;                                                                        \
        if (l && l->rc > 1) {                                                            \
            L c = L##_alloc(l->len);                                                     \
            for (int64_t i = 0; i < l->len; i++) c->data[i] = T##_retain(l->data[i]);    \
            c->len = l->len;                                                             \
            l->rc--;                                                                     \
            *p = c;                                                                      \
        }                                                                                \
    }                                                                                    \
    static TN_UNUSED void L##_reserve(L *p, int64_t extra) {                             \
        if (!*p) { *p = L##_alloc(extra); return; }                                      \
        L##_unique(p);                                                                   \
        L l = *p;                                                                        \
        if (l->len + extra > l->cap) {                                                   \
            int64_t cap = l->cap * 2;                                                    \
            if (cap < l->len + extra) cap = l->len + extra;                              \
            l = tn_realloc(l, sizeof(struct L##_s) + sizeof(T) * (size_t)cap);           \
            l->cap = cap;                                                                \
            *p = l;                                                                      \
        }                                                                                \
    }                                                                                    \
    static inline void L##_push(L *p, T x) {                                             \
        L l = *p;                                                                        \
        if (!(l && l->rc == 1 && l->len < l->cap)) { L##_reserve(p, 1); l = *p; }        \
        l->data[l->len++] = x;                                                           \
    }                                                                                    \
    static inline T *L##_at(L l, int64_t i, const char *loc) {                           \
        int64_t n = L##_len(l);                                                          \
        if (TN_UNLIKELY((uint64_t)i >= (uint64_t)n))                                     \
            tn_trapf(loc, "index %lld out of bounds for length %lld", (long long)i, (long long)n); \
        return &l->data[i];                                                              \
    }                                                                                    \
    static inline T *L##_at_mut(L *p, int64_t i, const char *loc) {                      \
        L##_at(*p, i, loc);                                                              \
        if ((*p)->rc > 1) L##_unique(p);                                                 \
        return &(*p)->data[i];                                                           \
    }                                                                                    \
    static TN_UNUSED bool L##_pop(L *p, T *out) {                                        \
        if (L##_len(*p) == 0) return false;                                              \
        L##_unique(p);                                                                   \
        *out = (*p)->data[--(*p)->len];                                                  \
        return true;                                                                     \
    }                                                                                    \
    static TN_UNUSED void L##_insert(L *p, int64_t i, T x, const char *loc) {            \
        int64_t n = L##_len(*p);                                                         \
        if (i < 0 || i > n)                                                              \
            tn_trapf(loc, "index %lld out of bounds for length %lld", (long long)i, (long long)n); \
        L##_reserve(p, 1);                                                               \
        L l = *p;                                                                        \
        memmove(&l->data[i + 1], &l->data[i], sizeof(T) * (size_t)(n - i));             \
        l->data[i] = x;                                                                  \
        l->len++;                                                                        \
    }                                                                                    \
    static TN_UNUSED T L##_remove(L *p, int64_t i, const char *loc) {                    \
        L##_at(*p, i, loc);                                                              \
        L##_unique(p);                                                                   \
        L l = *p;                                                                        \
        T x = l->data[i];                                                                \
        memmove(&l->data[i], &l->data[i + 1], sizeof(T) * (size_t)(l->len - i - 1));     \
        l->len--;                                                                        \
        return x;                                                                        \
    }                                                                                    \
    static TN_UNUSED void L##_clear(L *p) { L##_release(*p); *p = NULL; }                \
    static TN_UNUSED void L##_reverse(L *p) {                                            \
        if (L##_len(*p) < 2) return;                                                     \
        L##_unique(p);                                                                   \
        L l = *p;                                                                        \
        for (int64_t i = 0, j = l->len - 1; i < j; i++, j--) {                           \
            T t = l->data[i]; l->data[i] = l->data[j]; l->data[j] = t;                   \
        }                                                                                \
    }                                                                                    \
    static TN_UNUSED L L##_slice(L l, int64_t a, int64_t b, const char *loc) {           \
        int64_t n = L##_len(l);                                                          \
        if (a < 0 || b < a || b > n)                                                     \
            tn_trapf(loc, "slice [%lld, %lld) out of bounds for length %lld",            \
                     (long long)a, (long long)b, (long long)n);                          \
        if (a == b) return NULL;                                                         \
        L c = L##_alloc(b - a);                                                          \
        for (int64_t i = a; i < b; i++) c->data[i - a] = T##_retain(l->data[i]);         \
        c->len = b - a;                                                                  \
        return c;                                                                        \
    }                                                                                    \
    static TN_UNUSED L L##_concat(L a, L b) {                                            \
        int64_t n = L##_len(a), m = L##_len(b);                                          \
        if (n + m == 0) return NULL;                                                     \
        L c = L##_alloc(n + m);                                                          \
        for (int64_t i = 0; i < n; i++) c->data[i] = T##_retain(a->data[i]);             \
        for (int64_t i = 0; i < m; i++) c->data[n + i] = T##_retain(b->data[i]);         \
        c->len = n + m;                                                                  \
        return c;                                                                        \
    }                                                                                    \
    static TN_UNUSED bool L##_eq(L a, L b) {                                             \
        int64_t n = L##_len(a);                                                          \
        if (n != L##_len(b)) return false;                                               \
        for (int64_t i = 0; i < n; i++)                                                  \
            if (!T##_eq(a->data[i], b->data[i])) return false;                           \
        return true;                                                                     \
    }                                                                                    \
    static TN_UNUSED int L##_cmp(L a, L b) {                                             \
        int64_t n = L##_len(a), m = L##_len(b);                                          \
        for (int64_t i = 0; i < n && i < m; i++) {                                       \
            int c = T##_cmp(a->data[i], b->data[i]);                                     \
            if (c) return c;                                                             \
        }                                                                                \
        return n < m ? -1 : n > m;                                                       \
    }                                                                                    \
    static TN_UNUSED uint64_t L##_hash(L l) {                                            \
        uint64_t h = 7;                                                                  \
        for (int64_t i = 0; i < L##_len(l); i++) h = tn_mix(h * 31 + T##_hash(l->data[i])); \
        return h;                                                                        \
    }                                                                                    \
    static TN_UNUSED void L##_show(tn_buf *b, L l, int mode) {                           \
        (void)mode;                                                                       \
        tn_buf_add(b, "[", 1);                                                           \
        for (int64_t i = 0; i < L##_len(l); i++) {                                       \
            if (i) tn_buf_add(b, ", ", 2);                                               \
            T##_show(b, l->data[i], mode & TN_FULL);                                              \
        }                                                                                \
        tn_buf_add(b, "]", 1);                                                           \
    }                                                                                    \
    static TN_UNUSED bool L##_dec(tn_dec *d, L *out) {                                   \
        if (!tn_dec_expect(d, "[")) return false;                                        \
        L l = NULL;                                                                      \
        if (!tn_dec_lit(d, "]")) {                                                       \
            for (;;) {                                                                   \
                T x;                                                                     \
                if (!T##_dec(d, &x)) { L##_release(l); return false; }                   \
                L##_push(&l, x);                                                         \
                if (tn_dec_lit(d, ", ")) continue;                                       \
                if (!tn_dec_expect(d, "]")) { L##_release(l); return false; }            \
                break;                                                                   \
            }                                                                            \
        }                                                                                \
        *out = l;                                                                        \
        return true;                                                                     \
    }                                                                                    \
    /* stable merge sort of xs by keys (keys == xs when sorting by value) */             \
    static TN_UNUSED void L##_msort(T *xs, T *tmp, int64_t n) {                          \
        if (n < 2) return;                                                               \
        if (n <= 16) {                                                                   \
            for (int64_t i = 1; i < n; i++) {                                            \
                T x = xs[i];                                                             \
                int64_t j = i;                                                           \
                while (j > 0 && T##_cmp(xs[j - 1], x) > 0) { xs[j] = xs[j - 1]; j--; }   \
                xs[j] = x;                                                               \
            }                                                                            \
            return;                                                                      \
        }                                                                                \
        int64_t h = n / 2;                                                               \
        L##_msort(xs, tmp, h);                                                           \
        L##_msort(xs + h, tmp, n - h);                                                   \
        if (T##_cmp(xs[h - 1], xs[h]) <= 0) return;                                      \
        memcpy(tmp, xs, sizeof(T) * (size_t)h);                                          \
        int64_t i = 0, j = h, k = 0;                                                     \
        while (i < h && j < n) xs[k++] = T##_cmp(xs[j], tmp[i]) < 0 ? xs[j++] : tmp[i++]; \
        while (i < h) xs[k++] = tmp[i++];                                                \
    }                                                                                    \
    static TN_UNUSED void L##_sort(L *p) {                                               \
        if (L##_len(*p) < 2) return;                                                     \
        L##_unique(p);                                                                   \
        T *tmp = tn_alloc(sizeof(T) * (size_t)((*p)->len / 2 + 1));                      \
        L##_msort((*p)->data, tmp, (*p)->len);                                           \
        tn_free(tmp);                                                                       \
    }

/* ---------- maps: insertion-ordered hash maps; NULL is the empty map ---------- */

#define TN_MAP_TYPE(M, K, V)                                                             \
    struct M##_e { K k; V v; uint64_t h; bool live; };                                   \
    struct M##_s { int64_t rc, len, n, cap, icap, last, last_slot; struct M##_e *e; int32_t *idx; };
#define TN_MAP_FUNCS(M, K, V)                                                            \
    static TN_UNUSED M M##_retain(M m) { if (m) m->rc++; return m; }                     \
    static TN_UNUSED void M##_release(M m) {                                             \
        if (m && --m->rc == 0) {                                                         \
            for (int64_t i = 0; i < m->n; i++)                                           \
                if (m->e[i].live) { K##_release(m->e[i].k); V##_release(m->e[i].v); }    \
            tn_free(m->e); tn_free(m->idx); tn_free(m);                                           \
        }                                                                                \
    }                                                                                    \
    static inline int64_t M##_len(M m) { return m ? m->len : 0; }                        \
    static TN_UNUSED void M##_reindex(M m, int64_t icap) {                               \
        tn_free(m->idx);                                                                    \
        m->icap = icap;                                                                  \
        m->idx = tn_alloc(sizeof(int32_t) * (size_t)icap);                               \
        for (int64_t i = 0; i < icap; i++) m->idx[i] = -1;                               \
        int64_t w = 0;                                                                   \
        for (int64_t r = 0; r < m->n; r++) {                                             \
            if (!m->e[r].live) continue;                                                 \
            m->e[w] = m->e[r];                                                           \
            uint64_t s = m->e[w].h & (uint64_t)(icap - 1);                               \
            while (m->idx[s] != -1) s = (s + 1) & (uint64_t)(icap - 1);                  \
            m->idx[s] = (int32_t)w++;                                                    \
        }                                                                                \
        m->n = w;                                                                        \
        m->last = -1;                                                                    \
    }                                                                                    \
    /* small maps (at most TN_MAP_SMALL entries) have no index: lookups scan */         \
    static TN_UNUSED void M##_compact(M m) {                                             \
        int64_t w = 0;                                                                   \
        for (int64_t r = 0; r < m->n; r++) if (m->e[r].live) m->e[w++] = m->e[r];        \
        m->n = w;                                                                        \
        m->last = -1;                                                                    \
    }                                                                                    \
    static TN_UNUSED M M##_alloc(int64_t cap) {                                          \
        M m = tn_alloc(sizeof(struct M##_s));                                            \
        m->rc = 1; m->len = 0; m->n = 0; m->cap = cap < 4 ? 4 : cap;                      \
        m->e = tn_alloc(sizeof(struct M##_e) * (size_t)m->cap);                          \
        m->idx = NULL; m->icap = 0; m->last = -1;                                        \
        if (cap > TN_MAP_SMALL) {                                                        \
            int64_t ic = 16;                                                             \
            while (ic * 3 < m->cap * 4) ic *= 2;                                         \
            M##_reindex(m, ic);                                                          \
        }                                                                                \
        return m;                                                                        \
    }                                                                                    \
    static TN_UNUSED void M##_unique(M *p) {                                             \
        M m = *p;                                                                        \
        if (!m) { *p = M##_alloc(4); return; }                                           \
        if (m->rc == 1) return;                                                          \
        M c = M##_alloc(m->len);                                                         \
        for (int64_t i = 0; i < m->n; i++)                                               \
            if (m->e[i].live) {                                                          \
                struct M##_e x = m->e[i];                                                \
                x.k = K##_retain(x.k); x.v = V##_retain(x.v);                            \
                c->e[c->n++] = x;                                                        \
            }                                                                            \
        c->len = c->n;                                                                   \
        if (c->idx) M##_reindex(c, c->icap);                                             \
        m->rc--;                                                                         \
        *p = c;                                                                          \
    }                                                                                    \
    /* index of the entry holding k, or -1; *slot gets the probe position */             \
    static TN_UNUSED int64_t M##_find(M m, K k, uint64_t h, int64_t *slot) {             \
        if (m->last >= 0 && m->e[m->last].h == h && K##_eq(m->e[m->last].k, k)) {        \
            if (slot) *slot = m->last_slot;                                              \
            return m->last;                                                              \
        }                                                                                \
        if (!m->idx) {                                                                   \
            if (slot) *slot = -1;                                                        \
            for (int64_t j = 0; j < m->n; j++)                                           \
                if (m->e[j].live && m->e[j].h == h && K##_eq(m->e[j].k, k)) {            \
                    m->last = j; m->last_slot = -1;                                      \
                    return j;                                                            \
                }                                                                        \
            return -1;                                                                   \
        }                                                                                \
        uint64_t s = h & (uint64_t)(m->icap - 1);                                        \
        int64_t tomb = -1;                                                               \
        for (;;) {                                                                       \
            int64_t j = m->idx[s];                                                       \
            if (j == -1) { if (slot) *slot = tomb >= 0 ? tomb : (int64_t)s; return -1; }  \
            if (j == -2) { if (tomb < 0) tomb = (int64_t)s; }                            \
            else if (m->e[j].h == h && K##_eq(m->e[j].k, k)) {                           \
                m->last = j; m->last_slot = (int64_t)s;                                  \
                if (slot) *slot = (int64_t)s;                                            \
                return j;                                                                \
            }                                                                            \
            s = (s + 1) & (uint64_t)(m->icap - 1);                                       \
        }                                                                                \
    }                                                                                    \
    static inline uint64_t M##_khash(M m, K k) {                                          \
        if (m->last >= 0 && K##_same(m->e[m->last].k, k)) return m->e[m->last].h;       \
        return K##_hash(k);                                                              \
    }                                                                                    \
    static TN_UNUSED V *M##_get(M m, K k) {                                              \
        if (!m || !m->len) return NULL;                                                  \
        if (!m->idx) { /* small map: compare keys, no hashing */                         \
            for (int64_t j = 0; j < m->n; j++)                                           \
                if (m->e[j].live && K##_eq(m->e[j].k, k)) return &m->e[j].v;             \
            return NULL;                                                                 \
        }                                                                                \
        int64_t j = M##_find(m, k, M##_khash(m, k), NULL);                                \
        return j < 0 ? NULL : &m->e[j].v;                                                \
    }                                                                                    \
    static TN_UNUSED V *M##_at(M m, K k, const char *loc) {                              \
        V *v = M##_get(m, k);                                                            \
        if (TN_UNLIKELY(!v)) {                                                           \
            tn_buf b = tn_buf_new();                                                     \
            tn_buf_cstr(&b, "key not found: ");                                          \
            K##_show(&b, k, 0);                                                      \
            tn_buf_add(&b, "", 1);                                                       \
            tn_trap(b.p + sizeof(tn_rc), loc);                                           \
        }                                                                                \
        return v;                                                                        \
    }                                                                                    \
    /* slot for k (taking ownership of k); inserts a zero value if absent */             \
    static TN_UNUSED V *M##_slot(M *p, K k, bool *fresh) {                               \
        M##_unique(p);                                                                   \
        M m = *p;                                                                        \
        uint64_t h = M##_khash(m, k);                                                     \
        int64_t s;                                                                       \
        int64_t j = M##_find(m, k, h, &s);                                               \
        if (j >= 0) { K##_release(k); *fresh = false; return &m->e[j].v; }              \
        if (!m->idx) {                                                                   \
            if (m->n == m->cap && m->len < m->n) M##_compact(m);                         \
            if (m->n == m->cap) {                                                        \
                m->cap *= 2;                                                             \
                m->e = tn_realloc(m->e, sizeof(struct M##_e) * (size_t)m->cap);          \
            }                                                                            \
            if (m->len + 1 <= TN_MAP_SMALL) {                                            \
                j = m->n++;                                                              \
                m->e[j].k = k; m->e[j].h = h; m->e[j].live = true;                       \
                memset(&m->e[j].v, 0, sizeof(V));                                        \
                m->last = j; m->last_slot = -1;                                          \
                m->len++;                                                                \
                *fresh = true;                                                           \
                return &m->e[j].v;                                                       \
            }                                                                            \
            M##_reindex(m, 32);                                                          \
            M##_find(m, k, h, &s);                                                       \
        }                                                                                \
        if ((m->n + 1) * 4 > m->icap * 3 || m->n == m->cap) {                            \
            if (m->n == m->cap) {                                                        \
                m->cap *= 2;                                                             \
                m->e = tn_realloc(m->e, sizeof(struct M##_e) * (size_t)m->cap);          \
            }                                                                            \
            int64_t ic = m->icap;                                                        \
            while ((m->len + 1) * 4 > ic * 3) ic *= 2;                                   \
            M##_reindex(m, ic);                                                          \
            M##_find(m, k, h, &s);                                                       \
        }                                                                                \
        j = m->n++;                                                                      \
        m->e[j].k = k; m->e[j].h = h; m->e[j].live = true;                               \
        memset(&m->e[j].v, 0, sizeof(V));                                                \
        if (TN_UNLIKELY(j >= INT32_MAX)) tn_oom();                                     \
        m->idx[s] = (int32_t)j;                                                          \
        m->last = j; m->last_slot = s;                                                   \
        m->len++;                                                                        \
        *fresh = true;                                                                   \
        return &m->e[j].v;                                                               \
    }                                                                                    \
    static TN_UNUSED V *M##_at_mut(M *p, K k, const char *loc) {                         \
        M##_at(*p, k, loc);                                                              \
        bool fresh;                                                                      \
        return M##_slot(p, K##_retain(k), &fresh);                                       \
    }                                                                                    \
    static TN_UNUSED void M##_insert(M *p, K k, V v) {                                   \
        bool fresh;                                                                      \
        V *s = M##_slot(p, k, &fresh);                                                   \
        if (!fresh) V##_release(*s);                                                     \
        *s = v;                                                                          \
    }                                                                                    \
    static TN_UNUSED bool M##_remove(M *p, K k, V *out) {                                \
        if (!*p || !(*p)->len) return false;                                             \
        M##_unique(p);                                                                   \
        M m = *p;                                                                        \
        int64_t s;                                                                       \
        int64_t j = M##_find(m, k, M##_khash(m, k), &s);                                  \
        if (j < 0) return false;                                                         \
        if (m->idx) m->idx[s] = -2;                                                      \
        m->e[j].live = false;                                                            \
        m->last = -1;                                                                    \
        K##_release(m->e[j].k);                                                          \
        *out = m->e[j].v;                                                                \
        m->len--;                                                                        \
        if (m->n > 8 && m->len * 2 < m->n) {                                             \
            if (m->idx) M##_reindex(m, m->icap); else M##_compact(m);                    \
        }                                                                                \
        return true;                                                                     \
    }                                                                                    \
    static TN_UNUSED bool M##_eq(M a, M b) {                                             \
        if (M##_len(a) != M##_len(b)) return false;                                      \
        if (!M##_len(a)) return true;                                                    \
        for (int64_t i = 0; i < a->n; i++) {                                             \
            if (!a->e[i].live) continue;                                                 \
            V *v = M##_get(b, a->e[i].k);                                                \
            if (!v || !V##_eq(*v, a->e[i].v)) return false;                              \
        }                                                                                \
        return true;                                                                     \
    }                                                                                    \
    static TN_UNUSED int M##_cmp(M a, M b) {                                             \
        (void)a; (void)b;                                                                \
        tn_trap("maps are not ordered", tn_cur_loc);                                     \
    }                                                                                    \
    static TN_UNUSED uint64_t M##_hash(M m) { return (uint64_t)M##_len(m); }            \
    static inline bool M##_same(M a, M b) { return a == b; }                             \
    static TN_UNUSED bool M##_dec(tn_dec *d, M *out) {                                   \
        M m = NULL;                                                                      \
        if (tn_dec_lit(d, "[:]")) { *out = NULL; return true; }                          \
        if (!tn_dec_expect(d, "[")) return false;                                        \
        for (;;) {                                                                       \
            int64_t ks = d->pos;                                                         \
            K k; V v;                                                                    \
            if (!K##_dec(d, &k)) { M##_release(m); return false; }                       \
            if (M##_get(m, k)) { K##_release(k); M##_release(m); return tn_dec_fail(d, ks); } \
            if (!tn_dec_expect(d, ": ")) { K##_release(k); M##_release(m); return false; } \
            if (!V##_dec(d, &v)) { K##_release(k); M##_release(m); return false; }       \
            M##_insert(&m, k, v);                                                        \
            if (tn_dec_lit(d, ", ")) continue;                                           \
            if (!tn_dec_expect(d, "]")) { M##_release(m); return false; }                \
            break;                                                                       \
        }                                                                                \
        *out = m;                                                                        \
        return true;                                                                     \
    }                                                                                    \
    static TN_UNUSED void M##_show(tn_buf *b, M m, int mode) {                           \
        (void)mode;                                                                       \
        if (!M##_len(m)) { tn_buf_cstr(b, "[:]"); return; }                              \
        tn_buf_add(b, "[", 1);                                                           \
        bool first = true;                                                               \
        for (int64_t i = 0; i < m->n; i++) {                                             \
            if (!m->e[i].live) continue;                                                 \
            if (!first) tn_buf_add(b, ", ", 2);                                          \
            first = false;                                                               \
            K##_show(b, m->e[i].k, mode & TN_FULL);                                               \
            tn_buf_add(b, ": ", 2);                                                      \
            V##_show(b, m->e[i].v, mode & TN_FULL);                                               \
        }                                                                                \
        tn_buf_add(b, "]", 1);                                                           \
    }

/* List[Str] is used by the runtime itself (split, lines, args, fs listing). */
typedef struct tn_List_Str_s *tn_List_Str;
TN_LIST_TYPE(tn_List_Str, tn_Str)
TN_LIST_FUNCS(tn_List_Str, tn_Str)

/* List[Int] is the runtime's byte list (every element 0..255). */
typedef struct tn_List_Int_s *tn_List_Int;
TN_LIST_TYPE(tn_List_Int, tn_Int)
TN_LIST_FUNCS(tn_List_Int, tn_Int)
/* Append n bytes to a list whose capacity the caller has reserved. */
static inline void tn_bytes_put(tn_List_Int l, const char *p, int64_t n) {
    const unsigned char *s = (const unsigned char *)p;
    tn_Int *d = l->data + l->len;
    for (int64_t i = 0; i < n; i++) d[i] = s[i];
    l->len += n;
}
static TN_UNUSED tn_List_Int tn_bytes_list(const char *p, int64_t n) {
    if (n == 0) return NULL;
    tn_List_Int l = tn_List_Int_alloc(n);
    tn_bytes_put(l, p, n);
    return l;
}
/* The bytes of l as a string; false (and *bad = the index) if an element is not in 0..255. */
static TN_UNUSED bool tn_list_to_bytes(tn_List_Int l, tn_Str *out, int64_t *bad) {
    int64_t n = tn_List_Int_len(l);
    tn_rc *o = tn_alloc(sizeof(tn_rc) + (size_t)n);
    unsigned char *d = (unsigned char *)(o + 1);
    for (int64_t i = 0; i < n; i++) {
        tn_Int v = l->data[i];
        if ((uint64_t)v > 255) { tn_free(o); *bad = i; return false; }
        d[i] = (unsigned char)v;
    }
    o->rc = 1;
    o->cap = n;
    *out = (tn_Str){(const char *)d, n, o};
    return true;
}
static TN_UNUSED tn_Str tn_bytes_of(tn_List_Int l, const char *loc) {
    tn_Str s;
    int64_t i;
    if (!tn_list_to_bytes(l, &s, &i))
        tn_trapf(loc, "byte %lld at index %lld is not in 0..255", (long long)l->data[i], (long long)i);
    return s;
}

/* ---------- string operations ---------- */

static inline TN_UNUSED tn_Int tn_str_byte(tn_Str s, tn_Int i, const char *loc) {
    if ((uint64_t)i >= (uint64_t)s.len)
        tn_trapf(loc, "index %lld out of bounds for length %lld", (long long)i, (long long)s.len);
    return (uint8_t)s.p[i];
}
static inline bool tn_is_boundary(tn_Str s, int64_t i) {
    return i == 0 || i == s.len || ((uint8_t)s.p[i] & 0xC0) != 0x80;
}
static TN_UNUSED tn_Str tn_str_slice(tn_Str s, tn_Int a, tn_Int b, const char *loc) {
    if (a < 0 || b < a || b > s.len)
        tn_trapf(loc, "slice [%lld, %lld) out of bounds for length %lld", (long long)a, (long long)b, (long long)s.len);
    if (!tn_is_boundary(s, a) || !tn_is_boundary(s, b))
        tn_trapf(loc, "slice [%lld, %lld) is not on a character boundary", (long long)a, (long long)b);
    return tn_str_view(s, a, b);
}
static TN_UNUSED int64_t tn_str_find(tn_Str s, tn_Str sub, int64_t from) {
    if (sub.len == 0) return from <= s.len ? from : -1;
    for (int64_t i = from; i + sub.len <= s.len; i++)
        if (s.p[i] == sub.p[0] && memcmp(s.p + i, sub.p, (size_t)sub.len) == 0) return i;
    return -1;
}
static TN_UNUSED tn_List_Str tn_str_split(tn_Str s, tn_Str sep, const char *loc) {
    if (sep.len == 0) tn_trap("split with an empty separator", loc);
    tn_List_Str out = NULL;
    int64_t start = 0;
    for (;;) {
        int64_t i = tn_str_find(s, sep, start);
        if (i < 0) break;
        tn_List_Str_push(&out, tn_str_view(s, start, i));
        start = i + sep.len;
    }
    tn_List_Str_push(&out, tn_str_view(s, start, s.len));
    return out;
}
/* Borrowed views for fused `for w in s.words()` / `s.lines()` loops. */
static inline bool tn_next_word(tn_Str s, int64_t *pos, tn_Str *out) {
    int64_t i = *pos;
    while (i < s.len && (s.p[i] == ' ' || s.p[i] == '\t' || s.p[i] == '\n' || s.p[i] == '\r')) i++;
    if (i >= s.len) return false;
    int64_t st = i;
    while (i < s.len && !(s.p[i] == ' ' || s.p[i] == '\t' || s.p[i] == '\n' || s.p[i] == '\r')) i++;
    *out = (tn_Str){s.p + st, i - st, s.o};
    *pos = i;
    return true;
}
static inline bool tn_next_line(tn_Str s, int64_t *pos, tn_Str *out) {
    int64_t st = *pos;
    if (st >= s.len) return false;
    const char *nl = memchr(s.p + st, '\n', (size_t)(s.len - st));
    int64_t e = nl ? nl - s.p : s.len;
    *pos = nl ? e + 1 : s.len;
    if (e > st && s.p[e - 1] == '\r') e--; /* one trailing "\r", as read_line */
    *out = (tn_Str){s.p + st, e - st, s.o};
    return true;
}
static TN_UNUSED tn_List_Str tn_str_words(tn_Str s) {
    tn_List_Str out = NULL;
    int64_t i = 0;
    while (i < s.len) {
        while (i < s.len && (s.p[i] == ' ' || s.p[i] == '\t' || s.p[i] == '\n' || s.p[i] == '\r')) i++;
        int64_t st = i;
        while (i < s.len && !(s.p[i] == ' ' || s.p[i] == '\t' || s.p[i] == '\n' || s.p[i] == '\r')) i++;
        if (i > st) tn_List_Str_push(&out, tn_str_view(s, st, i));
    }
    return out;
}
/* Split on "\n", drop a final empty line, remove one trailing "\r" from every line. */
static TN_UNUSED tn_List_Str tn_str_lines(tn_Str s) {
    tn_List_Str out = NULL;
    int64_t pos = 0;
    tn_Str l;
    while (tn_next_line(s, &pos, &l)) tn_List_Str_push(&out, tn_str_view(s, l.p - s.p, l.p - s.p + l.len));
    return out;
}
static inline bool tn_is_space(char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f'; }
static TN_UNUSED tn_Str tn_str_trim(tn_Str s, bool front, bool back) {
    int64_t a = 0, b = s.len;
    if (front) while (a < b && tn_is_space(s.p[a])) a++;
    if (back) while (b > a && tn_is_space(s.p[b - 1])) b--;
    return tn_str_view(s, a, b);
}
static TN_UNUSED bool tn_str_starts(tn_Str s, tn_Str p) {
    return p.len <= s.len && memcmp(s.p, p.p, (size_t)p.len) == 0;
}
static TN_UNUSED bool tn_str_ends(tn_Str s, tn_Str p) {
    return p.len <= s.len && memcmp(s.p + s.len - p.len, p.p, (size_t)p.len) == 0;
}
static TN_UNUSED bool tn_str_to_int(tn_Str s, tn_Int *out) {
    int64_t i = 0;
    bool neg = false;
    if (i < s.len && (s.p[i] == '+' || s.p[i] == '-')) neg = s.p[i++] == '-';
    if (i == s.len) return false;
    uint64_t v = 0, lim = neg ? (uint64_t)INT64_MAX + 1 : (uint64_t)INT64_MAX;
    for (; i < s.len; i++) {
        char c = s.p[i];
        if (c < '0' || c > '9') return false;
        uint64_t d = (uint64_t)(c - '0');
        if (v > (lim - d) / 10) return false;
        v = v * 10 + d;
    }
    *out = neg ? (tn_Int)(0 - v) : (tn_Int)v;
    return true;
}
/* Same grammar as interp::parse_float. */
static TN_UNUSED bool tn_str_to_float(tn_Str s, tn_Float *out) {
    char tmp[64];
    if (s.len == 0 || s.len >= (int64_t)sizeof tmp) {
        if (s.len == 0) return false;
    }
    int64_t i = 0, n = s.len;
    const char *p = s.p;
    if (i < n && (p[i] == '+' || p[i] == '-')) i++;
    int64_t rest = n - i;
    char low[16];
    if (rest <= 8) {
        for (int64_t k = 0; k < rest; k++) low[k] = (char)(p[i + k] | 0x20);
        low[rest] = 0;
        if (!strcmp(low, "inf") || !strcmp(low, "infinity") || !strcmp(low, "nan")) {
            bool neg = p[0] == '-';
            *out = low[0] == 'n' ? (neg ? -NAN : NAN) : (neg ? -INFINITY : INFINITY);
            return true;
        }
    }
    int64_t nd = 0;
    while (i < n && p[i] >= '0' && p[i] <= '9') i++, nd++;
    if (i < n && p[i] == '.') {
        i++;
        while (i < n && p[i] >= '0' && p[i] <= '9') i++, nd++;
    }
    if (nd == 0) return false;
    if (i < n && (p[i] == 'e' || p[i] == 'E')) {
        i++;
        if (i < n && (p[i] == '+' || p[i] == '-')) i++;
        int64_t es = i;
        while (i < n && p[i] >= '0' && p[i] <= '9') i++;
        if (i == es) return false;
    }
    if (i != n) return false;
    char *z = n < (int64_t)sizeof tmp ? tmp : tn_alloc((size_t)n + 1);
    memcpy(z, p, (size_t)n);
    z[n] = 0;
    *out = strtod(z, NULL);
    if (z != tmp) tn_free(z);
    return true;
}
/* Consumes s: converts in place when s is the only reference to its buffer. */
static TN_UNUSED tn_Str tn_str_case_move(tn_Str s, bool up) {
    tn_Str r = s;
    if (!(s.o && s.o->rc == 1)) {
        r = tn_str_new(s.p, s.len);
        tn_Str_release(s);
    }
    char *q = (char *)r.p;
    for (int64_t i = 0; i < r.len; i++) {
        char c = q[i];
        if (up && c >= 'a' && c <= 'z') q[i] = (char)(c - 32);
        if (!up && c >= 'A' && c <= 'Z') q[i] = (char)(c + 32);
    }
    return r;
}
static TN_UNUSED tn_Str tn_str_case(tn_Str s, bool up) {
    tn_Str r = tn_str_new(s.p, s.len);
    char *q = (char *)r.p;
    for (int64_t i = 0; i < s.len; i++) {
        char c = q[i];
        if (up && c >= 'a' && c <= 'z') q[i] = (char)(c - 32);
        if (!up && c >= 'A' && c <= 'Z') q[i] = (char)(c + 32);
    }
    return r;
}
static TN_UNUSED tn_Str tn_str_replace(tn_Str s, tn_Str from, tn_Str to, const char *loc) {
    if (from.len == 0) tn_trap("replace with an empty pattern", loc);
    int64_t i = tn_str_find(s, from, 0);
    if (i < 0) return tn_Str_retain(s);
    tn_buf b = tn_buf_new();
    int64_t start = 0;
    while (i >= 0) {
        tn_buf_add(&b, s.p + start, i - start);
        tn_buf_str(&b, to);
        start = i + from.len;
        i = tn_str_find(s, from, start);
    }
    tn_buf_add(&b, s.p + start, s.len - start);
    return tn_buf_finish(&b);
}
static TN_UNUSED tn_Str tn_str_concat(tn_Str a, tn_Str b) {
    if (a.len == 0) return tn_Str_retain(b);
    if (b.len == 0) return tn_Str_retain(a);
    tn_rc *o = tn_alloc(sizeof(tn_rc) + (size_t)(a.len + b.len));
    o->rc = 1;
    o->cap = a.len + b.len;
    memcpy(o + 1, a.p, (size_t)a.len);
    memcpy((char *)(o + 1) + a.len, b.p, (size_t)b.len);
    return (tn_Str){(const char *)(o + 1), a.len + b.len, o};
}
/* x += y. Appends in place when x is the only reference to its buffer and
 * starts at its beginning (amortized O(1)); otherwise copies. */
static TN_UNUSED void tn_str_append(tn_Str *x, tn_Str y) {
    tn_rc *o = x->o;
    if (y.len == 0) return;
    if (o && o->rc == 1 && x->p == (const char *)(o + 1) && y.o != o) {
        if (x->len + y.len > o->cap) {
            int64_t cap = o->cap * 2;
            if (cap < x->len + y.len) cap = x->len + y.len;
            if (cap < 32) cap = 32;
            o = tn_realloc(o, sizeof(tn_rc) + (size_t)cap);
            o->cap = cap;
            x->o = o;
            x->p = (const char *)(o + 1);
        }
        memcpy((char *)(o + 1) + x->len, y.p, (size_t)y.len);
        x->len += y.len;
        return;
    }
    tn_Str r = tn_str_concat(*x, y);
    tn_Str_release(*x);
    *x = r;
}
static TN_UNUSED tn_Int tn_str_char_count(tn_Str s) {
    tn_Int n = 0; /* code points: every byte that is not a UTF-8 continuation byte */
    for (int64_t i = 0; i < s.len; i++) n += ((uint8_t)s.p[i] & 0xC0) != 0x80;
    return n;
}
static TN_UNUSED tn_List_Str tn_str_chars(tn_Str s) {
    tn_List_Str out = NULL;
    int64_t i = 0;
    while (i < s.len) {
        int64_t j = i + 1;
        while (j < s.len && ((uint8_t)s.p[j] & 0xC0) == 0x80) j++;
        tn_List_Str_push(&out, tn_str_view(s, i, j));
        i = j;
    }
    return out;
}
static TN_UNUSED tn_Str tn_str_join(tn_List_Str l, tn_Str sep) {
    tn_buf b = tn_buf_new();
    for (int64_t i = 0; i < tn_List_Str_len(l); i++) {
        if (i) tn_buf_str(&b, sep);
        tn_buf_str(&b, l->data[i]);
    }
    return tn_buf_finish(&b);
}
static TN_UNUSED tn_Str tn_int_char(tn_Int c, const char *loc) {
    if (c < 0 || c > 0x10FFFF || (c >= 0xD800 && c <= 0xDFFF))
        tn_trapf(loc, "invalid character code %lld", (long long)c);
    char t[4];
    int n;
    if (c < 0x80) { t[0] = (char)c; n = 1; }
    else if (c < 0x800) { t[0] = (char)(0xC0 | (c >> 6)); t[1] = (char)(0x80 | (c & 0x3F)); n = 2; }
    else if (c < 0x10000) {
        t[0] = (char)(0xE0 | (c >> 12)); t[1] = (char)(0x80 | ((c >> 6) & 0x3F));
        t[2] = (char)(0x80 | (c & 0x3F)); n = 3;
    } else {
        t[0] = (char)(0xF0 | (c >> 18)); t[1] = (char)(0x80 | ((c >> 12) & 0x3F));
        t[2] = (char)(0x80 | ((c >> 6) & 0x3F)); t[3] = (char)(0x80 | (c & 0x3F)); n = 4;
    }
    return tn_str_new(t, n);
}
static TN_UNUSED tn_Str tn_float_fixed(tn_Float x, tn_Int d) {
    char t[512];
    int n = tn_float_fixed_into(t, x, d);
    return tn_str_new(t, n);
}
static TN_UNUSED tn_Int tn_float_to_int(tn_Float x, const char *loc) {
    if (!(x >= -9223372036854775808.0 && x < 9223372036854775808.0))
        tn_trap("float to int conversion out of range", loc);
    return (tn_Int)x;
}

/* Decode UTF-8, replacing each maximal invalid subpart with U+FFFD (as Rust's
 * String::from_utf8_lossy does). Returns false if the input was invalid. */
static TN_UNUSED bool tn_utf8_lossy(const char *p, int64_t n, tn_buf *out) {
    bool ok = true;
    int64_t i = 0, run = 0; /* bytes [run, i) are valid and not yet copied */
    const unsigned char *s = (const unsigned char *)p;
    tn_buf_grow(out, n);
    while (i < n) {
        unsigned c = s[i];
        int need;
        unsigned lo = 0x80, hi = 0xBF;
        if (c < 0x80) { i++; continue; }
        else if (c >= 0xC2 && c <= 0xDF) need = 1;
        else if (c == 0xE0) { need = 2; lo = 0xA0; }
        else if (c >= 0xE1 && c <= 0xEC) need = 2;
        else if (c == 0xED) { need = 2; hi = 0x9F; }
        else if (c >= 0xEE && c <= 0xEF) need = 2;
        else if (c == 0xF0) { need = 3; lo = 0x90; }
        else if (c >= 0xF1 && c <= 0xF3) need = 3;
        else if (c == 0xF4) { need = 3; hi = 0x8F; }
        else {
            tn_buf_add(out, (const char *)s + run, i - run);
            tn_buf_add(out, "\xEF\xBF\xBD", 3);
            ok = false;
            run = ++i;
            continue;
        }
        int64_t j = i + 1;
        int got = 0;
        while (got < need && j < n) {
            unsigned d = s[j];
            if (got == 0 ? (d < lo || d > hi) : (d < 0x80 || d > 0xBF)) break;
            j++, got++;
        }
        if (got != need) {
            tn_buf_add(out, (const char *)s + run, i - run);
            tn_buf_add(out, "\xEF\xBF\xBD", 3);
            ok = false;
            run = j;
        }
        i = j;
    }
    tn_buf_add(out, (const char *)s + run, n - run);
    return ok;
}

/* ---------- console ---------- */

/* Input buffer; allocated with room for a tn_rc header so read_all can hand
 * the bytes over as a string without copying. */
TN_STATE char *tn_in_mem, *tn_in_buf;
TN_STATE int64_t tn_in_len, tn_in_pos, tn_in_cap;
TN_STATE bool tn_in_eof;

static bool tn_in_fill(void) {
    if (tn_in_eof) return false;
    if (!tn_in_mem) {
        tn_in_cap = 1 << 16;
        tn_in_mem = tn_alloc(sizeof(tn_rc) + (size_t)tn_in_cap);
        tn_in_buf = tn_in_mem + sizeof(tn_rc);
    }
    if (tn_in_pos > 0) {
        memmove(tn_in_buf, tn_in_buf + tn_in_pos, (size_t)(tn_in_len - tn_in_pos));
        tn_in_len -= tn_in_pos;
        tn_in_pos = 0;
    }
    if (tn_in_len == tn_in_cap) {
        tn_in_cap *= 2;
        tn_in_mem = tn_realloc(tn_in_mem, sizeof(tn_rc) + (size_t)tn_in_cap);
        tn_in_buf = tn_in_mem + sizeof(tn_rc);
    }
    ssize_t r;
    do r = read(0, tn_in_buf + tn_in_len, (size_t)(tn_in_cap - tn_in_len));
    while (r < 0 && errno == EINTR);
    if (r <= 0) { tn_in_eof = true; return false; }
    tn_in_len += r;
    return true;
}
static bool tn_read_line_u(tn_Str *out) {
    tn_flush();
    int64_t scan = tn_in_pos;
    for (;;) {
        for (; scan < tn_in_len; scan++)
            if (tn_in_buf[scan] == '\n') goto found;
        int64_t off = scan - tn_in_pos;
        bool more = tn_in_fill(); /* may move the buffered bytes */
        scan = tn_in_pos + off;
        if (!more) break;
    }
    if (tn_in_pos == tn_in_len) return false;
found:;
    int64_t end = scan, next = scan < tn_in_len ? scan + 1 : scan;
    if (end > tn_in_pos && tn_in_buf[end - 1] == '\r') end--; /* one "\r" off every line, also a last one without "\n" */
    tn_buf b = tn_buf_new();
    tn_utf8_lossy(tn_in_buf + tn_in_pos, end - tn_in_pos, &b);
    tn_in_pos = next;
    *out = tn_buf_finish(&b);
    return true;
}
static bool tn_utf8_valid(const char *p, int64_t n) {
    tn_buf scratch = {0};
    for (int64_t i = 0; i < n; i++)
        if ((unsigned char)p[i] >= 0x80) {
            scratch = tn_buf_new();
            bool ok = tn_utf8_lossy(p + i, n - i, &scratch);
            tn_free(scratch.p);
            return ok;
        }
    return true;
}
static tn_Str tn_read_all_u(void) {
    tn_flush();
    while (tn_in_fill()) {}
    if (tn_in_mem && tn_in_pos == 0 && tn_utf8_valid(tn_in_buf, tn_in_len)) {
        tn_rc *o = (tn_rc *)tn_in_mem;
        o->rc = 1;
        o->cap = tn_in_cap;
        tn_Str r = {tn_in_buf, tn_in_len, o};
        tn_in_mem = tn_in_buf = NULL;
        tn_in_len = tn_in_pos = 0;
        return r;
    }
    tn_buf b = tn_buf_new();
    if (tn_in_mem) tn_utf8_lossy(tn_in_buf + tn_in_pos, tn_in_len - tn_in_pos, &b);
    tn_in_pos = tn_in_len;
    return tn_buf_finish(&b);
}
static tn_List_Int tn_read_all_bytes_u(void) {
    tn_flush();
    while (tn_in_fill()) {}
    tn_List_Int l = tn_in_mem ? tn_bytes_list(tn_in_buf + tn_in_pos, tn_in_len - tn_in_pos) : NULL;
    tn_in_pos = tn_in_len;
    return l;
}
/* The next n bytes of stdin; fewer only at end of input. */
static tn_List_Int tn_read_bytes_u(int64_t n) {
    tn_flush();
    if (n <= 0) return NULL;
    while (tn_in_len - tn_in_pos < n && tn_in_fill()) {}
    int64_t k = tn_in_mem ? tn_in_len - tn_in_pos : 0;
    if (k > n) k = n;
    tn_List_Int l = k > 0 ? tn_bytes_list(tn_in_buf + tn_in_pos, k) : NULL;
    tn_in_pos += k;
    return l;
}
/* Standard input is shared by the workers: one reader at a time. */
static TN_UNUSED bool tn_read_line(tn_Str *out) {
    TN_LOCK(tn_in_mu);
    bool r = tn_read_line_u(out);
    TN_UNLOCK(tn_in_mu);
    return r;
}
static TN_UNUSED tn_Str tn_read_all(void) {
    TN_LOCK(tn_in_mu);
    tn_Str r = tn_read_all_u();
    TN_UNLOCK(tn_in_mu);
    return r;
}
static TN_UNUSED tn_List_Int tn_read_all_bytes(void) {
    TN_LOCK(tn_in_mu);
    tn_List_Int r = tn_read_all_bytes_u();
    TN_UNLOCK(tn_in_mu);
    return r;
}
static TN_UNUSED tn_List_Int tn_read_bytes(int64_t n) {
    TN_LOCK(tn_in_mu);
    tn_List_Int r = tn_read_bytes_u(n);
    TN_UNLOCK(tn_in_mu);
    return r;
}
static TN_UNUSED bool tn_str_from_utf8(tn_List_Int l, tn_Str *out) {
    int64_t bad;
    if (!tn_list_to_bytes(l, out, &bad)) return false;
    if (tn_utf8_valid(out->p, out->len)) return true;
    tn_Str_release(*out);
    return false;
}
static TN_UNUSED tn_Str tn_str_from_utf8_lossy(tn_List_Int l, const char *loc) {
    tn_Str s = tn_bytes_of(l, loc);
    tn_buf b = tn_buf_new();
    tn_utf8_lossy(s.p, s.len, &b);
    tn_Str_release(s);
    return tn_buf_finish(&b);
}
static TN_UNUSED void tn_write_bytes(tn_List_Int l, const char *loc) {
    tn_Str s = tn_bytes_of(l, loc);
    tn_write(s.p, (size_t)s.len);
    tn_Str_release(s);
}
static TN_UNUSED void tn_eprintln(tn_Str s) {
    TN_LOCK(tn_out_mu);
    tn_flush_u();
    tn_write_fd(2, s.p, (size_t)s.len, false);
    tn_write_fd(2, "\n", 1, false);
    TN_UNLOCK(tn_out_mu);
}

/* ---------- file system capability ---------- */

typedef struct tn_Fs_s { int64_t rc; tn_Str root; bool att, wr; } *tn_Fs;
static TN_UNUSED tn_Fs tn_Fs_retain(tn_Fs f) { f->rc++; return f; }
static TN_UNUSED void tn_Fs_release(tn_Fs f) {
    if (--f->rc == 0) { tn_Str_release(f->root); tn_free(f); }
}
static TN_UNUSED void tn_Fs_show(tn_buf *b, tn_Fs f, int mode) { (void)f; (void)mode; tn_buf_cstr(b, "<Fs>"); }
TN_INCOMPARABLE(tn_Fs)
static TN_UNUSED tn_Fs tn_fs_make(tn_Str root, bool att, bool wr) {
    tn_Fs f = tn_alloc(sizeof *f);
    f->rc = 1; f->root = root; f->att = att; f->wr = wr;
    return f;
}

enum { TN_IO_OK = 0, TN_IO_NOTFOUND = 1, TN_IO_DENIED = 2, TN_IO_FAILED = 3 };

/* Resolve p under f into a NUL-terminated path; false if it escapes the root. */
/* Same rules as builtins.rs fs_path: a NUL byte always escapes (C strings
 * would truncate); an attenuated Fs also rejects absolute paths, `..` and any
 * existing symlink on the way (a concurrent change after the check is not
 * prevented). */
static TN_UNUSED bool tn_fs_path(tn_Fs f, tn_Str p, tn_buf *out) {
    if (memchr(p.p, 0, (size_t)p.len)) return false;
    if (f->att) {
        if (p.len == 0 || p.p[0] == '/') return false;
        int64_t s = 0;
        for (int64_t i = 0; i <= p.len; i++) {
            if (i == p.len || p.p[i] == '/') {
                if (i - s == 2 && p.p[s] == '.' && p.p[s + 1] == '.') return false;
                s = i + 1;
            }
        }
    }
    if (f->root.len == 0) {
        if (p.len == 0) tn_buf_cstr(out, ".");
        else tn_buf_str(out, p);
    } else if (p.len == 0 || (p.len == 1 && p.p[0] == '.')) {
        tn_buf_str(out, f->root);
    } else {
        tn_buf_str(out, f->root);
        tn_buf_add(out, "/", 1);
        tn_buf_str(out, p);
    }
    tn_buf_add(out, "", 1);
    if (f->att) {
        /* walk root/comp1, root/comp1/comp2, ... refusing symlinks */
        char *full = out->p + sizeof(tn_rc);
        size_t start = (size_t)f->root.len;
        /* the path is the root itself: nothing to walk */
        for (size_t i = start + 1; full[start] != 0; i++) {
            char c = full[i];
            if (c == '/' || c == 0) {
                if (i > start + 1) {
                    full[i] = 0;
                    struct stat st;
                    int r = lstat(full, &st);
                    full[i] = c;
                    if (r == 0 && S_ISLNK(st.st_mode)) return false;
                    if (r != 0) break;
                }
                start = i;
                if (c == 0) break;
            }
        }
    }
    return true;
}
static TN_UNUSED int tn_io_kind(int e) {
    if (e == ENOENT) return TN_IO_NOTFOUND;
    if (e == EACCES || e == EPERM) return TN_IO_DENIED;
    return TN_IO_FAILED;
}
/* Error message for kind: NotFound/Denied carry the path, Failed adds the reason. */
static TN_UNUSED tn_Str tn_io_msg(int kind, tn_Str path, const char *why) {
    tn_buf b = tn_buf_new();
    tn_buf_str(&b, path);
    if (kind == TN_IO_FAILED) {
        tn_buf_cstr(&b, ": ");
        tn_buf_cstr(&b, why);
    }
    return tn_buf_finish(&b);
}
#define TN_FS_PRE(writes)                                                                 \
    tn_buf pb = tn_buf_new();                                                             \
    if (!tn_fs_path(f, p, &pb)) {                                                         \
        tn_free(pb.p);                                                                       \
        tn_buf b = tn_buf_new();                                                          \
        tn_buf_cstr(&b, "path escapes the Fs root: ");                                    \
        tn_buf_str(&b, p);                                                                \
        *msg = tn_buf_finish(&b);                                                         \
        return TN_IO_DENIED;                                                              \
    }                                                                                     \
    const char *full = pb.p + sizeof(tn_rc);                                              \
    if ((writes) && !f->wr) {                                                             \
        tn_free(pb.p);                                                                       \
        tn_buf b = tn_buf_new();                                                          \
        tn_buf_cstr(&b, "read-only Fs: ");                                                \
        tn_buf_str(&b, p);                                                                \
        *msg = tn_buf_finish(&b);                                                         \
        return TN_IO_DENIED;                                                              \
    }
#define TN_FS_FAIL(e)                                                                     \
    do {                                                                                  \
        int k_ = tn_io_kind(e);                                                           \
        *msg = tn_io_msg(k_, p, strerror(e));                                             \
        tn_free(pb.p);                                                                       \
        return k_;                                                                        \
    } while (0)

static TN_UNUSED int tn_fs_read(tn_Fs f, tn_Str p, tn_Str *res, tn_Str *msg) {
    TN_FS_PRE(false)
    int fd = open(full, O_RDONLY);
    if (fd < 0) TN_FS_FAIL(errno);
    struct stat st;
    if (fstat(fd, &st) == 0 && S_ISDIR(st.st_mode)) { close(fd); TN_FS_FAIL(EISDIR); }
    tn_buf b = tn_buf_new();
    char chunk[1 << 16];
    for (;;) {
        ssize_t r = read(fd, chunk, sizeof chunk);
        if (r < 0 && errno == EINTR) continue;
        if (r < 0) { int e = errno; close(fd); tn_free(b.p); TN_FS_FAIL(e); }
        if (r == 0) break;
        tn_buf_add(&b, chunk, r);
    }
    close(fd);
    tn_buf chk = tn_buf_new();
    bool valid = tn_utf8_lossy(b.p + sizeof(tn_rc), b.len, &chk);
    tn_free(chk.p);
    if (!valid) {
        tn_free(b.p);
        *msg = tn_io_msg(TN_IO_FAILED, p, "invalid UTF-8");
        tn_free(pb.p);
        return TN_IO_FAILED;
    }
    tn_free(pb.p);
    *res = tn_buf_finish(&b);
    return TN_IO_OK;
}
/* One allocation: the list is sized from fstat and filled chunk by chunk. */
static TN_UNUSED int tn_fs_read_bytes(tn_Fs f, tn_Str p, tn_List_Int *res, tn_Str *msg) {
    TN_FS_PRE(false)
    int fd = open(full, O_RDONLY);
    if (fd < 0) TN_FS_FAIL(errno);
    struct stat st;
    if (fstat(fd, &st) == 0 && S_ISDIR(st.st_mode)) { close(fd); TN_FS_FAIL(EISDIR); }
    tn_List_Int l = NULL;
    if (st.st_size > 0) tn_List_Int_reserve(&l, (int64_t)st.st_size);
    char chunk[1 << 16];
    for (;;) {
        ssize_t r = read(fd, chunk, sizeof chunk);
        if (r < 0 && errno == EINTR) continue;
        if (r < 0) { int e = errno; close(fd); tn_List_Int_release(l); TN_FS_FAIL(e); }
        if (r == 0) break;
        tn_List_Int_reserve(&l, r);
        tn_bytes_put(l, chunk, r);
    }
    close(fd);
    tn_free(pb.p);
    if (l && l->len == 0) { tn_List_Int_release(l); l = NULL; }
    *res = l;
    return TN_IO_OK;
}
static TN_UNUSED bool tn_write_all(int fd, tn_Str d) {
    const char *q = d.p;
    int64_t n = d.len;
    while (n > 0) {
        ssize_t w = write(fd, q, (size_t)n);
        if (w < 0 && errno == EINTR) continue;
        if (w < 0) return false;
        q += w;
        n -= w;
    }
    return true;
}
/* Atomic, durable replace: write a temp file, fsync, rename over the target. */
static TN_UNUSED int tn_fs_write(tn_Fs f, tn_Str p, tn_Str d, tn_Str *msg) {
    TN_FS_PRE(true)
    tn_buf tb = tn_buf_new();
    tn_buf_cstr(&tb, full);
    tn_buf_cstr(&tb, ".tmp");
    tn_buf_add(&tb, "", 1);
    const char *tmp = tb.p + sizeof(tn_rc);
    unlink(tmp); /* never write through a pre-existing temp file (it may be a planted symlink) */
    int fd = open(tmp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0644);
    if (fd < 0) { int e = errno; tn_free(tb.p); TN_FS_FAIL(e); }
    if (!tn_write_all(fd, d) || fsync(fd) != 0) {
        int e = errno; close(fd); unlink(tmp); tn_free(tb.p); TN_FS_FAIL(e);
    }
    close(fd);
    if (rename(tmp, full) != 0) { int e = errno; unlink(tmp); tn_free(tb.p); TN_FS_FAIL(e); }
    tn_free(tb.p);
    tn_free(pb.p);
    return TN_IO_OK;
}
static TN_UNUSED int tn_fs_append(tn_Fs f, tn_Str p, tn_Str d, tn_Str *msg) {
    TN_FS_PRE(true)
    int fd = open(full, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) TN_FS_FAIL(errno);
    if (!tn_write_all(fd, d) || fsync(fd) != 0) { int e = errno; close(fd); TN_FS_FAIL(e); }
    close(fd);
    tn_free(pb.p);
    return TN_IO_OK;
}
/* Cut an existing file to len bytes and fsync; never extends (builtins.rs Fs.truncate). */
static TN_UNUSED int tn_fs_truncate(tn_Fs f, tn_Str p, tn_Int len, tn_Str *msg) {
    TN_FS_PRE(true)
    int fd = open(full, O_WRONLY);
    if (fd < 0) TN_FS_FAIL(errno);
    struct stat st;
    if (fstat(fd, &st) != 0) { int e = errno; close(fd); TN_FS_FAIL(e); }
    if (len < 0 || len > (tn_Int)st.st_size) {
        close(fd);
        char why[128];
        if (len < 0) snprintf(why, sizeof why, "truncate length %lld is negative", (long long)len);
        else snprintf(why, sizeof why, "truncate length %lld is larger than the file (%lld bytes)", (long long)len, (long long)st.st_size);
        *msg = tn_io_msg(TN_IO_FAILED, p, why);
        tn_free(pb.p);
        return TN_IO_FAILED;
    }
    if (ftruncate(fd, (off_t)len) != 0 || fsync(fd) != 0) { int e = errno; close(fd); TN_FS_FAIL(e); }
    close(fd);
    tn_free(pb.p);
    return TN_IO_OK;
}
static TN_UNUSED bool tn_fs_exists(tn_Fs f, tn_Str p) {
    tn_buf pb = tn_buf_new();
    if (!tn_fs_path(f, p, &pb)) { tn_free(pb.p); return false; }
    struct stat st;
    bool r = stat(pb.p + sizeof(tn_rc), &st) == 0;
    tn_free(pb.p);
    return r;
}
static TN_UNUSED bool tn_fs_is_dir(tn_Fs f, tn_Str p) {
    tn_buf pb = tn_buf_new();
    if (!tn_fs_path(f, p, &pb)) { tn_free(pb.p); return false; }
    struct stat st;
    bool r = stat(pb.p + sizeof(tn_rc), &st) == 0 && S_ISDIR(st.st_mode);
    tn_free(pb.p);
    return r;
}
static TN_UNUSED int tn_fs_rename(tn_Fs f, tn_Str p, tn_Str to, tn_Str *msg) {
    TN_FS_PRE(true)
    tn_buf tb = tn_buf_new();
    if (!tn_fs_path(f, to, &tb)) {
        tn_free(tb.p); tn_free(pb.p);
        tn_buf b = tn_buf_new();
        tn_buf_cstr(&b, "path escapes the Fs root: ");
        tn_buf_str(&b, to);
        *msg = tn_buf_finish(&b);
        return TN_IO_DENIED;
    }
    if (rename(full, tb.p + sizeof(tn_rc)) != 0) { int e = errno; tn_free(tb.p); TN_FS_FAIL(e); }
    tn_free(tb.p);
    tn_free(pb.p);
    return TN_IO_OK;
}
static TN_UNUSED int tn_fs_remove(tn_Fs f, tn_Str p, tn_Str *msg) {
    TN_FS_PRE(true)
    if (remove(full) != 0) TN_FS_FAIL(errno);
    tn_free(pb.p);
    return TN_IO_OK;
}
static TN_UNUSED int tn_fs_mkdir(tn_Fs f, tn_Str p, tn_Str *msg) {
    TN_FS_PRE(true)
    char *q = (char *)full;
    for (char *s = q + 1;; s++) {
        if (*s == '/' || *s == 0) {
            char c = *s;
            *s = 0;
            if (mkdir(q, 0755) != 0 && errno != EEXIST) { int e = errno; *s = c; TN_FS_FAIL(e); }
            *s = c;
            if (c == 0) break;
        }
    }
    struct stat st;
    if (stat(full, &st) != 0 || !S_ISDIR(st.st_mode)) TN_FS_FAIL(EEXIST);
    tn_free(pb.p);
    return TN_IO_OK;
}
/* Exactly one directory: the parent must exist and the path must not. */
static TN_UNUSED int tn_fs_mkdir_one(tn_Fs f, tn_Str p, tn_Str *msg) {
    TN_FS_PRE(true)
    if (mkdir(full, 0755) != 0) TN_FS_FAIL(errno);
    tn_free(pb.p);
    return TN_IO_OK;
}
static int tn_cmp_cstr(const void *a, const void *b) {
    return tn_Str_cmp(*(const tn_Str *)a, *(const tn_Str *)b);
}
static TN_UNUSED int tn_fs_list(tn_Fs f, tn_Str p, tn_List_Str *res, tn_Str *msg) {
    TN_FS_PRE(false)
    DIR *d = opendir(full);
    if (!d) TN_FS_FAIL(errno);
    tn_List_Str out = NULL;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        tn_buf nb = tn_buf_new(); /* invalid UTF-8 becomes U+FFFD, as in the interpreter */
        tn_utf8_lossy(e->d_name, (int64_t)strlen(e->d_name), &nb);
        tn_List_Str_push(&out, tn_buf_finish(&nb));
    }
    closedir(d);
    if (out) qsort(out->data, (size_t)out->len, sizeof(tn_Str), tn_cmp_cstr);
    tn_free(pb.p);
    *res = out;
    return TN_IO_OK;
}
static TN_UNUSED tn_Fs tn_fs_within(tn_Fs f, tn_Str p) {
    tn_buf pb = tn_buf_new();
    if (!tn_fs_path(f, p, &pb)) {
        tn_free(pb.p);
        return tn_fs_make(tn_str_lit("/nonexistent-denied", 19), true, false);
    }
    tn_Str root = tn_str_new(pb.p + sizeof(tn_rc), pb.len - 1);
    tn_free(pb.p);
    return tn_fs_make(root, true, f->wr);
}

/* ---------- network capability: TCP, blocking ---------- */

typedef uint8_t tn_Net;
TN_TRIVIAL(tn_Net)
TN_INCOMPARABLE(tn_Net)
static TN_UNUSED void tn_Net_show(tn_buf *b, tn_Net x, int mode) { (void)x; (void)mode; tn_buf_cstr(b, "<Net>"); }

/* Listener and Conn: unique handles; the last release closes the socket. */
typedef struct tn_sock_s { int64_t rc; int fd; char *buf; int64_t len, pos; } *tn_Listener, *tn_Conn;
static TN_UNUSED struct tn_sock_s *tn_sock_new(int fd) {
    struct tn_sock_s *s = tn_alloc(sizeof *s);
    s->rc = 1; s->fd = fd; s->buf = NULL; s->len = s->pos = 0;
    return s;
}
#define TN_SOCK(T, NAME)                                                                     \
    static TN_UNUSED T T##_retain(T s) { s->rc++; return s; }                                \
    static TN_UNUSED void T##_release(T s) {                                                 \
        if (s && --s->rc == 0) { close(s->fd); tn_free(s->buf); tn_free(s); }                      \
    }                                                                                        \
    static TN_UNUSED void T##_show(tn_buf *b, T s, int mode) { (void)s; (void)mode; tn_buf_cstr(b, NAME); } \
    TN_INCOMPARABLE(T)
TN_SOCK(tn_Listener, "<Listener>")
TN_SOCK(tn_Conn, "<Conn>")

static TN_UNUSED int tn_net_err(const char *what, int e, tn_Str *msg) {
    int k = tn_io_kind(e);
    *msg = tn_io_msg(k, tn_str_lit(what, (int64_t)strlen(what)), strerror(e));
    return k;
}
static TN_UNUSED int tn_net_listen(tn_Int port, tn_Listener *out, tn_Str *msg) {
    char what[64];
    snprintf(what, sizeof what, "127.0.0.1:%lld", (long long)port);
    if (port < 0 || port > 65535) {
        char m[96];
        snprintf(m, sizeof m, "%s: port must be 0-65535", what);
        *msg = tn_str_new(m, (int64_t)strlen(m));
        return TN_IO_FAILED;
    }
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return tn_net_err(what, errno, msg);
    int one = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_port = htons((uint16_t)port);
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0 || listen(fd, 128) != 0) {
        int e = errno;
        close(fd);
        return tn_net_err(what, e, msg);
    }
    *out = tn_sock_new(fd);
    return TN_IO_OK;
}
static TN_UNUSED tn_Int tn_listener_port(tn_Listener l) {
    struct sockaddr_in a;
    socklen_t n = sizeof a;
    if (getsockname(l->fd, (struct sockaddr *)&a, &n) != 0) return 0;
    return ntohs(a.sin_port);
}
static TN_UNUSED int tn_listener_accept(tn_Listener l, tn_Conn *out, tn_Str *msg) {
    tn_flush(); /* a program about to block has shown all of its output */
    int fd;
    do fd = accept(l->fd, NULL, NULL);
    while (fd < 0 && errno == EINTR);
    if (fd < 0) return tn_net_err("accept", errno, msg);
    *out = tn_sock_new(fd);
    return TN_IO_OK;
}
static TN_UNUSED int tn_net_connect(tn_Str host, tn_Int port, tn_Conn *out, tn_Str *msg) {
    tn_flush(); /* a program about to block has shown all of its output */
    char h[256], what[320], ps[16];
    snprintf(h, sizeof h, "%.*s", (int)host.len, host.p);
    bool nul = host.len == 0 || memchr(host.p, 0, (size_t)host.len) != NULL;
    snprintf(what, sizeof what, "%s:%lld", h, (long long)port);
    snprintf(ps, sizeof ps, "%lld", (long long)port);
    if (port < 0 || port > 65535 || nul) {
        char tail[64];
        snprintf(tail, sizeof tail, ":%lld: %s", (long long)port, (port < 0 || port > 65535) ? "port must be 0-65535" : "invalid host name");
        tn_buf mb = tn_buf_new();
        tn_buf_str(&mb, host); /* byte for byte, NULs included */
        tn_buf_cstr(&mb, tail);
        *msg = tn_buf_finish(&mb);
        return TN_IO_FAILED;
    }
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof hints);
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(h, ps, &hints, &res) != 0) {
        char m[384];
        snprintf(m, sizeof m, "%s: host not found", what);
        *msg = tn_str_new(m, (int64_t)strlen(m));
        return TN_IO_FAILED;
    }
    int e = ECONNREFUSED, fd = -1;
    for (struct addrinfo *p = res; p; p = p->ai_next) {
        fd = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (fd < 0) { e = errno; continue; }
        if (connect(fd, p->ai_addr, p->ai_addrlen) == 0) break;
        e = errno;
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    if (fd < 0) return tn_net_err(what, e, msg);
    *out = tn_sock_new(fd);
    return TN_IO_OK;
}
/* Buffered read of more bytes; returns false at end of stream, *err on failure. */
static bool tn_conn_fill(tn_Conn c, int *err) {
    if (c->pos > 0) {
        memmove(c->buf, c->buf + c->pos, (size_t)(c->len - c->pos));
        c->len -= c->pos;
        c->pos = 0;
    }
    c->buf = tn_realloc(c->buf, (size_t)c->len + 65536);
    ssize_t r;
    do r = read(c->fd, c->buf + c->len, 65536);
    while (r < 0 && errno == EINTR);
    if (r < 0) { *err = errno; return false; }
    if (r == 0) return false;
    c->len += r;
    return true;
}
static TN_UNUSED int tn_conn_read_line(tn_Conn c, bool *some, tn_Str *line, tn_Str *msg) {
    tn_flush(); /* a program about to block has shown all of its output */
    int64_t scan = c->pos;
    int err = 0;
    for (;;) {
        for (; scan < c->len; scan++)
            if (c->buf[scan] == '\n') goto found;
        int64_t off = scan - c->pos;
        bool more = tn_conn_fill(c, &err);
        scan = c->pos + off;
        if (err) return tn_net_err("read", err, msg);
        if (!more) break;
    }
    if (c->pos == c->len) { *some = false; return TN_IO_OK; }
found:;
    int64_t end = scan, next = scan < c->len ? scan + 1 : scan;
    if (end > c->pos && c->buf[end - 1] == '\r') end--;
    tn_buf b = tn_buf_new();
    tn_utf8_lossy(c->buf + c->pos, end - c->pos, &b);
    c->pos = next;
    *line = tn_buf_finish(&b);
    *some = true;
    return TN_IO_OK;
}
static TN_UNUSED int tn_conn_read(tn_Conn c, tn_Int n, tn_Str *out, tn_Str *msg) {
    tn_flush(); /* a program about to block has shown all of its output */
    int err = 0;
    if (n < 0) n = 0;
    while (c->len - c->pos < n) {
        if (!tn_conn_fill(c, &err)) break;
    }
    if (err) return tn_net_err("read", err, msg);
    int64_t k = c->len - c->pos < n ? c->len - c->pos : n;
    tn_buf b = tn_buf_new();
    tn_utf8_lossy(c->buf + c->pos, k, &b);
    c->pos += k;
    *out = tn_buf_finish(&b);
    return TN_IO_OK;
}
static TN_UNUSED int tn_conn_write(tn_Conn c, tn_Str s, tn_Str *msg) {
    if (!tn_write_all(c->fd, s)) return tn_net_err("write", errno, msg);
    return TN_IO_OK;
}

/* ---------- event loop: one Poller owns sockets named by increasing ids ---------- */

typedef struct { int64_t id; int fd; bool listener; } tn_psock;
typedef struct tn_Poller_s { int64_t rc, next, n, cap; tn_psock *s; } *tn_Poller;
typedef struct { int kind; int64_t a, b; tn_Str data; } tn_rawev; /* kind: 0 Accepted 1 Data 2 Closed 3 Timeout */
static TN_UNUSED tn_Poller tn_Poller_retain(tn_Poller p) { p->rc++; return p; }
static TN_UNUSED void tn_Poller_release(tn_Poller p) {
    if (p && --p->rc == 0) {
        for (int64_t i = 0; i < p->n; i++) close(p->s[i].fd);
        tn_free(p->s);
        tn_free(p);
    }
}
static TN_UNUSED void tn_Poller_show(tn_buf *b, tn_Poller p, int mode) { (void)p; (void)mode; tn_buf_cstr(b, "<Poller>"); }
TN_INCOMPARABLE(tn_Poller)
static TN_UNUSED tn_Poller tn_net_poller(void) {
    tn_Poller p = tn_alloc(sizeof *p);
    p->rc = 1; p->next = 0; p->n = 0; p->cap = 0; p->s = NULL;
    return p;
}
static int64_t tn_poller_add(tn_Poller p, int fd, bool listener) {
    if (p->n == p->cap) {
        p->cap = p->cap ? p->cap * 2 : 8;
        p->s = tn_realloc(p->s, sizeof(tn_psock) * (size_t)p->cap);
    }
    p->s[p->n++] = (tn_psock){++p->next, fd, listener};
    return p->next;
}
static int64_t tn_poller_find(tn_Poller p, int64_t id) {
    for (int64_t i = 0; i < p->n; i++)
        if (p->s[i].id == id) return i;
    return -1;
}
static TN_UNUSED int tn_poller_listen(tn_Poller p, tn_Int port, tn_Int *id, tn_Str *msg) {
    tn_Listener l;
    int k = tn_net_listen(port, &l, msg);
    if (k != TN_IO_OK) return k;
    *id = tn_poller_add(p, l->fd, true);
    l->fd = -1; /* the poller owns the socket now */
    tn_Listener_release(l);
    return TN_IO_OK;
}
static TN_UNUSED int tn_poller_connect(tn_Poller p, tn_Str host, tn_Int port, tn_Int *id, tn_Str *msg) {
    tn_Conn c;
    int k = tn_net_connect(host, port, &c, msg);
    if (k != TN_IO_OK) return k;
    *id = tn_poller_add(p, c->fd, false);
    c->fd = -1;
    tn_Conn_release(c);
    return TN_IO_OK;
}
static TN_UNUSED tn_Int tn_poller_port(tn_Poller p, tn_Int id) {
    int64_t i = tn_poller_find(p, id);
    if (i < 0 || !p->s[i].listener) return 0;
    struct sockaddr_in a;
    socklen_t n = sizeof a;
    if (getsockname(p->s[i].fd, (struct sockaddr *)&a, &n) != 0) return 0;
    return ntohs(a.sin_port);
}
static TN_UNUSED int tn_poller_send(tn_Poller p, tn_Int id, tn_Str data, tn_Str *msg) {
    int64_t i = tn_poller_find(p, id);
    if (i < 0 || p->s[i].listener) return tn_net_err("send", EBADF, msg);
    if (!tn_write_all(p->s[i].fd, data)) return tn_net_err("send", errno, msg);
    return TN_IO_OK;
}
static void tn_poller_drop(tn_Poller p, int64_t i) {
    close(p->s[i].fd);
    memmove(&p->s[i], &p->s[i + 1], sizeof(tn_psock) * (size_t)(p->n - i - 1));
    p->n--;
}
static TN_UNUSED void tn_poller_close(tn_Poller p, tn_Int id) {
    int64_t i = tn_poller_find(p, id);
    if (i >= 0) tn_poller_drop(p, i);
}
/* Events in ascending id order; *out is a tn_alloc'd array the caller frees. */
static TN_UNUSED int64_t tn_poller_wait(tn_Poller p, tn_Int timeout, tn_rawev **out) {
    tn_flush();
    int64_t n = p->n;
    struct pollfd *fds = tn_alloc(sizeof(struct pollfd) * (size_t)(n ? n : 1));
    for (int64_t i = 0; i < n; i++) fds[i] = (struct pollfd){p->s[i].fd, POLLIN, 0};
    int t = timeout < 0 ? -1 : timeout > INT32_MAX ? INT32_MAX : (int)timeout;
    int r;
    do r = poll(fds, (nfds_t)n, t);
    while (r < 0 && errno == EINTR);
    tn_rawev *ev = tn_alloc(sizeof(tn_rawev) * (size_t)(n + 1));
    int64_t k = 0;
    if (r <= 0) {
        ev[k++] = (tn_rawev){3, 0, 0, {0}};
        tn_free(fds);
        *out = ev;
        return k;
    }
    /* snapshot of ids: accepting adds sockets, closing removes them */
    int64_t *ids = tn_alloc(sizeof(int64_t) * (size_t)(n ? n : 1));
    for (int64_t i = 0; i < n; i++) ids[i] = p->s[i].id;
    for (int64_t j = 0; j < n; j++) {
        if (!fds[j].revents) continue;
        int64_t i = tn_poller_find(p, ids[j]);
        if (i < 0) continue;
        if (p->s[i].listener) {
            int fd;
            do fd = accept(p->s[i].fd, NULL, NULL);
            while (fd < 0 && errno == EINTR);
            if (fd >= 0) {
                int64_t cid = tn_poller_add(p, fd, false);
                ev[k++] = (tn_rawev){0, ids[j], cid, {0}};
                ev = tn_realloc(ev, sizeof(tn_rawev) * (size_t)(k + n + 1));
            }
        } else {
            char buf[65536];
            ssize_t got;
            do got = read(p->s[i].fd, buf, sizeof buf);
            while (got < 0 && errno == EINTR);
            if (got > 0) {
                tn_buf b = tn_buf_new();
                tn_utf8_lossy(buf, got, &b);
                ev[k++] = (tn_rawev){1, ids[j], 0, tn_buf_finish(&b)};
            } else {
                tn_poller_drop(p, i);
                ev[k++] = (tn_rawev){2, ids[j], 0, {0}};
            }
        }
    }
    tn_free(ids);
    tn_free(fds);
    *out = ev;
    return k;
}

/* ---------- clock ---------- */

static TN_UNUSED tn_Int tn_now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_REALTIME, &t);
    return (tn_Int)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static TN_UNUSED tn_Int tn_mono_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (tn_Int)(t.tv_sec - tn_mono0.tv_sec) * 1000000000 + (t.tv_nsec - tn_mono0.tv_nsec);
}
static TN_UNUSED void tn_sleep_ms(tn_Int ms) {
    tn_flush(); /* a program about to block has shown all of its output */
    if (ms <= 0) return;
    struct timespec t = {ms / 1000, (ms % 1000) * 1000000};
    while (nanosleep(&t, &t) != 0 && errno == EINTR) {}
}

static TN_UNUSED tn_List_Str tn_args(void) {
    tn_List_Str out = NULL;
    for (int i = 1; i < tn_argc; i++) { /* invalid UTF-8 becomes U+FFFD, as in the interpreter */
        tn_buf b = tn_buf_new();
        tn_utf8_lossy(tn_argv[i], (int64_t)strlen(tn_argv[i]), &b);
        tn_List_Str_push(&out, tn_buf_finish(&b));
    }
    return out;
}

/* ---------- processes (Proc) ---------- */

extern char **environ;
typedef uint8_t tn_Proc;
TN_TRIVIAL(tn_Proc)
TN_INCOMPARABLE(tn_Proc)
static TN_UNUSED void tn_Proc_show(tn_buf *b, tn_Proc x, int mode) { (void)x; (void)mode; tn_buf_cstr(b, "<Proc>"); }
/* A NUL-terminated heap copy of s (the caller frees it). */
static char *tn_proc_cstr(tn_Str s) {
    char *c = tn_alloc((size_t)s.len + 1);
    memcpy(c, s.p, (size_t)s.len);
    c[s.len] = 0;
    return c;
}
static TN_UNUSED int tn_proc_run(tn_Str cmd, tn_List_Str args, tn_Int *res, tn_Str *msg) {
    int64_t n = tn_List_Str_len(args);
    bool nul = memchr(cmd.p, 0, (size_t)cmd.len) != NULL;
    for (int64_t i = 0; i < n; i++) nul = nul || memchr(args->data[i].p, 0, (size_t)args->data[i].len) != NULL;
    if (nul) { *msg = tn_io_msg(TN_IO_FAILED, cmd, "argument contains a NUL byte"); return TN_IO_FAILED; }
    tn_flush(); /* the command's output follows everything printed so far */
    char **argv = tn_alloc(sizeof(char *) * (size_t)(n + 2));
    argv[0] = tn_proc_cstr(cmd);
    for (int64_t i = 0; i < n; i++) argv[i + 1] = tn_proc_cstr(args->data[i]);
    argv[n + 1] = NULL;
    pid_t pid;
    int e = posix_spawnp(&pid, argv[0], NULL, NULL, argv, environ);
    int st = 0;
    if (e == 0) {
        while (waitpid(pid, &st, 0) < 0) {
            if (errno != EINTR) { e = errno; break; }
        }
    }
    for (int64_t i = 0; i <= n; i++) tn_free(argv[i]);
    tn_free(argv);
    if (e != 0) {
        int k = tn_io_kind(e);
        *msg = tn_io_msg(k, cmd, strerror(e));
        return k;
    }
    if (WIFEXITED(st)) { *res = WEXITSTATUS(st); return TN_IO_OK; }
    char why[64];
    snprintf(why, sizeof why, "terminated by signal %d", WIFSIGNALED(st) ? WTERMSIG(st) : 0);
    *msg = tn_io_msg(TN_IO_FAILED, cmd, why);
    return TN_IO_FAILED;
}
static TN_UNUSED bool tn_proc_env(tn_Str name, tn_Str *out) {
    if (name.len == 0 || memchr(name.p, 0, (size_t)name.len) || memchr(name.p, '=', (size_t)name.len)) return false;
    char *c = tn_proc_cstr(name);
    const char *v = getenv(c);
    tn_free(c);
    if (!v) return false;
    tn_buf b = tn_buf_new(); /* invalid UTF-8 becomes U+FFFD, as in the interpreter */
    tn_utf8_lossy(v, (int64_t)strlen(v), &b);
    *out = tn_buf_finish(&b);
    return true;
}
/* Proc.exit: any status 0..255 (also the reserved ones); output is flushed first. */
static TN_UNUSED void tn_proc_exit(tn_Int status, const char *loc) {
    if (status < 0 || status > 255) tn_trapf(loc, "exit status %lld is out of range", (long long)status);
    tn_exit((int)status);
}
static int64_t tn_ms_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
/* Proc.run_capture (Proc.run_with in the prelude): run cmd in dir with the
 * given standard input, capturing standard output and error; kill it
 * (SIGKILL) after timeout_ms > 0. The result is packed as
 * [status, signal, timed_out, len(out), out..., err...]; status is -1 when the
 * command was ended by a signal. */
static TN_UNUSED int tn_proc_capture(tn_Str cmd, tn_List_Str args, tn_Str dir, tn_Str input, tn_Int timeout_ms, tn_List_Int *res, tn_Str *msg) {
    int64_t n = tn_List_Str_len(args);
    bool nul = memchr(cmd.p, 0, (size_t)cmd.len) != NULL || memchr(dir.p, 0, (size_t)dir.len) != NULL;
    for (int64_t i = 0; i < n; i++) nul = nul || memchr(args->data[i].p, 0, (size_t)args->data[i].len) != NULL;
    if (nul) { *msg = tn_io_msg(TN_IO_FAILED, cmd, "argument contains a NUL byte"); return TN_IO_FAILED; }
    char *cdir = dir.len > 0 ? tn_proc_cstr(dir) : NULL;
    struct stat ds;
    if (cdir && (stat(cdir, &ds) != 0 || !S_ISDIR(ds.st_mode))) {
        tn_free(cdir);
        *msg = tn_io_msg(TN_IO_NOTFOUND, dir, "");
        return TN_IO_NOTFOUND;
    }
    tn_flush();
    char **argv = tn_alloc(sizeof(char *) * (size_t)(n + 2));
    argv[0] = tn_proc_cstr(cmd);
    for (int64_t i = 0; i < n; i++) argv[i + 1] = tn_proc_cstr(args->data[i]);
    argv[n + 1] = NULL;
    int pin[2], pout[2], perr[2], pex[2];
    if (pipe(pin) != 0 || pipe(pout) != 0 || pipe(perr) != 0 || pipe(pex) != 0) {
        int e = errno;
        *msg = tn_io_msg(TN_IO_FAILED, cmd, strerror(e));
        return TN_IO_FAILED;
    }
    fcntl(pex[1], F_SETFD, FD_CLOEXEC);
    pid_t pid = fork();
    if (pid == 0) {
        dup2(pin[0], 0);
        dup2(pout[1], 1);
        dup2(perr[1], 2);
        close(pin[0]); close(pin[1]); close(pout[0]); close(pout[1]); close(perr[0]); close(perr[1]); close(pex[0]);
        int e = 0;
        if (cdir && chdir(cdir) != 0) e = errno;
        if (e == 0) { execvp(argv[0], argv); e = errno; }
        ssize_t w = write(pex[1], &e, sizeof e);
        (void)w;
        _exit(127);
    }
    int fe = pid < 0 ? errno : 0;
    close(pin[0]); close(pout[1]); close(perr[1]); close(pex[1]);
    for (int64_t i = 0; i <= n; i++) tn_free(argv[i]);
    tn_free(argv);
    tn_free(cdir);
    int e = fe;
    if (pid > 0) {
        ssize_t r;
        while ((r = read(pex[0], &e, sizeof e)) < 0 && errno == EINTR) {}
        if (r != (ssize_t)sizeof e) e = 0;
    }
    close(pex[0]);
    if (e != 0) {
        close(pin[1]); close(pout[0]); close(perr[0]);
        if (pid > 0) while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {}
        int k = tn_io_kind(e);
        *msg = tn_io_msg(k, cmd, strerror(e));
        return k;
    }
    fcntl(pin[1], F_SETFL, fcntl(pin[1], F_GETFL) | O_NONBLOCK);
    tn_buf ob = tn_buf_new(), eb = tn_buf_new();
    int64_t sent = 0, deadline = timeout_ms > 0 ? tn_ms_now() + timeout_ms : 0;
    int fin = pin[1], fout = pout[0], ferr = perr[0];
    if (input.len == 0) { close(fin); fin = -1; }
    bool timed_out = false;
    while (fout >= 0 || ferr >= 0) {
        struct pollfd ps[3];
        int np = 0, wi = -1, oi = -1, ei = -1;
        if (fin >= 0) { wi = np; ps[np].fd = fin; ps[np].events = POLLOUT; ps[np++].revents = 0; }
        if (fout >= 0) { oi = np; ps[np].fd = fout; ps[np].events = POLLIN; ps[np++].revents = 0; }
        if (ferr >= 0) { ei = np; ps[np].fd = ferr; ps[np].events = POLLIN; ps[np++].revents = 0; }
        int wait = -1;
        if (deadline) {
            int64_t left = deadline - tn_ms_now();
            if (left <= 0) { timed_out = true; break; }
            wait = left > 1000000 ? 1000000 : (int)left;
        }
        int k = poll(ps, (nfds_t)np, wait);
        if (k < 0 && errno == EINTR) continue;
        if (k < 0) break;
        if (wi >= 0 && ps[wi].revents) {
            ssize_t w = write(fin, input.p + sent, (size_t)(input.len - sent));
            if (w > 0) sent += w;
            if ((w < 0 && errno != EAGAIN && errno != EINTR) || sent == input.len) { close(fin); fin = -1; }
        }
        char chunk[1 << 16];
        if (oi >= 0 && ps[oi].revents) {
            ssize_t r = read(fout, chunk, sizeof chunk);
            if (r > 0) tn_buf_add(&ob, chunk, r);
            else if (r == 0 || errno != EINTR) { close(fout); fout = -1; }
        }
        if (ei >= 0 && ps[ei].revents) {
            ssize_t r = read(ferr, chunk, sizeof chunk);
            if (r > 0) tn_buf_add(&eb, chunk, r);
            else if (r == 0 || errno != EINTR) { close(ferr); ferr = -1; }
        }
    }
    int st = 0;
    for (;;) {
        if (timed_out) { kill(pid, SIGKILL); while (waitpid(pid, &st, 0) < 0 && errno == EINTR) {} break; }
        pid_t w = waitpid(pid, &st, deadline ? WNOHANG : 0);
        if (w == pid) break;
        if (w < 0 && errno != EINTR) break;
        if (deadline && tn_ms_now() >= deadline) { timed_out = true; continue; }
        if (deadline) { struct timespec t = {0, 2000000}; nanosleep(&t, NULL); }
    }
    if (fin >= 0) close(fin);
    if (fout >= 0) close(fout);
    if (ferr >= 0) close(ferr);
    int64_t no = ob.len, ne = eb.len;
    tn_List_Int l = tn_List_Int_alloc(4 + no + ne);
    l->data[0] = WIFEXITED(st) ? WEXITSTATUS(st) : -1;
    l->data[1] = WIFSIGNALED(st) ? WTERMSIG(st) : 0;
    l->data[2] = timed_out ? 1 : 0;
    l->data[3] = no;
    l->len = 4;
    tn_bytes_put(l, ob.p + sizeof(tn_rc), no);
    tn_bytes_put(l, eb.p + sizeof(tn_rc), ne);
    tn_free(ob.p);
    tn_free(eb.p);
    *res = l;
    return TN_IO_OK;
}

/* ---------- workers and channels (v2: lib/v2/prelude.tn) ----------
 * A worker (Workers.spawn) is an OS thread with a heap of its own: in a
 * program compiled with TN_MT every allocator list, pool and release queue
 * is thread-local. Workers share nothing: a value given to spawn, returned
 * by a worker or sent on a channel is deep-copied by the sender (T_copy,
 * generated per type; it reads the original without touching its counts),
 * and the receiver owns the copy. So reference counts stay plain integers.
 * Only the handles below (Sender/Receiver = tn_Chan, Worker = tn_Worker) are
 * shared, with atomic counts.
 * One lock (tn_mt_mu) guards every channel and worker. It also counts the
 * threads waiting on a channel or a join: when every live thread waits, none
 * can ever wake, and the program traps with "deadlock" at the main thread's
 * wait (the interpreter detects the same situation and reports the same). */
typedef uint8_t tn_Workers;
TN_TRIVIAL(tn_Workers)
TN_INCOMPARABLE(tn_Workers)
static TN_UNUSED void tn_Workers_show(tn_buf *b, tn_Workers x, int mode) { (void)x; (void)mode; tn_buf_cstr(b, "<Workers>"); }

TN_STATE pthread_mutex_t tn_mt_mu TN_INIT(PTHREAD_MUTEX_INITIALIZER);
TN_STATE int64_t tn_mt_live TN_INIT(1);
TN_STATE int64_t tn_mt_blocked;
TN_STATE const char *tn_mt_main_loc TN_INIT("?");

TN_NORETURN static void tn_mt_deadlock(void) {
    tn_trap("deadlock: every worker is waiting for a channel or a join", tn_mt_main_loc);
}
/* Wait on cv (tn_mt_mu held). A thread woken by tn_mt_wake was already
 * uncounted by its waker, through a wake token; one that wakes without a
 * token (spuriously) uncounts itself. */
static void tn_mt_wait(pthread_cond_t *cv, int64_t *waiting, int64_t *wakes, const char *loc) {
    (*waiting)++;
    tn_mt_blocked++;
    if (!tn_in_worker) tn_mt_main_loc = loc;
    if (tn_mt_blocked == tn_mt_live) tn_mt_deadlock();
    pthread_cond_wait(cv, &tn_mt_mu);
    if (*wakes > 0) {
        (*wakes)--;
    } else {
        (*waiting)--;
        tn_mt_blocked--;
    }
}
static void tn_mt_wake(pthread_cond_t *cv, int64_t *waiting, int64_t *wakes, bool all) {
    int64_t n = all ? *waiting : *waiting > 0;
    if (n == 0) return;
    *waiting -= n;
    *wakes += n;
    tn_mt_blocked -= n;
    if (all) pthread_cond_broadcast(cv); else pthread_cond_signal(cv);
}

/* A channel: a ring buffer of elements of esz bytes (each one a value owned
 * by the channel), closed only by Sender.close. */
typedef struct tn_chan_s {
    int64_t rc; /* atomic */
    int64_t esz, head, len, cap, waiting, wakes;
    bool closed;
    void (*rel)(void *); /* releases one element in place; NULL for trivial types */
    char *buf;
    pthread_cond_t cv;
} *tn_Chan;
static TN_UNUSED tn_Chan tn_Chan_retain(tn_Chan c) {
    __atomic_fetch_add(&c->rc, 1, __ATOMIC_RELAXED);
    return c;
}
static TN_UNUSED void tn_Chan_release(tn_Chan c) {
    if (__atomic_sub_fetch(&c->rc, 1, __ATOMIC_ACQ_REL) != 0) return;
    for (int64_t i = 0; i < c->len && c->rel; i++) c->rel(c->buf + ((c->head + i) % c->cap) * c->esz);
    free(c->buf);
    pthread_cond_destroy(&c->cv);
    free(c);
}
/* Sender[T] and Receiver[T] are the same channel pointer, for every T. */
typedef tn_Chan tn_Sender, tn_Receiver;
#define TN_CHAN_HANDLE(T, S)                                                                \
    static inline TN_UNUSED T T##_retain(T c) { return tn_Chan_retain(c); }                \
    static inline TN_UNUSED void T##_release(T c) { tn_Chan_release(c); }                  \
    static TN_UNUSED void T##_show(tn_buf *b, T c, int mode) { (void)c; (void)mode; tn_buf_cstr(b, S); } \
    TN_INCOMPARABLE(T)
TN_CHAN_HANDLE(tn_Sender, "<Sender>")
TN_CHAN_HANDLE(tn_Receiver, "<Receiver>")
static TN_UNUSED tn_Chan tn_chan_new(int64_t esz, void (*rel)(void *)) {
    tn_Chan c = calloc(1, sizeof *c);
    if (!c) tn_oom();
    c->rc = 1;
    c->esz = esz > 0 ? esz : 1;
    c->rel = rel;
    pthread_cond_init(&c->cv, NULL);
    return c;
}
/* Takes ownership of *x (esz bytes). */
static TN_UNUSED void tn_chan_send(tn_Chan c, void *x, const char *loc) {
    pthread_mutex_lock(&tn_mt_mu);
    if (c->closed) {
        pthread_mutex_unlock(&tn_mt_mu);
        if (c->rel) c->rel(x);
        tn_trap("send on a closed channel", loc);
    }
    if (c->len == c->cap) {
        int64_t cap = c->cap ? c->cap * 2 : 16;
        char *nb = malloc((size_t)(cap * c->esz));
        if (!nb) tn_oom();
        for (int64_t i = 0; i < c->len; i++) memcpy(nb + i * c->esz, c->buf + ((c->head + i) % c->cap) * c->esz, (size_t)c->esz);
        free(c->buf);
        c->buf = nb;
        c->cap = cap;
        c->head = 0;
    }
    memcpy(c->buf + ((c->head + c->len) % c->cap) * c->esz, x, (size_t)c->esz);
    c->len++;
    tn_mt_wake(&c->cv, &c->waiting, &c->wakes, false);
    pthread_mutex_unlock(&tn_mt_mu);
}
/* The next element into *out (true), or false: closed and empty, or (when
 * not waiting) empty. */
static TN_UNUSED bool tn_chan_recv(tn_Chan c, void *out, bool wait, const char *loc) {
    pthread_mutex_lock(&tn_mt_mu);
    while (wait && c->len == 0 && !c->closed) tn_mt_wait(&c->cv, &c->waiting, &c->wakes, loc);
    bool got = c->len > 0;
    if (got) {
        memcpy(out, c->buf + c->head * c->esz, (size_t)c->esz);
        c->head = (c->head + 1) % c->cap;
        c->len--;
    }
    pthread_mutex_unlock(&tn_mt_mu);
    return got;
}
static TN_UNUSED void tn_chan_close(tn_Chan c) {
    pthread_mutex_lock(&tn_mt_mu);
    c->closed = true;
    tn_mt_wake(&c->cv, &c->waiting, &c->wakes, true);
    pthread_mutex_unlock(&tn_mt_mu);
}

/* A worker: run(t) computes res (rsz bytes) from f and arg (asz bytes),
 * which the spawning thread copied for it. */
typedef struct tn_task_s {
    int64_t rc; /* atomic */
    bool done;
    int64_t waiting, wakes;
    pthread_cond_t cv;
    void (*run)(struct tn_task_s *);
    void (*rel)(void *); /* releases res in place; NULL for trivial types */
    tn_fn f;
    void *arg, *res;
} *tn_Worker;
static TN_UNUSED tn_Worker tn_Worker_retain(tn_Worker t) {
    __atomic_fetch_add(&t->rc, 1, __ATOMIC_RELAXED);
    return t;
}
static TN_UNUSED void tn_Worker_release(tn_Worker t) {
    if (__atomic_sub_fetch(&t->rc, 1, __ATOMIC_ACQ_REL) != 0) return;
    if (t->done && t->rel) t->rel(t->res);
    pthread_cond_destroy(&t->cv);
    free(t->arg);
    free(t->res);
    free(t);
}
static TN_UNUSED void tn_Worker_show(tn_buf *b, tn_Worker t, int mode) { (void)t; (void)mode; tn_buf_cstr(b, "<Worker>"); }
TN_INCOMPARABLE(tn_Worker)
static TN_UNUSED tn_Worker tn_task_new(int64_t asz, int64_t rsz, void (*run)(tn_Worker), void (*rel)(void *)) {
    tn_Worker t = calloc(1, sizeof *t);
    if (!t) tn_oom();
    t->rc = 1;
    t->run = run;
    t->rel = rel;
    t->arg = calloc(1, (size_t)(asz > 0 ? asz : 1));
    t->res = calloc(1, (size_t)(rsz > 0 ? rsz : 1));
    if (!t->arg || !t->res) tn_oom();
    pthread_cond_init(&t->cv, NULL);
    return t;
}
#define TN_WORKER_STACK ((size_t)256 << 20)
static void *tn_task_thread(void *p) {
    tn_Worker t = p;
    tn_in_worker = true;
    /* the stack overflow handler runs on a stack of its own (unless a
     * sanitizer has given the thread one already) */
    stack_t old, ss = {.ss_sp = NULL, .ss_size = 1 << 16, .ss_flags = 0};
    if (sigaltstack(NULL, &old) == 0 && (old.ss_flags & SS_DISABLE)) {
        ss.ss_sp = malloc(ss.ss_size);
        if (ss.ss_sp) sigaltstack(&ss, NULL);
    }
    t->run(t);
    pthread_mutex_lock(&tn_mt_mu);
    t->done = true;
    tn_mt_wake(&t->cv, &t->waiting, &t->wakes, true);
    tn_mt_live--;
    if (tn_mt_blocked > 0 && tn_mt_blocked == tn_mt_live) tn_mt_deadlock();
    pthread_mutex_unlock(&tn_mt_mu);
    tn_Worker_release(t);
    /* the worker's heap goes back to malloc */
    for (int c = 1; c <= TN_SMALL_MAX / 16; c++) {
        while (tn_freelist[c]) {
            void *h = tn_freelist[c];
            tn_freelist[c] = *(void **)((char *)h + 16);
            free(h);
        }
    }
    free(tn_defer_q);
    if (ss.ss_sp) {
        stack_t off = {.ss_sp = NULL, .ss_size = 0, .ss_flags = SS_DISABLE};
        sigaltstack(&off, NULL);
        free(ss.ss_sp);
    }
    return NULL;
}
static TN_UNUSED void tn_task_start(tn_Worker t, const char *loc) {
    pthread_mutex_lock(&tn_mt_mu);
    tn_mt_live++;
    pthread_mutex_unlock(&tn_mt_mu);
    tn_Worker_retain(t); /* the thread's reference */
    pthread_attr_t at;
    pthread_attr_init(&at);
    pthread_attr_setstacksize(&at, TN_WORKER_STACK);
    pthread_attr_setdetachstate(&at, PTHREAD_CREATE_DETACHED);
    pthread_t th;
    int e = pthread_create(&th, &at, tn_task_thread, t);
    pthread_attr_destroy(&at);
    if (e != 0) tn_trapf(loc, "cannot start a worker: %s", strerror(e));
}
/* Waits until the worker is done; its result is then at t->res. */
static TN_UNUSED void tn_task_join(tn_Worker t, const char *loc) {
    pthread_mutex_lock(&tn_mt_mu);
    while (!t->done) tn_mt_wait(&t->cv, &t->waiting, &t->wakes, loc);
    pthread_mutex_unlock(&tn_mt_mu);
}
static TN_UNUSED tn_Int tn_cores(void) {
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    return n > 0 ? n : 1;
}

#ifdef TN_MT
/* Deep copies (the sender's side of every transfer). */
#define TN_COPY_ID(T) static inline TN_UNUSED T T##_copy(T x) { return x; }
TN_COPY_ID(tn_Int)
TN_COPY_ID(tn_Float)
TN_COPY_ID(tn_Bool)
TN_COPY_ID(tn_Unit)
TN_COPY_ID(tn_Console)
TN_COPY_ID(tn_Clock)
TN_COPY_ID(tn_Net)
TN_COPY_ID(tn_Proc)
TN_COPY_ID(tn_Workers)
TN_COPY_ID(tn_Listener) /* never sent (not Send); here so every type has a copy */
TN_COPY_ID(tn_Conn)
TN_COPY_ID(tn_Poller)
static TN_UNUSED tn_Str tn_Str_copy(tn_Str s) { return s.o ? tn_str_new(s.p, s.len) : s; }
static TN_UNUSED tn_Fs tn_Fs_copy(tn_Fs f) { return tn_fs_make(tn_Str_copy(f->root), f->att, f->wr); }
static TN_UNUSED tn_fn tn_fn_copy(tn_fn f) {
    if (f.env) f.env = f.env->copy(f.env);
    return f;
}
static TN_UNUSED tn_Sender tn_Sender_copy(tn_Sender c) { return tn_Chan_retain(c); }
static TN_UNUSED tn_Receiver tn_Receiver_copy(tn_Receiver c) { return tn_Chan_retain(c); }
static TN_UNUSED tn_Worker tn_Worker_copy(tn_Worker t) { return tn_Worker_retain(t); }
#define TN_LIST_COPY(L, T)                                                                \
    static TN_UNUSED L L##_copy(L l) {                                                     \
        if (!l) return NULL;                                                               \
        L c = L##_alloc(l->len);                                                           \
        for (int64_t i = 0; i < l->len; i++) c->data[i] = T##_copy(l->data[i]);           \
        c->len = l->len;                                                                   \
        return c;                                                                          \
    }
#define TN_MAP_COPY(M, K, V)                                                               \
    static TN_UNUSED M M##_copy(M m) {                                                     \
        if (!m) return NULL;                                                               \
        M c = M##_alloc(m->len);                                                           \
        for (int64_t i = 0; i < m->n; i++)                                                 \
            if (m->e[i].live) {                                                            \
                struct M##_e x = m->e[i];                                                  \
                x.k = K##_copy(x.k); x.v = V##_copy(x.v);                                  \
                c->e[c->n++] = x;                                                          \
            }                                                                              \
        c->len = c->n;                                                                     \
        if (c->idx) M##_reindex(c, c->icap);                                               \
        return c;                                                                          \
    }
TN_LIST_COPY(tn_List_Str, tn_Str)
TN_LIST_COPY(tn_List_Int, tn_Int)
/* Nullary variants of boxed enums are static objects shared by every
 * thread: their counts are never changed (TN_RC_STATIC and above). */
#define TN_RC_STATIC (INT64_MAX / 4)
#endif

#endif
