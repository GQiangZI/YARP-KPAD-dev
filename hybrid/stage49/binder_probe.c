/* SPDX-License-Identifier: Apache-2.0
 * Read-only, isolated-process probe. No service registration or key operations.
 * Compare the modern ServiceManager API with legacy CHECK_SERVICE transaction 2.
 */
#include <stddef.h>
#include <stdarg.h>
extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);
extern char *getenv(const char *);
extern int vsnprintf(char *, unsigned long, const char *, va_list);
extern long write(int, const void *, unsigned long);
extern int getpid(void);
struct dl_info { const char *file; void *base; const char *symbol; void *address; };
extern int dladdr(const void *, struct dl_info *);

static void say(const char *format, ...) {
    char buffer[1200];
    va_list ap; va_start(ap, format);
    int n = vsnprintf(buffer, sizeof(buffer), format, ap); va_end(ap);
    if (n < 0) return;
    unsigned long count = (unsigned)n < sizeof(buffer) - 1 ? (unsigned)n : sizeof(buffer) - 2;
    buffer[count++] = '\n';
    (void)write(1, buffer, count);
}
static int equal(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static int size_of(const char *s) { int n = 0; while (s[n]) ++n; return n; }

/* AArch64 AAPCS64: nontrivial C++ sp<T> results use an indirect result in
 * x8, even though sp<T> contains one pointer. Do not declare them as C returns.
 * The callee writes an owned sp into our one-pointer slot. Its strong reference
 * is intentionally retained for the lifetime of this short-lived probe.
 */
#ifdef __aarch64__
__attribute__((naked)) void turner_sret0(void *fn __attribute__((unused)),
                                      void *out __attribute__((unused))) {
    __asm__ volatile("mov x8, x1\n br x0\n");
}
__attribute__((naked)) void turner_sret2(void *fn __attribute__((unused)),
                                      void *out __attribute__((unused)),
                                      void *self __attribute__((unused)),
                                      long arg __attribute__((unused))) {
    __asm__ volatile("mov x9, x0\n mov x8, x1\n mov x0, x2\n mov x1, x3\n br x9\n");
}
#ifdef TURNER_BINDER_ABI_TEST
__attribute__((naked)) void turner_abi_echo(void) {
    __asm__ volatile("stp x0, x1, [x8]\n ret\n");
}
#endif
#else
#error This probe is specific to ARM64 turner
#endif

typedef void *(*lookup_fn)(const char *);
typedef void (*release_fn)(void *);
typedef int (*prepare_fn)(void *, void **);
typedef int (*write_string_fn)(void *, const char *, int);
typedef int (*transact_fn)(void *, unsigned, void **, void **, unsigned);
typedef int (*read_object_fn)(const void *, void **);
typedef _Bool (*bool_fn)(const void *);

struct api {
    void *binder_handle, *ndk_handle;
    lookup_fn check, wait;
    release_fn dec, parcel_delete, status_delete;
    prepare_fn prepare;
    write_string_fn write_string;
    transact_fn transact;
    read_object_fn read_status, read_binder;
    bool_fn status_ok;
};

static void *create_cookie(void *cookie) { return cookie; }
static void destroy_cookie(void *cookie) { (void)cookie; }
static int no_server(void *binder, unsigned code, const void *in, void *out) {
    (void)binder; (void)code; (void)in; (void)out;
    return -74;
}

static void where(const char *label, void *function) {
    struct dl_info info;
    if (function && dladdr(function, &info))
        say("%s=%p library=%s", label, function, info.file ? info.file : "?");
    else say("%s=%p dlerror=%s", label, function, dlerror());
}

static void *legacy_context(struct api *a) {
    void *self_fn = dlsym(a->binder_handle, "_ZN7android12ProcessState4selfEv");
    void *proxy_fn = dlsym(a->binder_handle,
                         "_ZN7android12ProcessState23getStrongProxyForHandleEi");
    typedef void *(*from_fn)(const void *);
    from_fn from = (from_fn)dlsym(a->ndk_handle,
                       "_Z27AIBinder_fromPlatformBinderRKN7android2spINS_7IBinderEEE");
    typedef const void *(*class_fn)(const char *, void *(*)(void *),
                                    void (*)(void *), int (*)(void *, unsigned, const void *, void *));
    typedef _Bool (*associate_fn)(void *, const void *);
    class_fn define = (class_fn)dlsym(a->ndk_handle, "AIBinder_Class_define");
    associate_fn associate = (associate_fn)dlsym(a->ndk_handle, "AIBinder_associateClass");
    where("ProcessState::self", self_fn);
    where("ProcessState::getStrongProxyForHandle", proxy_fn);
    where("AIBinder_fromPlatformBinder", (void *)from);
    if (!self_fn || !proxy_fn || !from || !define || !associate) return 0;
    void *process = 0, *context_cpp = 0;
    turner_sret0(self_fn, &process);
    say("legacy bootstrap ProcessState=%p", process);
    if (!process) return 0;
    turner_sret2(proxy_fn, &context_cpp, process, 0);
    say("legacy bootstrap context IBinder=%p", context_cpp);
    if (!context_cpp) return 0;
    void *context = from(&context_cpp);
    say("legacy bootstrap context AIBinder=%p", context);
    if (!context) return 0;
    const void *clazz = define("android.os.IServiceManager", create_cookie, destroy_cookie, no_server);
    _Bool associated = clazz && associate(context, clazz);
    say("legacy context class=%p associated=%d", clazz, (int)associated);
    if (!associated) { a->dec(context); return 0; }
    return context;
}

static void *legacy_check(struct api *a, void *context, const char *name) {
    void *in = 0, *reply = 0, *status = 0, *binder = 0;
    int rc = a->prepare(context, &in);
    const char *phase = "prepare";
    if (rc) goto done;
    phase = "writeString";
    rc = a->write_string(in, name, size_of(name));
    if (rc) goto done;
    phase = "transact(code=2)";
    rc = a->transact(context, 2, &in, &reply, 0);
    if (rc) goto done;
    phase = "readStatusHeader";
    rc = a->read_status(reply, &status);
    if (rc || !status) goto done;
    if (!a->status_ok(status)) {
        typedef int (*status_int_fn)(const void *);
        typedef const char *(*message_fn)(const void *);
        status_int_fn ex = (status_int_fn)dlsym(a->ndk_handle, "AStatus_getExceptionCode");
        status_int_fn transport = (status_int_fn)dlsym(a->ndk_handle, "AStatus_getStatus");
        message_fn message = (message_fn)dlsym(a->ndk_handle, "AStatus_getMessage");
        say("legacy status exception=%d transport=%d message=%s",
            ex ? ex(status) : -999, transport ? transport(status) : -999,
            message ? message(status) : "?");
        rc = -1; goto done;
    }
    phase = "readStrongBinder";
    rc = a->read_binder(reply, &binder);
done:
    say("legacy check %s phase=%s rc=%d binder=%p", name, phase, rc, binder);
    if (status) a->status_delete(status);
    if (reply) a->parcel_delete(reply);
    if (in) a->parcel_delete(in);
    if (rc && binder) { a->dec(binder); binder = 0; }
    return binder;
}

static int load_api(struct api *a) {
    a->binder_handle = dlopen("libbinder.so", 2);
    if (!a->binder_handle) { say("dlopen libbinder failed: %s", dlerror()); return 0; }
    a->ndk_handle = dlopen("libbinder_ndk.so", 2);
    if (!a->ndk_handle) { say("dlopen libbinder_ndk failed: %s", dlerror()); return 0; }
#define LOAD(field, type, symbol) do { \
    a->field = (type)dlsym(a->ndk_handle, symbol); \
    if (!a->field) { say("missing %s: %s", symbol, dlerror()); return 0; } \
} while (0)
    LOAD(check, lookup_fn, "AServiceManager_checkService");
    LOAD(wait, lookup_fn, "AServiceManager_waitForService");
    LOAD(dec, release_fn, "AIBinder_decStrong");
    LOAD(parcel_delete, release_fn, "AParcel_delete");
    LOAD(status_delete, release_fn, "AStatus_delete");
    LOAD(prepare, prepare_fn, "AIBinder_prepareTransaction");
    LOAD(write_string, write_string_fn, "AParcel_writeString");
    LOAD(transact, transact_fn, "AIBinder_transact");
    LOAD(read_status, read_object_fn, "AParcel_readStatusHeader");
    LOAD(read_binder, read_object_fn, "AParcel_readStrongBinder");
    LOAD(status_ok, bool_fn, "AStatus_isOk");
#undef LOAD
    where("AServiceManager_checkService", (void *)a->check);
    where("AServiceManager_waitForService", (void *)a->wait);
    return 1;
}

