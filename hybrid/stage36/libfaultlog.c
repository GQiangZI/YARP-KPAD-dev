/* libfaultlog.so -- v3.20 diagnostic preload for keystore2 ONLY.
 * Installs SIGSEGV/SIGABRT/SIGBUS handlers that dump a backtrace
 * (library + offset per frame, via backtrace_symbols_fd) to
 * /dev/kmsg, then exit. Everything resolves from the host process's
 * libc at load; built -nostdlib like liblogcapture. */
typedef unsigned long size_t;
extern int open(const char *, int, ...);
extern long write(int, const void *, size_t);
extern void _exit(int);
extern int backtrace(void **, int);
extern void backtrace_symbols_fd(void *const *, int, int);
extern int sigaction(int, const void *, void *);
extern int sigemptyset(void *);
struct k_sigaction {
    void (*handler)(int, void *, void *);
    unsigned long flags;
    void (*restorer)(void);
    unsigned long mask[2];
};
#define SA_SIGINFO 0x00000004
#define O_WRONLY 1
static void fault_handler(int sig, void *info, void *uctx) {
    (void)info; (void)uctx;
    int fd = open("/dev/kmsg", O_WRONLY);
    if (fd < 0) fd = 2;
    const char *msg = "FAULTLOG: fatal signal in keystore2, backtrace follows\n";
    long n = 0; while (msg[n]) n++;
    write(fd, msg, (size_t)n);
    void *frames[32];
    int count = backtrace(frames, 32);
    if (count > 0) backtrace_symbols_fd(frames, count, fd);
    _exit(128 + sig);
}
__attribute__((constructor)) static void faultlog_init(void) {
    struct k_sigaction sa;
    sa.handler = fault_handler;
    sa.flags = SA_SIGINFO;
    sa.restorer = 0;
    sa.mask[0] = 0; sa.mask[1] = 0;
    sigemptyset(&sa.mask);
    sigaction(11, &sa, 0); /* SIGSEGV */
    sigaction(6, &sa, 0);  /* SIGABRT */
    sigaction(7, &sa, 0);  /* SIGBUS */
}
