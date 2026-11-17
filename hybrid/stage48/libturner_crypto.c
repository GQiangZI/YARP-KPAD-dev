/* SPDX-License-Identifier: Apache-2.0
 * Recovery-only bridge for the verified turner v3.30 hybrid.
 * No C++ ABI, global Binder replacement, or service restart is involved.
 * Build without a sysroot; undefined functions resolve from recovery's bionic.
 */
#include <stdarg.h>
#include <stddef.h>

extern void *dlsym(void *, const char *);
extern int open(const char *, int, ...);
extern int close(int);
extern long read(int, void *, unsigned long);
extern long write(int, const void *, unsigned long);
extern long lseek(int, long, int);
extern long readlink(const char *, char *, unsigned long);
extern void *malloc(unsigned long);
extern void free(void *);
extern int memfd_create(const char *, unsigned int);
extern int snprintf(char *, unsigned long, const char *, ...);
extern int pthread_create(unsigned long *, const void *, void *(*)(void *), void *);
extern int pthread_detach(unsigned long);

typedef struct turner_FILE FILE;
extern FILE *fdopen(int, const char *);

#define NEXT ((void *)-1L)
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 0100
#define O_APPEND 02000
#define O_NONBLOCK 04000
#define O_CLOEXEC 02000000
#define O_TMPFILE 020000000
#define MAX_FSTAB 65536
#ifndef TURNER_ADDITIONAL_FSTAB
#define TURNER_ADDITIONAL_FSTAB "/etc/additional.fstab"
#endif

typedef int (*open_fn)(const char *, int, ...);
typedef void *(*lookup_fn)(const char *);
typedef void (*strong_fn)(void *);
static int enabled;

