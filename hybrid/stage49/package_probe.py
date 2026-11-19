#!/usr/bin/env python3
"""Produce one generated shell artifact containing the ARM64 read-only probe."""
import argparse
import base64
from hashlib import sha256
from pathlib import Path
import textwrap

START = r'''#!/system/bin/sh
# Generated, read-only Binder query probe for turner v3.35.
# Run: sh /tmp/turner-binder-probe.sh
if [ "$(id -u)" != 0 ]; then
    echo 'Run this from the recovery terminal as root.'
    exit 1
fi
TB=/system/bin/toybox
if [ ! -x "$TB" ]; then echo 'Missing /system/bin/toybox'; exit 1; fi
echo 'Turner Binder probe v3'
WORK=/tmp/turner-binder-probe
mkdir -p "$WORK" || exit 1
'''
DECODE = r'''if ! printf '%s\n' '@PAYLOAD@' |
    "$TB" base64 -d > "$WORK/libbinderprobe.so"; then
    echo 'Probe decode failed'
    exit 1
fi
'''
END = r'''
EXPECTED='@SHA@'
ACTUAL=$("$TB" sha256sum "$WORK/libbinderprobe.so")
ACTUAL=${ACTUAL%% *}
if [ "$ACTUAL" != "$EXPECTED" ]; then echo 'Probe checksum mismatch'; exit 1; fi
chmod 0644 "$WORK/libbinderprobe.so"
{
    id
    cat /proc/uptime
    for p in $(pidof recovery); do
        echo "recovery pid=$p"
        grep -E 'libturner_crypto|libbinder(_ndk)?\.so' "/proc/$p/maps"
    done
    echo 'This program queries services only. It does not decrypt or write keys.'
} > "$WORK/context.txt" 2>&1
run_probe() {
    label=$1
    libs=$2
    preload=$3
    probe_log="$WORK/$label.txt"
    echo "Running $label (8 second limit)..."
    TURNER_BINDER_PROBE=1 LD_LIBRARY_PATH="$libs" LD_PRELOAD="$preload" \
        "$TB" true > "$probe_log" 2>&1 &
    probe_pid=$!
    elapsed=0
    # Recovery builds can omit the timeout applet or return nonzero for help.
    # Watch only this child and retain its output if the Binder call stalls.
    while kill -0 "$probe_pid" 2>/dev/null; do
        if [ "$elapsed" -eq 8 ]; then
            if kill -KILL "$probe_pid" 2>/dev/null; then
                echo 'probe timed out after 8 seconds' >> "$probe_log"
            fi
            break
        fi
        if ! sleep 1; then
            kill -KILL "$probe_pid" 2>/dev/null
            echo 'probe stopped: watchdog sleep failed' >> "$probe_log"
            break
        fi
        elapsed=$((elapsed + 1))
    done
    wait "$probe_pid" 2>/dev/null
    rc=$?
    echo "probe process rc=$rc" >> "$probe_log"
}
run_probe recovery \
    /system/lib64/twrp16:/system/lib64 \
    "$WORK/libbinderprobe.so"
run_probe split \
    /system/etc/hybrid/twrpbinder:/system/lib64/twrp16:/system/lib64 \
    "/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so:$WORK/libbinderprobe.so"
run_probe stock \
    /system/lib64:/system/lib64/twrp16 \
    "$WORK/libbinderprobe.so"
tar -cf /tmp/turner-binder-probe-logs.tar -C /tmp turner-binder-probe/context.txt \
    turner-binder-probe/recovery.txt turner-binder-probe/split.txt \
    turner-binder-probe/stock.txt
if [ $? != 0 ]; then echo 'Archive failed; individual logs remain in /tmp/turner-binder-probe'; exit 1; fi
chmod 0644 /tmp/turner-binder-probe-logs.tar
echo 'Saved /tmp/turner-binder-probe-logs.tar'
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.library.read_bytes()
    if data[:6] != b"\x7fELF\x02\x01" or int.from_bytes(data[18:20], "little") != 183:
        raise ValueError("Expected little-endian ARM64 ELF64")
    encoded = "\n".join(textwrap.wrap(base64.b64encode(data).decode(), 76))
    # Android's mksh writes here-documents to TMPDIR, which can point at
    # /data/local/tmp while /data is unmounted. A pipe needs no such file.
    script = START + DECODE.replace("@PAYLOAD@", encoded) + END.replace("@SHA@", sha256(data).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(script)
    print(args.output, "library_sha256", sha256(data).hexdigest())


if __name__ == "__main__":
    main()
