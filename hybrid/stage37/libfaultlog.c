/* libfaultlog.so v2 -- diagnostic preload for keystore2 ONLY.
 * v1 used a hand-rolled struct sigaction whose layout does not match
 * bionic's; the handler never ran (crash stayed silent). v2 uses
 * signal() (bionic wraps the ABI correctly) and writes to fd 2
 * (spawn_hal points stderr at /dev/kmsg) before unwinding. */
typedef unsigned long size_t;
extern long write(int, const void *, size_t);
extern void _exit(int);
extern int backtrace(void **, int);
extern void backtrace_symbols_fd(void *const *, int, int);
typedef void (*sighandler_t)(int);
extern sighandler_t signal(int, sighandler_t);
static void emit(const char *s) {
    long n = 0; while (s[n]) n++;
    write(2, s, (size_t)n);
}
static void fault_handler(int sig) {
    emit("FAULTLOG: fatal signal caught, backtrace follows\n");
    void *frames[32];
    int count = backtrace(frames, 32);
    if (count > 0) backtrace_symbols_fd(frames, count, 2);
    emit("FAULTLOG: backtrace end\n");
    _exit(128 + sig);
}
__attribute__((constructor)) static void faultlog_init(void) {
    signal(11, fault_handler); /* SIGSEGV */
    signal(6, fault_handler);  /* SIGABRT */
    signal(7, fault_handler);  /* SIGBUS */
    emit("FAULTLOG: handlers installed\n");
}