static int eq(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static size_t length(const char *s) {
    size_t n = 0;
    while (s[n]) ++n;
    return n;
}
static int span_eq(const char *s, size_t n, const char *v) {
    return length(v) == n && __builtin_memcmp(s, v, n) == 0;
}
static int space(char c) { return c == ' ' || c == '\t' || c == '\r'; }

static void log_line(const char *s) {
    open_fn real = (open_fn)dlsym(NEXT, "open");
    if (!real) return;
    const char *paths[] = {"/tmp/turner-crypto.log", "/dev/kmsg"};
    char b[700];
    int n = snprintf(b, sizeof(b), "TURNER-CRYPTO v3.35: %s\n", s);
    if (n <= 0) return;
    size_t count = (size_t)n < sizeof(b) ? (size_t)n : sizeof(b) - 1;
    for (unsigned i = 0; i < 2; ++i) {
        int fd = real(paths[i], O_WRONLY | O_CLOEXEC | O_NONBLOCK |
                      (i == 0 ? O_CREAT | O_APPEND : 0), 0600);
        if (fd >= 0) { (void)write(fd, b, count); close(fd); }
    }
}

/* Append only to field 5 of a /data row carrying the exact OS4 metadata key
 * directory. Preserve all installed-ROM flags, comments, other rows and any
 * explicit metadata cipher. Return -1 on overflow; callers keep the real file.
 */
static long normalize_fstab(const char *in, size_t size, char *out, size_t cap) {
    const char add[] = ",metadata_encryption=aes-256-xts";
    size_t used = 0;
    int changed = 0;
    for (size_t pos = 0; pos < size;) {
        size_t end = pos;
        while (end < size && in[end] != '\n') ++end;
        size_t starts[5], ends[5], p = pos;
        int fields = 0;
        while (fields < 5) {
            while (p < end && space(in[p])) ++p;
            if (p == end || in[p] == '#') break;
            starts[fields] = p;
            while (p < end && !space(in[p])) ++p;
            ends[fields++] = p;
        }
        int keydir = 0, has_cipher = 0;
        if (fields == 5 && span_eq(in + starts[1], ends[1] - starts[1], "/data")) {
            for (size_t t = starts[4]; t < ends[4];) {
                size_t te = t;
                while (te < ends[4] && in[te] != ',') ++te;
                if (span_eq(in + t, te - t,
                            "keydirectory=/metadata/vold/metadata_encryption")) keydir = 1;
                const char prefix[] = "metadata_encryption=";
                if (te - t >= sizeof(prefix) - 1 &&
                    !__builtin_memcmp(in + t, prefix, sizeof(prefix) - 1)) has_cipher = 1;
                t = te + 1;
            }
        }
        int patch = fields == 5 && keydir && !has_cipher;
        size_t bytes = end - pos + (end < size);
        size_t extra = patch ? sizeof(add) - 1 : 0;
        if (used + bytes + extra > cap) return -1;
        if (patch) {
            size_t head = ends[4] - pos;
            __builtin_memcpy(out + used, in + pos, head); used += head;
            __builtin_memcpy(out + used, add, extra); used += extra;
            __builtin_memcpy(out + used, in + ends[4], bytes - head); used += bytes - head;
            ++changed;
        } else {
            __builtin_memcpy(out + used, in + pos, bytes); used += bytes;
        }
        pos += bytes;
    }
    return changed ? (long)used : 0;
}

static int target_path(const char *path) {
    return enabled && (eq(path, TURNER_ADDITIONAL_FSTAB) ||
                       eq(path, "/system/etc/additional.fstab"));
}

static int normalized_fd(int original, int flags) {
    if (original < 0 || (flags & 3) != O_RDONLY) return original;
    char *in = (char *)malloc(MAX_FSTAB + 1);
    char *out = (char *)malloc(MAX_FSTAB + 1024);
    int result = original;
    if (!in || !out) goto done;
    size_t n = 0;
    while (n <= MAX_FSTAB) {
        long r = read(original, in + n, MAX_FSTAB + 1 - n);
        if (r < 0) goto rewind;
        if (r == 0) break;
        n += (size_t)r;
        if (n > MAX_FSTAB) goto rewind;
    }
    long count = normalize_fstab(in, n, out, MAX_FSTAB + 1024);
    if (count <= 0) goto rewind;
    int fd = memfd_create("turner-crypto-fstab", (flags & O_CLOEXEC) ? 1 : 0);
    if (fd < 0) goto rewind;
    size_t offset = 0;
    while (offset < (size_t)count) {
        long w = write(fd, out + offset, (size_t)count - offset);
        if (w <= 0) { close(fd); goto rewind; }
        offset += (size_t)w;
    }
    if (lseek(fd, 0, 0) < 0) { close(fd); goto rewind; }
    close(original);
    result = fd;
    log_line("fstab: supplied missing /data metadata cipher at read time (RAM only)");
    goto done;
rewind:
    (void)lseek(original, 0, 0);
done:
    free(in); free(out);
    return result;
}

static int open_common(const char *symbol, const char *path, int flags, unsigned mode) {
    open_fn real = (open_fn)dlsym(NEXT, symbol);
    if (!real) real = (open_fn)dlsym(NEXT, "open");
    if (!real) return -1;
    int fd = real(path, flags, mode);
    return target_path(path) ? normalized_fd(fd, flags) : fd;
}

#define OPEN_HOOK(name) \
int name(const char *path, int flags, ...) { \
    unsigned mode = 0; \
    if ((flags & O_CREAT) || (flags & O_TMPFILE) == O_TMPFILE) { \
        va_list ap; va_start(ap, flags); mode = va_arg(ap, unsigned); va_end(ap); \
    } \
    return open_common(#name, path, flags, mode); \
}
OPEN_HOOK(open)
OPEN_HOOK(open64)

/* Android's fortified fcntl.h routes ReadFileToString through __open_2.
 * Keep the real fortify checks, then normalize only this exact file. */
int __open_2(const char *path, int flags) {
    typedef int (*fortified_fn)(const char *, int);
    fortified_fn real = (fortified_fn)dlsym(NEXT, "__open_2");
    int fd = real ? real(path, flags) : open_common("open", path, flags, 0);
    return real && target_path(path) ? normalized_fd(fd, flags) : fd;
}

int openat(int dir, const char *path, int flags, ...) {
    typedef int (*openat_fn)(int, const char *, int, ...);
    openat_fn real = (openat_fn)dlsym(NEXT, "openat");
    unsigned mode = 0;
    if ((flags & O_CREAT) || (flags & O_TMPFILE) == O_TMPFILE) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, unsigned); va_end(ap);
    }
    int fd = real ? real(dir, path, flags, mode) : -1;
    return target_path(path) ? normalized_fd(fd, flags) : fd;
}

int __openat_2(int dir, const char *path, int flags) {
    typedef int (*fortified_fn)(int, const char *, int);
    fortified_fn real = (fortified_fn)dlsym(NEXT, "__openat_2");
    int fd = real ? real(dir, path, flags) : openat(dir, path, flags);
    return real && target_path(path) ? normalized_fd(fd, flags) : fd;
}

