#include <stdio.h>
#include "../checked.h"
static int64_t fib(int64_t n) { return n < 2 ? n : ck_add(fib(ck_sub(n, 1)), fib(ck_sub(n, 2))); }
int main(void) { printf("%lld\n", (long long)fib(38)); return 0; }
