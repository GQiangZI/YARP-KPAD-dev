#!/usr/bin/env python3
"""Exercise the wrapper with neither toybox timeout nor a writable TMPDIR."""

from pathlib import Path
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile


def main():
    script = Path(sys.argv[1]).read_text()
    assert "<<" not in script, "mksh here-documents need a writable TMPDIR"
    with tempfile.TemporaryDirectory(prefix="turner-probe-wrapper-") as temporary:
        root = Path(temporary)
        bindir = root / "bin"
        bindir.mkdir()
        identity = bindir / "id"
        identity.write_text('#!/bin/sh\nif [ "$1" = -u ]; then echo 0; else echo uid=0; fi\n')
        identity.chmod(0o755)
        toybox = bindir / "toybox"
        toybox.write_text(f"#!{sys.executable}\n" + """
import os
import sys
import time

applet = sys.argv[1]
if applet in ('base64', 'sha256sum'):
    os.execvp(applet, sys.argv[1:])
if applet == 'timeout':
    raise SystemExit(127)
if applet != 'true' or os.environ.get('TURNER_BINDER_PROBE') != '1':
    raise SystemExit(2)
paths = os.environ.get('LD_LIBRARY_PATH', '')
assert os.environ.get('LD_PRELOAD', '').endswith('/libbinderprobe.so')
print(f'probe started with {paths}', flush=True)
if paths.startswith('/system/etc/hybrid/twrpbinder:'):
    time.sleep(60)
    raise AssertionError('the watchdog should stop this child')
print('probe completed')
""")
        toybox.chmod(0o755)
        wrapper = script.replace("TB=/system/bin/toybox", f"TB={shlex.quote(str(toybox))}")
        wrapper = wrapper.replace("/tmp/turner-binder-probe", f"{root}/turner-binder-probe")
        wrapper = wrapper.replace("-C /tmp ", f"-C {shlex.quote(str(root))} ")
        environment = os.environ | {"PATH": f"{bindir}:{os.environ['PATH']}",
                                    "TMPDIR": str(root / "unmounted-data/local/tmp")}
        shell = sys.argv[2] if len(sys.argv) > 2 else "sh"
        result = subprocess.run([shell], input=wrapper, text=True, env=environment,
                                capture_output=True, timeout=25)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Turner Binder probe v3" in result.stdout, result.stdout
        archive = root / "turner-binder-probe-logs.tar"
        with tarfile.open(archive) as logs:
            def output(label):
                return logs.extractfile(f"turner-binder-probe/{label}.txt").read().decode()

            for label in ("recovery", "stock"):
                log = output(label)
                assert "probe completed" in log and "probe process rc=0" in log, log
            split = output("split")
            assert "probe started with" in split, split
            assert "probe timed out after 8 seconds" in split, split
            assert "probe completed" not in split, split
            assert "uid=0" in output("context"), logs.getnames()
    print("PASS: probe decodes with missing TMPDIR and timeout, stops a stalled child, and archives results")


if __name__ == "__main__":
    main()
