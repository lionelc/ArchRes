/* gapCR pilot known-truth controls, loaded with LD_PRELOAD into one arm's process.
   GAPCR_PLANT_US=n : the constructor busy-waits n microseconds of wall time, then unsets the variable so that a
                      wrapper's exec does not plant twice. n = 0 is the null plant (the code runs, adds nothing).
   A sham switch is GAPCR_SHAM=1 with no preload at all. */
#define _GNU_SOURCE
#include <stdlib.h>
#include <time.h>

static long now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1000000000L + t.tv_nsec; }

__attribute__((constructor)) static void gapcr_plant(void) {
    const char *s = getenv("GAPCR_PLANT_US");
    if (!s) return;
    long ns = atol(s) * 1000L;
    unsetenv("GAPCR_PLANT_US");
    if (ns <= 0) return;
    long t0 = now_ns();
    volatile unsigned long x = 0;
    while (now_ns() - t0 < ns) x++;
}
