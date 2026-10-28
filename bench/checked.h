/* Overflow-checked 64-bit integer arithmetic for the C references
 * (bench/README.md, "Fairness"): Tenon's Int arithmetic traps on overflow
 * (runtime/tenon.h tn_add), so a reference computes the same defined result
 * with the same checks instead of relying on signed overflow being undefined
 * behaviour, which lets the C compiler transform code Tenon may not (gcc
 * turned the recursive fib into loops). On overflow: a trap message on
 * standard error and exit status 70, as Tenon. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

__attribute__((noreturn, cold)) static void ck_trap(void) {
    fputs("trap: integer overflow\n", stderr);
    exit(70);
}
static inline int64_t ck_add(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_expect(__builtin_add_overflow(a, b, &r), 0)) ck_trap();
    return r;
}
static inline int64_t ck_sub(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_expect(__builtin_sub_overflow(a, b, &r), 0)) ck_trap();
    return r;
}
static inline int64_t ck_mul(int64_t a, int64_t b) {
    int64_t r;
    if (__builtin_expect(__builtin_mul_overflow(a, b, &r), 0)) ck_trap();
    return r;
}
