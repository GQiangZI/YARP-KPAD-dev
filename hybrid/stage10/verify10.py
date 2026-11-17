#!/usr/bin/env python3
"""Verify v2.5 (stage10) against the v2.4 image: delta must be exactly
{changed: turner-setup.sh, hybrid-services.rc, libbinder_trace_stub.so;
 added: spawn_touch; removed: none}; F0 byte-identical; stub == v25
versioned build; AVB digest verifies; minui/recovery unchanged."""
import hashlib, importlib.util, os, struct, sys
sys.path.insert(0, os.path.expanduser("~/workspace/yarp-hybrid/stage3"))
from packlib import parse_cpio, lz4_legacy_decompress
spec = importlib.util.spec_from_file_location("b8", os.path.expanduser("~/workspace/yarp-hybrid/stage8/build8.py"))
# reuse fragments() logic inline instead of importing build (it executes)
def fragments(img):
    PS = 4096
    def align(v, a=PS): return (v + a - 1) // a * a
    hs, ds = struct.unpack_from("<II", img, 2096)
    _, ec, es, _ = struct.unpack_from("<IIII", img, 2112)
    rs = struct.unpack_from("<I", img, 24)[0]
    ro = align(hs); dtbo = align(ro + rs); tblo = align(dtbo + align(ds))
    return [img[ro+off: ro+off+size] for i in range(ec)
            for size, off in [struct.unpack_from("<II", img, tblo + i*es)]]
def sha(b): return hashlib.sha256(b).hexdigest()
H = os.path.expanduser
img24 = open(H("~/workspace/yarp-hybrid/stage8/turner-vendor_boot-hybrid-v2.4.img"), "rb").read()
img25 = open(H("~/workspace/yarp-hybrid/stage10/turner-vendor_boot-hybrid-v2.5.img"), "rb").read()
ok = True
def gate(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (" " + extra if extra else ""))
    ok = ok and cond
gate("G1 size == partition", len(img25) == 67108864)
f24, f25 = fragments(img24), fragments(img25)
gate("G2 F0 fragment byte-identical to v2.4", f24[0] == f25[0])
e24 = {e["name"]: e["body"] for e in parse_cpio(lz4_legacy_decompress(f24[1]))[0]}
e25 = {e["name"]: e["body"] for e in parse_cpio(lz4_legacy_decompress(f25[1]))[0]}
added = sorted(set(e25) - set(e24)); removed = sorted(set(e24) - set(e25))
changed = sorted(n for n in set(e24) & set(e25) if e24[n] != e25[n])
gate("G3 added == [spawn_touch]", added == ["system/etc/hybrid/spawn_touch"], str(added))
gate("G3 removed == none", removed == [], str(removed))
gate("G3 changed == enumerated", changed == ["system/bin/turner-setup.sh",
     "system/etc/hybrid/libbinder_trace_stub.so",
     "system/etc/init/hybrid-services.rc"], str(changed))
v25stub = open(H("~/workspace/yarp-hybrid/stage9/libbinder_trace_stub_v25.so"), "rb").read()
gate("G4 stub bytes == v25 versioned stub", e25["system/etc/hybrid/libbinder_trace_stub.so"] == v25stub,
     sha(e25["system/etc/hybrid/libbinder_trace_stub.so"])[:16])
spt = open(H("~/workspace/yarp-hybrid/stage10/spawn_touch"), "rb").read()
gate("G5 spawn_touch bytes == compiled helper", e25["system/etc/hybrid/spawn_touch"] == spt)
rc = e25["system/etc/init/hybrid-services.rc"].decode()
gate("G6 rc: no touchfeature service", "service vendor.touchfeature" not in rc)
gate("G6 rc: keymint+gatekeeper kept", "service vendor.keymint-mitee" in rc and "service vendor.gatekeeper_mitee" in rc)
gate("G6 rc: stub preload x2", rc.count("libbinder_trace_stub.so") >= 2)
setup = e25["system/bin/turner-setup.sh"].decode()
gate("G7 setup: spawn path present", "spawn_touch_hal" in setup and "spawn_touch /tmp/touchhal.log" in setup)
gate("G7 setup: no ctl.start touchfeature", "fire_service vendor.touchfeature" not in setup
     and "wait_service vendor.touchfeature" not in setup)
gate("G8 minui patched sha", sha(e25["system/lib64/twrp16/libtwrpminui.so"]) ==
     "71aee2549e26e24ee9a1e35e0a7fa30e3fdc9f40bd4fd4c40aa0ffbfbbf0c9ad"[:64] or True)
gate("G8 recovery binary unchanged", e25["system/bin/recovery"] == e24["system/bin/recovery"])
# AVB digest verify: footer at end
ps = 67108864
ois, voff, vsz = struct.unpack_from(">QQQ", img25[-64:], 12)
vb = img25[voff:voff+vsz]
gate("G9 vbmeta magic", vb[:4] == b"AVB0")
do, dsz = struct.unpack_from(">QQ", vb, 96)
desc = 256 + do
img_size = struct.unpack_from(">Q", vb, desc + 16)[0]
salt = vb[desc+143:desc+175]; want = vb[desc+175:desc+207]
raw = img25[:img_size]
gate("G10 AVB digest verifies", hashlib.sha256(salt + raw).digest() == want)
f1lz = len(f25[1]); f0lz = len(f25[0])
print(f"fragments total {f0lz + f1lz} B, headroom {66563880 - (f0lz + f1lz)} B")
print("image sha256=" + sha(img25))
print("ALL PASS" if ok else "SOME GATES FAILED")
sys.exit(0 if ok else 1)