static FILE *fopen_common(const char *symbol, const char *path, const char *mode) {
    typedef FILE *(*fopen_fn)(const char *, const char *);
    fopen_fn real = (fopen_fn)dlsym(NEXT, symbol);
    if (!real) real = (fopen_fn)dlsym(NEXT, "fopen");
    if (target_path(path) && (eq(mode, "r") || eq(mode, "re") || eq(mode, "rb"))) {
        int fd = open_common("open", path, O_RDONLY | (eq(mode, "re") ? O_CLOEXEC : 0), 0);
        if (fd < 0) return 0;
        FILE *fp = fdopen(fd, mode);
        if (!fp) close(fd);
        return fp;
    }
    return real ? real(path, mode) : 0;
}
FILE *fopen(const char *p, const char *m) { return fopen_common("fopen", p, m); }
FILE *fopen64(const char *p, const char *m) { return fopen_common("fopen64", p, m); }

struct service_slot { const char *name; void *binder; int state; };
static struct service_slot slots[] = {
    {"android.system.keystore2.IKeystoreService/default", 0, 0},
    {"android.hardware.security.keymint.IKeyMintDevice/default", 0, 0},
    {"android.hardware.gatekeeper.IGatekeeper/default", 0, 0},
    {"android.hardware.security.secureclock.ISecureClock/default", 0, 0},
    {"android.hardware.security.sharedsecret.ISharedSecret/default", 0, 0},
};

static void *lookup_worker(void *cookie) {
    struct service_slot *slot = (struct service_slot *)cookie;
    /* A wait started before registration needs a Binder thread to deliver the
     * registration callback. ProcessState::startThreadPool is idempotent. */
    typedef void (*start_pool_fn)(void);
    start_pool_fn start_pool = (start_pool_fn)dlsym(NEXT, "ABinderProcess_startThreadPool");
    if (start_pool) start_pool();
    lookup_fn real_wait = (lookup_fn)dlsym(NEXT, "AServiceManager_waitForService");
    void *binder = real_wait ? real_wait(slot->name) : 0;
    char b[400];
    snprintf(b, sizeof(b), "waitForService %s -> %p", slot->name, binder);
    log_line(b);
    /* waitForService returns one owned strong reference. Retain it until
     * process exit; give EACH caller a separate strong reference below. */
    __atomic_store_n(&slot->binder, binder, __ATOMIC_RELEASE);
    __atomic_store_n(&slot->state, binder ? 2 : 3, __ATOMIC_RELEASE);
    return 0;
}

void *AServiceManager_checkService(const char *name) {
    lookup_fn real_check = (lookup_fn)dlsym(NEXT, "AServiceManager_checkService");
    void *binder = real_check ? real_check(name) : 0;
    if (binder || !enabled || !name) return binder;
    for (unsigned i = 0; i < sizeof(slots) / sizeof(slots[0]); ++i) {
        struct service_slot *slot = &slots[i];
        if (!eq(slot->name, name)) continue;
        strong_fn inc = (strong_fn)dlsym(NEXT, "AIBinder_incStrong");
        if (!inc) return 0;
        binder = __atomic_load_n(&slot->binder, __ATOMIC_ACQUIRE);
        if (binder) { inc(binder); return binder; }
        int expect = 0;
        if (__atomic_compare_exchange_n(&slot->state, &expect, 1, 0,
                                        __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
            unsigned long thread;
            char b[400];
            snprintf(b, sizeof(b), "checkService null: starting async wait for %s", name);
            log_line(b);
            int rc = pthread_create(&thread, 0, lookup_worker, slot);
            if (!rc) (void)pthread_detach(thread);
            else {
                __atomic_store_n(&slot->state, 3, __ATOMIC_RELEASE);
                snprintf(b, sizeof(b), "pthread_create failed: %d", rc); log_line(b);
            }
        }
        /* Never run waitForService on the caller/UI thread. Vold retains its
         * existing 300 x 100 ms timeout when a service cannot register. */
        return 0;
    }
    return 0;
}

__attribute__((constructor)) static void init_bridge(void) {
    char exe[256];
    long n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n <= 0 || n >= (long)sizeof(exe) - 1) return;
    exe[n] = 0;
    char *base = exe;
    for (char *p = exe; *p; ++p) if (*p == '/') base = p + 1;
    enabled = eq(base, "recovery");
#ifdef TURNER_CRYPTO_TEST
    enabled = 1;
#endif
    if (enabled) log_line("loaded in recovery; bounded lookup bridge active");
}

#ifdef TURNER_CRYPTO_TEST
long turner_test_normalize(const char *i, size_t n, char *o, size_t cap) {
    return normalize_fstab(i, n, o, cap);
}
#endif
