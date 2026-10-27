/* Straightforward C: open-addressing hash table of (word, count). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef struct { char *w; size_t n; long count; } E;
static E *tab; static size_t cap = 1 << 16, used;
static uint64_t h(const char *s, size_t n) { uint64_t x = 1469598103934665603ULL; for (size_t i = 0; i < n; i++) x = (x ^ (unsigned char)s[i]) * 1099511628211ULL; return x; }
static void grow(void);
static void add(char *s, size_t n) {
    if (used * 4 > cap * 3) grow();
    size_t i = h(s, n) & (cap - 1);
    while (tab[i].w) { if (tab[i].n == n && !memcmp(tab[i].w, s, n)) { tab[i].count++; return; } i = (i + 1) & (cap - 1); }
    tab[i].w = s; tab[i].n = n; tab[i].count = 1; used++;
}
static void grow(void) {
    E *old = tab; size_t oc = cap; cap *= 2; tab = calloc(cap, sizeof(E)); used = 0;
    for (size_t i = 0; i < oc; i++) if (old[i].w) { size_t j = h(old[i].w, old[i].n) & (cap - 1); while (tab[j].w) j = (j + 1) & (cap - 1); tab[j] = old[i]; used++; }
    free(old);
}
static int cmp(const void *a, const void *b) {
    const E *x = a, *y = b;
    if (x->count != y->count) return x->count > y->count ? -1 : 1;
    size_t n = x->n < y->n ? x->n : y->n; int c = memcmp(x->w, y->w, n);
    return c ? c : (x->n > y->n) - (x->n < y->n);
}
int main(void) {
    size_t len = 0, bc = 1 << 20; char *buf = malloc(bc); size_t r;
    while ((r = fread(buf + len, 1, bc - len, stdin)) > 0) { len += r; if (len == bc) { bc *= 2; buf = realloc(buf, bc); } }
    for (size_t i = 0; i < len; i++) if (buf[i] >= 'A' && buf[i] <= 'Z') buf[i] += 32;
    tab = calloc(cap, sizeof(E));
    size_t i = 0;
    while (i < len) {
        while (i < len && (buf[i] == ' ' || buf[i] == '\n' || buf[i] == '\t' || buf[i] == '\r')) i++;
        size_t s = i;
        while (i < len && !(buf[i] == ' ' || buf[i] == '\n' || buf[i] == '\t' || buf[i] == '\r')) i++;
        if (i > s) add(buf + s, i - s);
    }
    E *all = malloc(used * sizeof(E)); size_t k = 0;
    for (size_t j = 0; j < cap; j++) if (tab[j].w) all[k++] = tab[j];
    qsort(all, k, sizeof(E), cmp);
    for (size_t j = 0; j < 10 && j < k; j++) printf("%ld %.*s\n", all[j].count, (int)all[j].n, all[j].w);
    return 0;
}
