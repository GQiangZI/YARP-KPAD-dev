#!/usr/bin/env python3
"""Self-check for recovery_deps.py: a dangling or looping symlink must fail the gate."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
elf = shutil.which('true')  # any dynamic 64-bit host ELF works as a fixture
out = subprocess.run(['readelf', '-dlW', elf], capture_output=True, text=True, check=True).stdout
needed = re.findall(r'Shared library: \[(.+?)\]', out)
interp = re.findall(r'program interpreter: (.+?)\]', out)[0]


def run(setup):
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(f'{root}/system/bin')
        os.makedirs(f'{root}/system/lib64')
        shutil.copy(elf, f'{root}/system/bin/probe')
        os.makedirs(os.path.dirname(root + interp), exist_ok=True)
        open(root + interp, 'w').close()
        for n in needed:
            open(f'{root}/system/lib64/{n}', 'w').close()
        setup(root)
        return subprocess.run([sys.executable, '-I', f'{here}/recovery_deps.py', root], capture_output=True).returncode


def relink(path, target):
    os.remove(path)
    os.symlink(target, path)


lib = lambda r: f'{r}/system/lib64/{needed[0]}'
cases = {
    'all present': (lambda r: None, 0),
    'absolute lib symlink inside the ramdisk': (lambda r: (os.rename(lib(r), f'{r}/system/real.so'), os.symlink('/system/real.so', lib(r))), 0),
    'dangling lib symlink': (lambda r: relink(lib(r), '/system/lib64/gone.so'), 1),
    'looping lib symlink': (lambda r: relink(lib(r), needed[0]), 1),
    'dangling interpreter symlink': (lambda r: relink(r + interp, '/nowhere/linker'), 1),
}
bad = [name for name, (setup, want) in cases.items() if run(setup) != want]
print('FAIL: ' + ', '.join(bad) if bad else f'ok ({len(cases)} cases)')
sys.exit(1 if bad else 0)
