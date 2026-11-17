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

/* v2 additions: modern libbase (SDK 35/36/37 alike) logs through
 * __android_log_logd_logger, which forwards the message struct to
 * __android_log_write_log_message. The v1 hooks never saw the HALs'
 * CHECK messages because neither function was interposed. The
 * struct layout is android/log.h's __android_log_message. */
struct log_message {
    unsigned long struct_size;
    int buffer_id;
    int priority;
    const char *tag;
    const char *file;
    unsigned int line;
    const char *message;
};

int __android_log_write_log_message(const struct log_message *m) {
    if (m && m->message) emit(m->tag ? m->tag : "liblog", m->message);
    return 0;
}

typedef void (*logger_fn)(const struct log_message *);
void __android_log_logd_logger(const struct log_message *m) {
    if (m && m->message) emit(m->tag ? m->tag : "libbase", m->message);
}

/* v3 (v3.8): the payload's SDK36 libbinder_ndk imports
 * android::binder::os::get_trace_enabled_tags() from libbinder.so;
 * the ramdisk's SDK35 libbinder (now paired with the 36 ndk in
 * twrpbinder) does not export it. Provide it here (preloaded first):
 * 0 = no binder tracing tags enabled, correct for recovery. */
unsigned long v38_get_trace_enabled_tags(void) { return 0; }
__asm__(".global _ZN7android6binder2os22get_trace_enabled_tagsEv\n"
        ".set _ZN7android6binder2os22get_trace_enabled_tagsEv, v38_get_trace_enabled_tags");

/* v4 (v3.9): Accessor-family stubs. The payload's SDK36 libbinder_ndk
 * is BIND_NOW: bionic resolves ALL its imports eagerly at load, and
 * the ramdisk's SDK35 libbinder lacks the 5 Accessor functions. These
 * are only used by RPC-over-socket services; our HALs never call
 * them -- they only need to EXIST for the loader. Stub shape: zero
 * the sret buffer when present (null sp / empty weak_ptr), return 0
 * (false for validateAccessor). */
__asm__(
".text\n"
".globl v39_accessor_stub\n"
"v39_accessor_stub:\n"
"  cbz x8, 1f\n"
"  str xzr, [x8]\n"
"  str xzr, [x8, #8]\n"
"1:\n"
"  mov w0, wzr\n"
"  ret\n"
".globl _ZN7android14createAccessorERKNS_8String16EONSt3__18functionIFiS2_P8sockaddrjEEE\n"
".set _ZN7android14createAccessorERKNS_8String16EONSt3__18functionIFiS2_P8sockaddrjEEE, v39_accessor_stub\n"
".globl _ZN7android16delegateAccessorERKNS_8String16ERKNS_2spINS_7IBinderEEEPS5_\n"
".set _ZN7android16delegateAccessorERKNS_8String16ERKNS_2spINS_7IBinderEEEPS5_, v39_accessor_stub\n"
".globl _ZN7android16validateAccessorERKNS_8String16ERKNS_2spINS_7IBinderEEE\n"
".set _ZN7android16validateAccessorERKNS_8String16ERKNS_2spINS_7IBinderEEE, v39_accessor_stub\n"
".globl _ZN7android19addAccessorProviderEONSt3__13setINS0_12basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEENS0_4lessIS7_EENS5_IS7_EEEEONS0_8functionIFNS_2spINS_7IBinderEEERKNS_8String16EEEE\n"
".set _ZN7android19addAccessorProviderEONSt3__13setINS0_12basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEENS0_4lessIS7_EENS5_IS7_EEEEONS0_8functionIFNS_2spINS_7IBinderEEERKNS_8String16EEEE, v39_accessor_stub\n"
".globl _ZN7android22removeAccessorProviderENSt3__18weak_ptrINS_16AccessorProviderEEE\n"
".set _ZN7android22removeAccessorProviderENSt3__18weak_ptrINS_16AccessorProviderEEE, v39_accessor_stub\n");
