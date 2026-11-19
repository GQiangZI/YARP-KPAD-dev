#!/usr/bin/env python3
"""Exercise the real fallback against a fake legacy ServiceManager."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
KEYSTORE = b"android.system.keystore2.IKeystoreService/default"
AUTHORIZATION = b"android.security.authorization"

FAKE_CPP = r'''
#include <assert.h>
static int process, manager, bootstrap_count;
void self(void **out) __asm__("_ZN7android12ProcessState4selfEv");
void proxy(void **out, void *self, long handle)
    __asm__("_ZN7android12ProcessState23getStrongProxyForHandleEi");
void self(void **out) { *out = &process; }
void proxy(void **out, void *self, long handle) {
    assert(self == &process && handle == 0);
    ++bootstrap_count;
    *out = &manager;
}
int fake_bootstraps(void) { return bootstrap_count; }
'''

FAKE_NDK = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>

static const char keystore[] = "android.system.keystore2.IKeystoreService/default";
static int context, clazz, target;
static atomic_int refs, calls, allocations;
static int mode;

void fake_set_mode(int value) { mode = value; }
int fake_refs(void) { return refs; }
int fake_calls(void) { return calls; }
int fake_live_allocations(void) { return allocations; }

static void *allocate(void) {
    void *p = calloc(1, 256);
    assert(p);
    ++allocations;
    return p;
}
static void release(void *p) { assert(p); free(p); --allocations; }

void *AServiceManager_checkService(const char *name) {
    if (name && (!strcmp(name, "test.healthy") || (mode == 4 && !strcmp(name, keystore)))) {
        ++refs;
        return &target;
    }
    return 0;
}
void AIBinder_decStrong(void *p) {
    assert(p == &target);
    --refs;
}
void *from(const void *p)
    __asm__("_Z27AIBinder_fromPlatformBinderRKN7android2spINS_7IBinderEEE");
void *from(const void *p) { assert(p && *(void *const *)p); return &context; }
const void *AIBinder_Class_define(const char *descriptor, void *create, void *destroy,
                                  void *transact) {
    assert(!strcmp(descriptor, "android.os.IServiceManager") && create && destroy && transact);
    return &clazz;
}
bool AIBinder_associateClass(void *p, const void *c) { return p == &context && c == &clazz; }

int AIBinder_prepareTransaction(void *p, void **in) { assert(p == &context); *in = allocate(); return 0; }
int AParcel_writeString(void *in, const char *name, int length) {
    assert(length == (int)strlen(name) && length < 256);
    memcpy(in, name, (size_t)length);
    return 0;
}
int AIBinder_transact(void *p, unsigned code, void **in, void **reply, unsigned flags) {
    assert(p == &context && code == 2 && flags == 0);
    assert(!strcmp(*in, keystore) || !strcmp(*in, "android.security.authorization"));
    ++calls;
    release(*in);
    *in = 0;
    if (mode == 5) return -74;
    *reply = allocate();
    return 0;
}
int AParcel_readStatusHeader(const void *reply, void **status) { assert(reply); *status = allocate(); return 0; }
bool AStatus_isOk(const void *p) { assert(p); return mode != 2; }
int AStatus_getStatus(const void *p) { assert(p); return -13; }
int AStatus_getExceptionCode(const void *p) { assert(p); return -1; }
int AParcel_readStrongBinder(const void *reply, void **binder) {
    assert(reply && (mode == 0 || mode == 1 || mode == 3));
    if (mode) { *binder = &target; ++refs; }
    return mode == 3 ? -22 : 0;
}
void AParcel_delete(void *p) { release(p); }
void AStatus_delete(void *p) { release(p); }
'''


def exercise():
    lib = ctypes.CDLL(None)
    check = lib.AServiceManager_checkService
    check.argtypes, check.restype = [ctypes.c_char_p], ctypes.c_void_p
    dec = lib.AIBinder_decStrong
    dec.argtypes, dec.restype = [ctypes.c_void_p], None
    mode, calls = lib.fake_set_mode, lib.fake_calls
    mode.argtypes, mode.restype = [ctypes.c_int], None
    assert not check(None)
    assert not check(b"test.ignored")
    dec(check(b"test.healthy"))
    assert calls() == 0 and lib.fake_bootstraps() == 0
    assert not check(KEYSTORE)
    assert calls() == 1 and lib.fake_bootstraps() == 1
    for error_mode in (2, 3, 5):
        mode(error_mode)
        assert not check(KEYSTORE), error_mode
        assert lib.fake_live_allocations() == 0 and lib.fake_refs() == 0
    assert calls() == 4

    def lookup(_):
        binder = check(KEYSTORE)
        assert binder
        dec(binder)

    mode(1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lookup, range(150)))
    assert calls() == 154 and lib.fake_bootstraps() == 1
    assert lib.fake_live_allocations() == 0 and lib.fake_refs() == 0
    mode(0)
    assert not check(KEYSTORE), "a disappeared service must not be served from cache"
    mode(4)
    dec(check(KEYSTORE))
    assert calls() == 155, "a valid modern result must bypass the fallback"
    mode(0)
    assert not check(AUTHORIZATION)
    mode(1)
    dec(check(AUTHORIZATION))
    assert calls() == 157 and lib.fake_live_allocations() == 0 and lib.fake_refs() == 0
    print("PASS: legacy transaction, late registration, missing service, errors, cleanup and concurrency")


def main():
    if "--child" in sys.argv:
        exercise()
        return

    with tempfile.TemporaryDirectory(prefix="turner-legacy-test-") as temporary:
        work = Path(temporary)
        libs = []
        for name, source in (("libbinder_ndk.so", FAKE_NDK), ("libbinder.so", FAKE_CPP)):
            lib = work / name
            code = lib.with_suffix(".c")
            code.write_text(source)
            subprocess.run(["cc", "-shared", "-fPIC", "-O2", f"-Wl,-soname,{name}",
                            str(code), "-o", str(lib)], check=True)
            libs.append(lib)
        shim = work / "libturner_crypto_legacy_test.so"
        subprocess.run(["cc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-DTURNER_CRYPTO_TEST", "-DTURNER_BINDER_BRIDGE", "-DTURNER_BINDER_BRIDGE_TEST",
                        str(ROOT / "hybrid/stage48/libturner_crypto.c"),
                        str(ROOT / "hybrid/stage49/binder_probe.c"), "-o", str(shim), "-ldl", "-pthread"],
                       check=True)
        env = os.environ | {"LD_PRELOAD": ":".join(map(str, [shim, *libs]))}
        subprocess.run([sys.executable, __file__, "--child"], env=env, check=True)


if __name__ == "__main__":
    main()
