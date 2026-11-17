/* liblogcapture: LD_PRELOAD shim that mirrors Android log calls to
 * stderr (which spawn_hal wires to /dev/kmsg), because logd is dead
 * in this recovery and libbase CHECK messages (the HALs' exact abort
 * reasons, including the servicemanager status) otherwise vanish.
 * The real log functions' only live destination was logd, so the
 * hooks capture and swallow (returning success); __android_log_assert
 * captures, then aborts via the process's own abort().
 * Built -nostdlib like the stage9 stub: undefined symbols (write,
 * vsnprintf, abort) resolve from the host process's bionic libc.
 */
#include <stdarg.h>
#include <stddef.h>

extern long write(int fd, const void *buf, unsigned long count);
extern int vsnprintf(char *str, unsigned long size, const char *format, va_list ap);
extern void abort(void);

static unsigned long xstrlen(const char *s) {
    unsigned long n = 0;
    while (s && s[n]) n++;
    return n;
}

static void emit(const char *tag, const char *text) {
    char buf[1200];
    int n = 0;
    const char *pre = "LOGCAP[";
    while (*pre && n < 1100) buf[n++] = *pre++;
    if (tag) {
        unsigned long i = 0;
        while (tag[i] && n < 1100) buf[n++] = tag[i++];
    }
    const char *mid = "]: ";
    while (*mid && n < 1100) buf[n++] = *mid++;
    if (text) {
        unsigned long i = 0;
        while (text[i] && n < 1150) buf[n++] = text[i++];
    }
    buf[n++] = '\n';
    write(2, buf, (unsigned long)n);
}

int __android_log_write(int prio, const char *tag, const char *text) {
    (void)prio;
    emit(tag, text);
    return text ? (int)xstrlen(text) : 0;
}

int __android_log_buf_write(int bufID, int prio, const char *tag, const char *text) {
    (void)bufID; (void)prio;
    emit(tag, text);
    return text ? (int)xstrlen(text) : 0;
}

int __android_log_vprint(int prio, const char *tag, const char *fmt, va_list ap) {
    (void)prio;
    char buf[1000];
    int n = vsnprintf(buf, sizeof(buf), fmt ? fmt : "", ap);
    emit(tag, buf);
    return n;
}

int __android_log_print(int prio, const char *tag, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int n = __android_log_vprint(prio, tag, fmt, ap);
    va_end(ap);
    return n;
}

void __android_log_assert(const char *cond, const char *tag, const char *fmt, ...) {
    char buf[1000];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt ? fmt : "", ap);
    va_end(ap);
    emit(tag, buf);
    if (cond) emit(tag, cond);
    abort();
    __builtin_unreachable();
}
