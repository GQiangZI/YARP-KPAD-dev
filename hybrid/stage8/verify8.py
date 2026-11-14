#!/usr/bin/env python3
"""verify7: independent gate for hybrid v2.3 image.
Parses the BUILT image (not the work tree) and asserts:
- F1 delta vs v2.2 == exactly the enumerated v2.3 set; F0 identical.
- flipped library order + LD_PRELOAD present for the 3 HALs, tee untouched.
- prop bake, manifests, hybrid files, minui patch, recovery binary.
- AVB hash footer self-consistent; size/headroom.
"""
import hashlib, os, struct, sys
sys.path.insert(0, os.path.expanduser("~/workspace/yarp-hybrid/stage3"))
from packlib import parse_cpio, lz4_legacy_decompress
H = os.path.expanduser
S6, S7 = H("~/workspace/yarp-hybrid/stage6"), H("~/workspace/yarp-hybrid/stage7")
S8 = H("~/workspace/yarp-hybrid/stage8")
IMG = os.path.join(S8, "turner-vendor_boot-hybrid-v2.4.img")
PS, PART = 4096, 67108864
def align(v, a=PS): return (v + a - 1) // a * a
def sha(b): return hashlib.sha256(b).hexdigest()
img = open(IMG, "rb").read()
ok = []
def chk(name, cond, extra=""):
    ok.append(cond)
    print(("PASS " if cond else "FAIL ") + name + (" " + extra if extra else ""))

chk("G1 size == partition", len(img) == PART)
hs, ds = struct.unpack_from("<II", img, 2096)
_, ec, es, _ = struct.unpack_from("<IIII", img, 2112)
rs = struct.unpack_from("<I", img, 24)[0]
ro, dtbo = align(hs), align(align(hs) + rs)
tblo = align(dtbo + align(ds))
frags = []
for i in range(ec):
    size, off = struct.unpack_from("<II", img, tblo + i * es)
    frags.append(img[ro + off: ro + off + size])
f0_old = open(os.path.join(S6, ".work", "f0.lz4"), "rb").read()
chk("G2 F0 fragment byte-identical to v2.2", frags[0] == f0_old)
e_new = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(frags[1]))[0]}
img_old = open(os.path.join(S7, "turner-vendor_boot-hybrid-v2.3.img"), "rb").read()
hs2, ds2 = struct.unpack_from("<II", img_old, 2096)
_, ec2, es2, _ = struct.unpack_from("<IIII", img_old, 2112)
rs2 = struct.unpack_from("<I", img_old, 24)[0]
ro2, dtbo2 = align(hs2), align(align(hs2) + rs2)
tblo2 = align(dtbo2 + align(ds2))
sz2, off2 = struct.unpack_from("<II", img_old, tblo2 + 1 * es2)
e_old = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(img_old[ro2 + off2: ro2 + off2 + sz2]))[0]}
EXP_ADD = {"system/etc/hybrid/libbinder_trace_stub.so"}
EXP_CHG = {"system/etc/init/hybrid-services.rc", "system/bin/turner-setup.sh"}
added = set(e_new) - set(e_old); removed = set(e_old) - set(e_new)
changed = {n for n in set(e_new) & set(e_old)
           if e_new[n]["body"] != e_old[n]["body"] or e_new[n]["mode"] != e_old[n]["mode"]}