__attribute__((constructor)) static void run(void) {
    if (!equal(getenv("TURNER_BINDER_PROBE"), "1")) return;
    say("turner Binder protocol probe v1, pid=%d", getpid());
    say("LD_LIBRARY_PATH=%s", getenv("LD_LIBRARY_PATH"));
    struct api a = {0};
    if (!load_api(&a)) return;
    const char *names[] = {
        "android.system.keystore2.IKeystoreService/default",
        "android.hardware.security.keymint.IKeyMintDevice/default",
        "android.hardware.gatekeeper.IGatekeeper/default",
        "vendor.hardware.vibratorfeature.IVibratorExt/default",
    };
    void *context = legacy_context(&a);
    for (unsigned i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
        void *binder = a.check(names[i]);
        say("modern check %s -> %p", names[i], binder);
        if (binder) a.dec(binder);
        if (context) {
            binder = legacy_check(&a, context, names[i]);
            if (binder) a.dec(binder);
        }
    }
    if (context) a.dec(context);
    typedef void (*start_fn)(void);
    start_fn start = (start_fn)dlsym(a.ndk_handle, "ABinderProcess_startThreadPool");
    if (start) start();
    say("calling modern waitForService for keystore2; outer timeout is 8 seconds");
    void *binder = a.wait(names[0]);
    say("modern waitForService %s -> %p", names[0], binder);
    if (binder) a.dec(binder);
    say("probe finished");
}
