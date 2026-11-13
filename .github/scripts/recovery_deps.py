#!/usr/bin/env python3
"""Make every 64-bit ELF in a recovery ramdisk loadable.

TWRP's relink lists copy fixed library versions (keystore2-V1, keymint-V1) while
vold already links newer ones (V4, V3), and system servicemanager is a bootstrap
binary whose interpreter /system/bin/bootstrap/linker64 does not exist in
recovery. Both left TWRP unable to start.

usage: recovery_deps.py <ramdisk root> [<library dir or soong .intermediates>...]

Missing NEEDED libraries are copied into <root>/system/lib64 from the given dirs
(directly in a dir, or in an arm64 shared-variant dir under .intermediates); a
missing interpreter becomes a symlink to the /system/bin linker of the same name.
Every change is printed. Exits 1 if something cannot be resolved.
"""
import os
import re
import shutil
import subprocess
import sys

LIBDIRS = ('system/lib64', 'vendor/lib64', 'odm/lib64')  # linker default paths in recovery
VARIANTS = ('android_recovery_arm64_armv8-a_shared', 'android_arm64_armv8-a_shared')
SKIP = ('first_stage_ramdisk', 'lib')  # normal-boot files and kernel modules

root, sources = sys.argv[1], sys.argv[2:]


def readelf(path, flag, pattern):
    r = subprocess.run(['readelf', flag, '-W', path], capture_output=True, text=True)
    # a readelf failure must not look like "no dependencies" and silently pass the gate
    if r.returncode != 0:
        sys.exit(f'::error title=Unreadable ELF::readelf {flag} failed on {path}: {r.stderr.strip()}')
    return re.findall(pattern, r.stdout)


def elfs():
    for dp, dns, fns in os.walk(root):
        if dp == root:
            dns[:] = [d for d in dns if d not in SKIP]
        for fn in fns:
            p = os.path.join(dp, fn)
            if not os.path.islink(p):
                with open(p, 'rb') as f:
                    if f.read(5) == b'\x7fELF\x02':
                        yield p


def index():
    found = {}
    for s in sources:
        for dp, _, fns in os.walk(s):
            v = os.path.basename(dp)
            if dp != s and v not in VARIANTS:
                continue
            for fn in fns:
                # earlier dirs win; under .intermediates the recovery variant beats the system one
                if fn.endswith('.so') and (fn not in found or v == VARIANTS[0] and found[fn][1] == VARIANTS[1]):
                    found[fn] = (os.path.join(dp, fn), v)
    return {k: p for k, (p, _) in found.items()}


def rel(p):
    return '/' + os.path.relpath(p, root)


def present(path):
    """Does the phone path exist in the ramdisk? Symlinks (also absolute ones and in parent
    dirs) resolve inside the ramdisk, so a dangling or looping link counts as missing."""
    todo, cur, hops = [x for x in path.split('/') if x], '', 0
    while todo:
        x = todo.pop(0)
        if x == '..':
            cur = cur.rsplit('/', 1)[0]
        elif x != '.':
            p = root + cur + '/' + x
            if os.path.islink(p):
                hops += 1
                if hops > 40:
                    return False
                t = os.readlink(p)
                if t.startswith('/'):
                    cur = ''
                todo = [y for y in t.split('/') if y] + todo
            elif os.path.lexists(p):
                cur += '/' + x
            else:
                return False
    return True


libs, unresolved = None, {}
while True:
    missing = {}
    for p in elfs():
        for n in readelf(p, '-d', r'Shared library: \[(.+?)\]'):
            if not any(present(f'/{d}/{n}') for d in LIBDIRS):
                missing.setdefault(n, rel(p))
        for interp in readelf(p, '-l', r'program interpreter: (.+?)\]'):
            dst = root + interp
            if present(interp):
                continue
            target = '/system/bin/' + os.path.basename(interp)
            if not os.path.lexists(dst) and present(target):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.symlink(target, dst)
                print(f'{interp} -> {target} (interpreter of {rel(p)})')
            else:
                unresolved[interp] = rel(p)
    if missing and libs is None:
        libs = index()
    added = False
    for n, by in sorted(missing.items()):
        if libs and n in libs:
            shutil.copy2(libs[n], os.path.join(root, 'system/lib64', n))
            print(f'/system/lib64/{n} (needed by {by})')
            added = True
        else:
            unresolved[n] = by
    if not added:
        break
    unresolved = {}

for n, by in sorted(unresolved.items()):
    print(f'::error title=Missing in recovery::{n} needed by {by}', file=sys.stderr)
sys.exit(1 if unresolved else 0)
