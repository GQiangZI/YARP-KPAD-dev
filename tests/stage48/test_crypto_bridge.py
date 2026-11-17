#!/usr/bin/env python3
"""Exercise real ELF interposition, asynchronous lookup and fstab I/O on host.

Uses fake Binder only. Does not claim Android/KeyMint/data decryption succeeds.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "hybrid/stage48/libturner_crypto.c"


def run_tests():
    lib = C.CDLL(None)
    check = lib.AServiceManager_checkService
    check.argtypes, check.restype = [C.c_char_p], C.c_void_p
    dec = lib.AIBinder_decStrong
    dec.argtypes = [C.c_void_p]
    refs, waits = lib.fake_refs, lib.fake_waits
    name = b"android.system.keystore2.IKeystoreService/default"
    start = time.monotonic()
    assert not check(name)
    assert time.monotonic() - start < .10, "lookup blocked caller"
    assert not check(b"test.absent.optional.service")
    assert not check(None)
    deadline = start + 2
    while not (binder := check(name)):
        assert time.monotonic() < deadline, "wait result never published"
        time.sleep(.01)
    assert waits() == 1, "more than one worker for the same service"
    assert refs() == 2, "worker owns one ref; caller must own another"
    dec(binder)
    assert refs() == 1

    def caller(_):
        p = check(name)
        assert p == binder
        dec(p)

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(caller, range(500)))
    assert refs() == 1 and waits() == 1
    p = check(b"test.healthy")
    assert p and refs() == 2
    dec(p)
    assert refs() == 1
    print("PASS: nonblocking lookup, exact service allowlist, concurrency, Binder ownership")

    normalize = lib.turner_test_normalize
    normalize.argtypes = [C.c_char_p, C.c_size_t, C.c_void_p, C.c_size_t]
    normalize.restype = C.c_long
    row = (b"/dev/block/by-name/userdata\t/data\tf2fs\tnoatime "
           b"wait,keydirectory=/metadata/vold/metadata_encryption,fsverity")
    add = b",metadata_encryption=aes-256-xts"

    def fix(value, capacity=70000):
        buf = C.create_string_buffer(capacity)
        n = normalize(value, len(value), buf, capacity)
        return n, buf.raw[:n] if n > 0 else value

    for suffix in [b"", b"\n", b"   # comment\n"]:
        original = row + suffix
        assert fix(original)[1] == row + add + suffix
    explicit = row + b",metadata_encryption=adiantum:wrappedkey_v0\n"
    assert fix(explicit)[0] == 0, "must preserve explicit cipher"
    assert fix(row.replace(b"/data\t", b"/cache\t"))[0] == 0
    assert fix(row.replace(b"keydirectory=", b"other="))[0] == 0
    assert fix(b"# " + row + b"\n")[0] == 0
    assert fix(row, len(row))[0] == -1, "overflow must fail closed"
    combined = b"#metadata_encryption=comment\n" + row + b" #keep\n" + explicit
    assert fix(combined)[1] == (b"#metadata_encryption=comment\n" + row + add +
                               b" #keep\n" + explicit)
    print("PASS: exact fstab field handling, existing cipher, comments, tabs, overflow")

    path = Path(os.environ["TURNER_TEST_PATH"])
    original = row + b" # comment\n"
    path.write_bytes(original)
    baseline_fds = len(os.listdir("/proc/self/fd"))
    for _ in range(100):
        assert path.read_bytes() == row + add + b" # comment\n"
    assert len(os.listdir("/proc/self/fd")) == baseline_fds, "fd leak"
    libc = C.CDLL("libc.so.6")
    libc.open.argtypes, libc.open.restype = [C.c_char_p, C.c_int], C.c_int
    raw_fd = libc.open(os.fsencode(path), os.O_RDONLY)
    assert os.read(raw_fd, 70000) == original, "source fstab was modified"
    os.close(raw_fd)
    lib.fopen.argtypes, lib.fopen.restype = [C.c_char_p, C.c_char_p], C.c_void_p
    libc.fileno.argtypes, libc.fileno.restype = [C.c_void_p], C.c_int
    libc.fclose.argtypes = [C.c_void_p]
    fp = lib.fopen(os.fsencode(path), b"r")
    assert fp
    assert os.read(libc.fileno(fp), 70000) == row + add + b" # comment\n"
    libc.fclose(fp)
    for symbol in ("__open_2", "openat", "__openat_2"):
        call = getattr(lib, symbol)
        call.restype = C.c_int
        if symbol == "__open_2":
            call.argtypes = [C.c_char_p, C.c_int]
            fd = call(os.fsencode(path), os.O_RDONLY)
        else:
            call.argtypes = [C.c_int, C.c_char_p, C.c_int]
            fd = call(-100, os.fsencode(path), os.O_RDONLY)
        assert fd >= 0, symbol
        assert os.read(fd, 70000) == row + add + b" # comment\n", symbol
        os.close(fd)
    path.unlink()
    assert not lib.fopen(os.fsencode(path), b"r"), "missing file must stay missing"
    print("PASS: open64/fopen/fortified/openat I/O, source unchanged, missing file, no fd leak")


def main():
    if "--child" in sys.argv:
        run_tests()
        return
    with tempfile.TemporaryDirectory(prefix="turner-crypto-test-") as temporary:
        work = Path(temporary)
        fake = work / "fake.c"
        fake.write_text(r'''
#include <stdatomic.h>
#include <string.h>
#include <unistd.h>
static int token;
static _Atomic int references, calls;
void *AServiceManager_checkService(const char *s) {
    if (s && !strcmp(s, "test.healthy")) {
        atomic_fetch_add(&references, 1); return &token;
    }
    return 0;
}
void *AServiceManager_waitForService(const char *s) {
    (void)s; atomic_fetch_add(&calls, 1); usleep(180000);
    atomic_fetch_add(&references, 1); return &token;
}
void AIBinder_incStrong(void *p) { if(p) atomic_fetch_add(&references, 1); }
void AIBinder_decStrong(void *p) { if(p) atomic_fetch_sub(&references, 1); }
int fake_refs(void) { return references; }
int fake_waits(void) { return calls; }
''')
        shim = work / "libturner_crypto_test.so"
        backend = work / "libfake.so"
        target = work / "additional.fstab"
        subprocess.run(["cc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-DTURNER_CRYPTO_TEST", f'-DTURNER_ADDITIONAL_FSTAB="{target}"',
                        str(SOURCE), "-o", str(shim), "-ldl", "-pthread"], check=True)
        subprocess.run(["cc", "-shared", "-fPIC", "-O2", str(fake), "-o", str(backend)],
                       check=True)
        env = os.environ | {"LD_PRELOAD": f"{shim}:{backend}",
                            "TURNER_TEST_PATH": str(target)}
        subprocess.run([sys.executable, __file__, "--child"], env=env, check=True)


if __name__ == "__main__":
    main()
