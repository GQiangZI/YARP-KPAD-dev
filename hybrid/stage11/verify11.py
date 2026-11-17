#!/usr/bin/env python3
"""Verify v2.6 (stage11) against the v2.5 image: delta must be exactly
{changed: turner-setup.sh, hybrid-services.rc; added: spawn_hal;
 removed: spawn_touch, libbinder_trace_stub.so}; F0 byte-identical;
 AVB verifies; minui/recovery unchanged."""
import hashlib, os, struct, sys
sys.path.insert(0, os.path.expanduser("~/workspace/yarp-hybrid/stage3"))
from packlib import parse_cpio, lz4_legacy_decompress
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
img25 = open(H("~/workspace/yarp-hybrid/stage10/turner-vendor_boot-hybrid-v2.5.img"), "rb").read()
img26 = open(H("~/workspace/yarp-hybrid/stage11/turner-vendor_boot-hybrid-v2.6.img"), "rb").read()
ok = True
def gate(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (" " + extra if extra else ""))
    ok = ok and cond
gate("G1 size == partition", len(img26) == 67108864)
f25, f26 = fragments(img25), fragments(img26)
gate("G2 F0 byte-identical to v2.5", f25[0] == f26[0])
e25 = {e["name"]: e["body"] for e in parse_cpio(lz4_legacy_decompress(f25[1]))[0]}
e26 = {e["name"]: e["body"] for e in parse_cpio(lz4_legacy_decompress(f26[1]))[0]}
added = sorted(set(e26) - set(e25)); removed = sorted(set(e25) - set(e26))
changed = sorted(n for n in set(e25) & set(e26) if e25[n] != e26[n])
gate("G3 added == [spawn_hal]", added == ["system/etc/hybrid/spawn_hal"], str(added))
gate("G3 removed == [stub, spawn_touch]", removed == ["system/etc/hybrid/libbinder_trace_stub.so",
     "system/etc/hybrid/spawn_touch"], str(removed))
gate("G3 changed == [setup, rc]", changed == ["system/bin/turner-setup.sh",
     "system/etc/init/hybrid-services.rc"], str(changed))
spt = open(H("~/workspace/yarp-hybrid/stage11/spawn_hal"), "rb").read()
gate("G4 spawn_hal bytes == compiled helper", e26["system/etc/hybrid/spawn_hal"] == spt)
rc = e26["system/etc/init/hybrid-services.rc"].decode()
gate("G5 rc: no HAL services", all(x not in rc for x in
     ("service vendor.keymint-mitee", "service vendor.gatekeeper_mitee", "service vendor.touchfeature")))
gate("G5 rc: tee-supplicant + turner-setup kept", "service vendor.tee-supplicant" in rc and "service turner-setup" in rc)
setup = e26["system/bin/turner-setup.sh"].decode()
gate("G6 setup: three spawn_hal calls", setup.count("spawn_and_check") >= 3 and "spawn_tee_chain" in setup)
gate("G6 setup: system-first env for TEE", "/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex" in setup)
gate("G6 setup: no ctl.start for HALs", "fire_service vendor.keymint" not in setup and "wait_service vendor.keymint" not in setup)
gate("G7 recovery binary unchanged", e26["system/bin/recovery"] == e25["system/bin/recovery"])
ps = 67108864
ois, voff, vsz = struct.unpack_from(">QQQ", img26[-64:], 12)
vb = img26[voff:voff+vsz]
gate("G8 vbmeta magic", vb[:4] == b"AVB0")
do, dsz = struct.unpack_from(">QQ", vb, 96)
desc = 256 + do
img_size = struct.unpack_from(">Q", vb, desc + 16)[0]
salt = vb[desc+143:desc+175]; want = vb[desc+175:desc+207]
gate("G9 AVB digest verifies", hashlib.sha256(salt + img26[:img_size]).digest() == want)
print(f"fragments total {len(f26[0]) + len(f26[1])} B, headroom {66563880 - (len(f26[0]) + len(f26[1]))} B")
print("image sha256=" + sha(img26))
print("ALL PASS" if ok else "SOME GATES FAILED")
sys.exit(0 if ok else 1)