chk("G3 added == enumerated", added == EXP_ADD, str(sorted(added)))
chk("G3 removed == none", removed == set(), str(sorted(removed)))
chk("G3 changed == enumerated", changed == EXP_CHG, str(sorted(changed)))
rc = e_new["system/etc/init/hybrid-services.rc"]["body"].decode()
OLD = "/system/lib64:/system/lib64/bootstrap:/mnt/system"
chk("G4 a7 ramdisk-first path x3 (keymint+gatekeeper+touch)", rc.count("setenv LD_LIBRARY_PATH " + OLD) == 3)
chk("G4 tee-supplicant system-first x1", rc.count("setenv LD_LIBRARY_PATH /mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap") == 1)
chk("G4 stub preload x2 (keymint+gatekeeper)", rc.count("LD_PRELOAD /system/etc/hybrid/libkmsglog.so /system/etc/hybrid/libbinder_trace_stub.so") == 2)
chk("G4 kmsglog preload x3 total", rc.count("setenv LD_PRELOAD /system/etc/hybrid/libkmsglog.so") == 3)
su = e_new["system/bin/turner-setup.sh"]["body"].decode()
chk("G5 setup v2.4: closure loader + parallel fire + honest done",
    all(t in su for t in ("basename \"${tok}\" .ko", "canonical /vendor_dlkm mount failed",
                          "fire_service vendor.keymint-mitee", "fire_service vendor.gatekeeper_mitee",
                          "fire_service vendor.touchfeature", "vendor.turner.setup.failed",
                          'FAILURES="${FAILURES} touch-module"', "touch_diag()")))
prop = e_new["prop.default"]["body"].decode()
chk("G6 prop release baked 17 x4, no stale ro.build 15",
    prop.count("release=17") + prop.count("release_or_codename=17") +
    prop.count("release_or_preview_display=17") >= 4 and
    "ro.build.version.release=15" not in prop and
    "ro.build.version.security_patch=2026-10-01" in prop and
    "ro.vendor.build.security_patch=2026-10-01" in prop)
chk("G7 manifests bytes == staged originals",
    all(e_new["system/etc/vintf/manifest/" + f]["body"] ==
        open(os.path.join(S7, "manifests", f), "rb").read()
        for f in os.listdir(os.path.join(S7, "manifests"))))
chk("G8 libkmsglog sha", sha(e_new["system/etc/hybrid/libkmsglog.so"]["body"]) ==
    "0454981809157d050f5770bd215563e19b9788a635bf34a2d162746d782443d1")
chk("G8 touch ko sha", sha(e_new["system/etc/hybrid/nt36536e_touch_turner.ko"]["body"]) ==
    "151619c748fb836268ab5c652eff92457b15493fe0a617358d75ac40bdecfa5f")
chk("G8 stub bytes == crafted stage8 stub",
    e_new["system/etc/hybrid/libbinder_trace_stub.so"]["body"] ==
    open(os.path.join(S8, "libbinder_trace_stub.so"), "rb").read())
chk("G9 minui patched", sha(e_new["system/lib64/twrp16/libtwrpminui.so"]["body"]) ==
    "71aee2540c4995920fe520cdb0cd4c3b4d694462686638eaf6a1c6884e3a1939")
chk("G9 recovery binary unchanged", sha(e_new["system/bin/recovery"]["body"]) ==
    "af0a3aa8bc8bf7f5aaf937b84d1c9a66934d8b684558e5789d61cc8c97250c8e")
# AVB footer self-consistency
assert img[PART - 64:PART - 60] == b"AVBf"
_, _, orig_sz, vm_off, vm_sz = struct.unpack_from(">IIQQQ", img, PART - 64 + 4)
vm = img[vm_off:vm_off + vm_sz]
chk("G10 vbmeta magic", vm[:4] == b"AVB0")
do, dsz = struct.unpack_from(">QQ", vm, 96)
da = 256 + do
stored_sz, = struct.unpack_from(">Q", vm, da + 16)
salt, digest = vm[da + 143:da + 175], vm[da + 175:da + 207]
raw = img[:orig_sz]
chk("G10 AVB digest verifies", stored_sz == orig_sz and
    hashlib.sha256(salt + raw).digest() == digest)
print(f"\nheadroom: {66563880 - (len(frags[0]) + len(frags[1]))} B; "
      f"image sha256={sha(img)}")
print("ALL PASS" if all(ok) else "SOME FAILED")
sys.exit(0 if all(ok) else 1)
