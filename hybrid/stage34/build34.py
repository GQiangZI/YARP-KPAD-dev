#!/usr/bin/env python3
"""Stage-7 assembly: turner YARP x Skyward hybrid vendor_boot v2.3.

= build6 (v2.2) + the v2.3 delta applied to f1_final after the stage-6
patch substitution (see the stage-7 block): stage-7 rc/setup bodies
(flipped HAL library order + LD_PRELOAD libkmsglog; unsilenced module
load + persist retries), prop.default release bake 15 -> 17, the four
OS4 VINTF manifests for the mitee HALs, and system/etc/hybrid/
{libkmsglog.so, nt36536e_touch_turner.ko}. The stage-4 faithfulness
assert still runs on the un-delta'd baseline first.

= build4b (v2.1) + ONE delta: F1 twrp16/libtwrpminui.so is replaced by
the stage-6 patched copy (force legacy_modeset=true; see VERIFY.md).
The uncut-baseline faithfulness assert and the CUT-1 measurements run
on the ORIGINAL lib first, reproducing v2.1 exactly; the patched body
is substituted into f1_final afterwards and the fragment re-packed.

Strict isolation, for real this time:
- F0: stage-3b's verified fragment reused BYTE-FOR-BYTE
  (OS4 stock + 11 twrp16 entries + 1 setenv line - res/ - system/bin/recovery).
- F1: OS4 STOCK F1 archive entries verbatim + ONLY the enumerated delta:
  1. system/bin/recovery      <- TWRP binary from the payload (addition;
                                 stock F1 has no such path)
  2. system/lib64/twrp16/*    <- every payload system/lib64 lib whose bytes
                                 differ from the merged OS4-stock counterpart,
                                 plus payload-only libs the TWRP binary needs
                                 (DT_NEEDED closure + strings dlopen scan)
  3. twres/ + res additions   <- payload UI resources (payload-only paths)
  4. system/etc/recovery.fstab<- payload version (body swap, mode unchanged)
  5. vendor/firmware/*        <- payload touch firmware (addition)
  6. system/bin/turner-setup.sh (stage-4 patched) +
     system/etc/init/hybrid-services.rc (stage-2 verbatim)
  7. init.recovery.mt8799.rc  <- append-only: breadcrumbs + Skyward block
  NO other shared-path file changes. Every stock lib stays stock.
"""
import hashlib, importlib.util, json, os, re, struct, sys
from collections import deque

sys.path.insert(0, os.path.expanduser("~/workspace/yarp-hybrid/stage3"))
from packlib import parse_cpio, write_newc, lz4_legacy_compress, lz4_legacy_decompress

H = os.path.expanduser
S1 = H("~/workspace/yarp-hybrid/stage1")
S2 = H("~/workspace/yarp-hybrid/stage2")
S3 = H("~/workspace/yarp-hybrid/stage3")
S4 = H("~/workspace/yarp-hybrid/stage4")
S6 = H("~/workspace/yarp-hybrid/stage6")
S7 = H("~/workspace/yarp-hybrid/stage7")
S8 = H("~/workspace/yarp-hybrid/stage8")
S9 = H("~/workspace/yarp-hybrid/stage9")
S10 = H("~/workspace/yarp-hybrid/stage10")
S11 = H("~/workspace/yarp-hybrid/stage11")
S12 = H("~/workspace/yarp-hybrid/stage12")
S13 = H("~/workspace/yarp-hybrid/stage13")
S14 = H("~/workspace/yarp-hybrid/stage14")
S15 = H("~/workspace/yarp-hybrid/stage15")
S16 = H("~/workspace/yarp-hybrid/stage16")
S17 = H("~/workspace/yarp-hybrid/stage17")
S18 = H("~/workspace/yarp-hybrid/stage18")
S19 = H("~/workspace/yarp-hybrid/stage19")
S20 = H("~/workspace/yarp-hybrid/stage20")
S21 = H("~/workspace/yarp-hybrid/stage21")
S22 = H("~/workspace/yarp-hybrid/stage22")
S23 = H("~/workspace/yarp-hybrid/stage23")
S24 = H("~/workspace/yarp-hybrid/stage24")
S25 = H("~/workspace/yarp-hybrid/stage25")
S26 = H("~/workspace/yarp-hybrid/stage26")
S27 = H("~/workspace/yarp-hybrid/stage27")
S28 = H("~/workspace/yarp-hybrid/stage28")
S29 = H("~/workspace/yarp-hybrid/stage29")
S30 = H("~/workspace/yarp-hybrid/stage30")
S31 = H("~/workspace/yarp-hybrid/stage31")
S32 = H("~/workspace/yarp-hybrid/stage32")
S33 = H("~/workspace/yarp-hybrid/stage33")
S34 = H("~/workspace/yarp-hybrid/stage34")
STOCK_IMG = H("~/workspace/skyward-turner/os4/vendor_boot.img")
V5_IMG = H("~/workspace/yarp/turner-vendor_boot-repack-v5.img")
F0_LZ4_REUSE = os.path.join(S3, ".work", "f0.lz4")
SETUP_SH = os.path.join(S4, "turner-setup.sh")
SERVICES_RC = os.path.join(S2, "hybrid-services.rc")
OUT_DIR = S34
WORK = os.path.join(S34, ".work")
PARTITION_SIZE = 67108864
PS = 4096
DIR, LINK, FILE = 0o040000, 0o120000, 0o100000


def align(v, a=PS):
    return (v + a - 1) // a * a


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fragments(img):
    hs, ds = struct.unpack_from("<II", img, 2096)
    _, ec, es, _ = struct.unpack_from("<IIII", img, 2112)
    rs = struct.unpack_from("<I", img, 24)[0]
    ro = align(hs)
    dtbo = align(ro + rs)
    tblo = align(dtbo + align(ds))
    out = []
    for i in range(ec):
        size, off = struct.unpack_from("<II", img, tblo + i * es)
        out.append(img[ro + off: ro + off + size])
    return out


def emap(entries):
    return {e["name"]: e for e in entries}


def resolve(m, name, depth=0):
    if depth > 8 or name not in m:
        return None, None
    e = m[name]
    t = e["mode"] & 0o170000
    if t == LINK:
        tgt = e["body"].decode()
        if tgt.startswith("/"):
            nxt = tgt.lstrip("/")
        else:
            base = name.rsplit("/", 1)[0] if "/" in name else ""
            nxt = os.path.normpath(os.path.join(base, tgt)) if base else os.path.normpath(tgt)
        return resolve(m, nxt, depth + 1)
    if t == DIR:
        return None, e
    return e["body"], e


# ------------------------------------------------------------------- inputs
stock = open(STOCK_IMG, "rb").read()
v5 = open(V5_IMG, "rb").read()
assert len(stock) == len(v5) == PARTITION_SIZE
sf0, _ = parse_cpio(lz4_legacy_decompress(fragments(stock)[0]))
sf1, _ = parse_cpio(lz4_legacy_decompress(fragments(stock)[1]))
pf1, _ = parse_cpio(lz4_legacy_decompress(fragments(v5)[1]))
stock_map = emap(sf0)
stock_map.update(emap(sf1))          # merged OS4 stock, F1 wins
pay_map = emap(pf1)
sf1_map = emap(sf1)

# ------------------------------------------------- twrp16 set (mechanical)
LIB = "system/lib64/"
pay_libs = {n for n in pay_map
            if n.startswith(LIB) and "/" not in n[len(LIB):]
            and (pay_map[n]["mode"] & 0o170000) == FILE}
stk_libs = {n for n in stock_map
            if n.startswith(LIB) and "/" not in n[len(LIB):]}
differing, pay_only = [], []
for n in sorted(pay_libs):
    pb, _ = resolve(pay_map, n)
    if n not in stk_libs:
        pay_only.append(n)
    else:
        sb, _ = resolve(stock_map, n)
        if pb != sb:
            differing.append(n)

spec = importlib.util.spec_from_file_location(
    "symaudit", os.path.join(S1, "_src", "audit-v5", "symbol-audit-v5.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
PAY_TREE = os.path.join(S1, "twrp_payload")


def elf_of(rel):
    p = os.path.join(PAY_TREE, rel)
    return mod.parse_elf(p) if os.path.isfile(p) else None


rec_info = elf_of("system/bin/recovery")
assert rec_info and rec_info["needed"]
by_base = {}
for n in pay_libs:
    by_base.setdefault(n.rsplit("/", 1)[-1], n)
closure, q, seen_needed = set(), deque(rec_info["needed"]), set()
while q:
    soname = q.popleft()
    if soname in seen_needed:
        continue
    seen_needed.add(soname)
    rel = by_base.get(soname)
    if rel is None:
        continue
    closure.add(rel)
    info = elf_of(rel)
    if info:
        q.extend(info["needed"])
rec_bytes, _ = resolve(pay_map, "system/bin/recovery")
tokens = {t.decode() for t in re.findall(rb"lib[\w.\-+]*\.so(?:\.[\w.]+)?", rec_bytes)}
needed_payonly = sorted(n for n in pay_only
                        if n in closure or n.rsplit("/", 1)[-1] in tokens)
unneeded_payonly = sorted(set(pay_only) - set(needed_payonly))
twrp16_set = sorted(differing + needed_payonly)
print(f"twrp16 set: {len(twrp16_set)} libs "
      f"({len(differing)} differing + {len(needed_payonly)} payload-only-needed); "
      f"{len(unneeded_payonly)} payload-only libs excluded as not needed")

# ------------------------------------------------------------- F1 assembly
f1 = {e["name"]: {"name": e["name"], "mode": e["mode"], "body": e["body"]} for e in sf1}
added, changed = [], []

# 1. TWRP recovery binary (addition — stock F1 has no system/bin/recovery)
assert "system/bin/recovery" not in f1
p = pay_map["system/bin/recovery"]
assert sha(p["body"]) == "af0a3aa8bc8bf7f5aaf937b84d1c9a66934d8b684558e5789d61cc8c97250c8e"
f1["system/bin/recovery"] = {"name": "system/bin/recovery", "mode": p["mode"], "body": p["body"]}
added.append("system/bin/recovery")

# 2. twrp16 private libs (payload resolved bytes as regular files)
f1["system/lib64/twrp16"] = {"name": "system/lib64/twrp16", "mode": 0o040755, "body": b""}
added.append("system/lib64/twrp16")
for n in twrp16_set:
    b, _ = resolve(pay_map, n)
    tgt = "system/lib64/twrp16/" + n[len(LIB):]
    f1[tgt] = {"name": tgt, "mode": 0o100644, "body": b}
    added.append(tgt)

# 3a. twres (payload-only tree)
for n in sorted(pay_map):
    if n == "twres" or n.startswith("twres/"):
        assert n not in f1
        f1[n] = {"name": n, "mode": pay_map[n]["mode"], "body": pay_map[n]["body"]}
        added.append(n)
# 3b. res additions (payload-only paths under res/)
res_add = sorted(n for n in pay_map
                 if (n == "res" or n.startswith("res/")) and n not in sf1_map)
for n in res_add:
    f1[n] = {"name": n, "mode": pay_map[n]["mode"], "body": pay_map[n]["body"]}
    added.append(n)
print(f"res additions: {res_add}")

# 4. recovery.fstab body swap (mode stays stock)
old = f1["system/etc/recovery.fstab"]
assert pay_map["system/etc/recovery.fstab"]["mode"] == old["mode"] == 0o100644
f1["system/etc/recovery.fstab"] = {"name": old["name"], "mode": old["mode"],
                                   "body": pay_map["system/etc/recovery.fstab"]["body"]}
changed.append("system/etc/recovery.fstab")

# 5. vendor/ + vendor/firmware (additions — stock F1 has no vendor tree)
for n in sorted(pay_map):
    if n == "vendor" or n == "vendor/firmware" or n.startswith("vendor/firmware/"):
        assert n not in f1, n
        f1[n] = {"name": n, "mode": pay_map[n]["mode"], "body": pay_map[n]["body"]}
        added.append(n)

# 6. orchestration
f1["system/bin/turner-setup.sh"] = {"name": "system/bin/turner-setup.sh",
                                    "mode": 0o100755, "body": open(SETUP_SH, "rb").read()}
added.append("system/bin/turner-setup.sh")
f1["system/etc/init/hybrid-services.rc"] = {
    "name": "system/etc/init/hybrid-services.rc", "mode": 0o100644,
    "body": open(SERVICES_RC, "rb").read()}
added.append("system/etc/init/hybrid-services.rc")

# 7. mt8799 rc: append-only breadcrumbs + Skyward block
APPENDAGE = """
# --- hybrid v2 additions (append-only; every stock line above is untouched) ---
on early-init
    write /dev/kmsg HYBRID-BREADCRUMB:early-init

on init
    write /dev/kmsg HYBRID-BREADCRUMB:init

on late-init
    write /dev/kmsg HYBRID-BREADCRUMB:late-init

on boot
    write /dev/kmsg HYBRID-BREADCRUMB:boot
    setprop sys.usb.config adb
    mkdir /data/vendor 0771 system system
    mkdir /data/vendor/touch 0771 system system
    mkdir /data/vendor/touch_state 0771 system system
    mkdir /data/vendor/mqsas_common 0771 system system
    mkdir /data/vendor/bsplog 0775 system system
    mkdir /data/vendor/bsplog/touch 0775 system system
    setprop vendor.teefs_state ready

on late_boot
    write /dev/kmsg HYBRID-BREADCRUMB:late_boot
"""
rc = f1["init.recovery.mt8799.rc"]
assert rc["body"].endswith(b"\n") and not rc["body"].endswith(b"\n\n")
f1["init.recovery.mt8799.rc"] = {"name": rc["name"], "mode": rc["mode"],
                                 "body": rc["body"] + APPENDAGE.encode()}
changed.append("init.recovery.mt8799.rc")

# ------------------------------------------- order: stock order preserved,
# additions inserted at the end of their parent dir's subtree.
sf1_names = [e["name"] for e in sf1]


def pack_f1(f1dict):
    order = [n for n in sf1_names if n in f1dict]

    def parent(n):
        return n.rsplit("/", 1)[0] if "/" in n else ""

    new_names = sorted(set(f1dict) - set(sf1_map),
                       key=lambda n: (n.count("/"), n))
    for n in new_names:
        par = parent(n)
        if par == "":
            order.append(n)
            continue
        idx = order.index(par)
        j = idx + 1
        while j < len(order) and order[j].startswith(par + "/"):
            j += 1
        order.insert(j, n)
    assert [n for n in order if n in sf1_map] == \
        [n for n in sf1_names if n in f1dict], "stock order drift"
    assert set(order) == set(f1dict)
    entries = []
    for idx, name in enumerate(order):
        e = f1dict[name]
        entries.append({"name": name, "ino": 300000 + idx, "mode": e["mode"],
                        "uid": 0, "gid": 0, "nlink": 1, "mtime": 0,
                        "body": e["body"], "devmaj": 0, "devmin": 0,
                        "rdevmaj": 0, "rdevmin": 0})
    cpio = write_newc(entries, upper=False,
                      trailer={"ino": 300000 + len(entries), "mode": 493})
    return entries, cpio, lz4_legacy_compress(cpio)


# ------------------------------------------------ stage-4b authorized cuts
# Preference order mandated by the parent agent; twrp16 and
# vendor/firmware are untouchable. Budget / minimum headroom:
BUDGET = 66563880
MIN_HEADROOM = 200000
F0_LEN = os.path.getsize(F0_LZ4_REUSE)
measurements = {}

# Faithfulness check: the refactored packer must reproduce stage-4's
# uncut F1 fragment byte-for-byte before any cut is trusted.
_, _, lz_base = pack_f1(f1)
s4_delta = json.load(open(os.path.join(S4, ".work", "f1_delta.json")))
assert sha(lz_base) == s4_delta["f1_lz4_sha256"], "pack_f1 refactor drift!"
measurements["baseline_f1_lz4"] = len(lz_base)
measurements["baseline_fragments_total"] = F0_LEN + len(lz_base)
print(f"pack_f1 refactor verified: uncut F1 lz4 {len(lz_base)} B "
      f"(== stage-4 fragment)")

# CUT-1: delete the OS4 stock F1 res/ tree. The two 0-byte directory
# entries `res` and `res/images` are retained ONLY as parent paths for
# the retained payload additions (res/fonts/*, res/images/dummyfile);
# every stock res file (572) and the other 4 stock res dirs are removed.
stock_res = sorted(n for n in sf1_map if n == "res" or n.startswith("res/"))
KEEP_DIRS = ["res", "res/images"]
cut1_removed = [n for n in stock_res if n not in KEEP_DIRS]
f1_final = dict(f1)
for n in cut1_removed:
    del f1_final[n]

f1_entries, f1_cpio, f1_lz4 = pack_f1(f1_final)
headroom = BUDGET - (F0_LEN + len(f1_lz4))
measurements["cut1_f1_lz4"] = len(f1_lz4)
measurements["cut1_saving"] = len(lz_base) - len(f1_lz4)
measurements["cut1_headroom"] = headroom
cuts_applied = [f"CUT-1: stock F1 res/ tree removed "
                f"({len(cut1_removed)} of {len(stock_res)} entries; "
                f"`res`+`res/images` dir entries retained as parents)"]
removed_stock = list(cut1_removed)
cut2_removed_additions = []
print(f"CUT-1: -{measurements['cut1_saving']} B lz4 -> F1 {len(f1_lz4)} B, "
      f"headroom {headroom} B")

if headroom < MIN_HEADROOM:
    # CUT-2: additionally drop the payload res additions (fonts set).
    cut2_removed_additions = list(res_add)
    for n in cut2_removed_additions:
        f1_final.pop(n, None)
    added = [n for n in added if n in f1_final]
    f1_entries, f1_cpio, f1_lz4 = pack_f1(f1_final)
    headroom = BUDGET - (F0_LEN + len(f1_lz4))
    measurements["cut2_f1_lz4"] = len(f1_lz4)
    measurements["cut2_headroom"] = headroom
    cuts_applied.append(f"CUT-2: payload res additions dropped "
                        f"({len(cut2_removed_additions)} entries: fonts set)")
    print(f"CUT-2: F1 {len(f1_lz4)} B, headroom {headroom} B")
    if headroom < MIN_HEADROOM:
        json.dump(measurements, open(os.path.join(WORK, "cut_measurements.json"), "w"), indent=1)
        print(f"STOP: CUT-1+CUT-2 still insufficient: fragments total "
              f"{F0_LEN + len(f1_lz4)} B vs budget {BUDGET} B "
              f"(headroom {headroom} B < {MIN_HEADROOM} B). No image written.")
        sys.exit(3)
f1 = f1_final

# ------------------------------------------------ stage-6: patched libtwrpminui
# Substitute the patched body (force legacy_modeset=true) and re-pack.
# Everything downstream (tree, artifacts, delta, assembly) uses the
# re-packed final fragment.
MINUI_TGT = "system/lib64/twrp16/libtwrpminui.so"
MINUI_ORIG_SHA = "0615820440c694fe840eb9ad58dcd7dcd22818dde5f0efa78434e414c1d7d269"
MINUI_PATCHED_PATH = os.path.join(S6, "libtwrpminui.so.patched")
patched_body = open(MINUI_PATCHED_PATH, "rb").read()
assert sha(f1_final[MINUI_TGT]["body"]) == MINUI_ORIG_SHA, "pre-patch lib mismatch"
assert len(patched_body) == len(f1_final[MINUI_TGT]["body"]) == 268768
f1_final[MINUI_TGT] = {"name": MINUI_TGT,
                       "mode": f1_final[MINUI_TGT]["mode"],
                       "body": patched_body}
# (vii) v2.7 splash device line: official YARP builds resetprop the whole
# ro.product.*.model family to the marketing name at boot (variant-script.sh
# in the sm8750 image: miro -> "REDMI K80 Pro", piano -> "Xiaomi Pad 8 Pro");
# the splash renders ro.product.model. Turner stock leaves 25079RPDCC (the
# model number) there, so our splash read "turner - 25079RPDCC". Bake the
# name into prop.default (same mechanism as the stage7 release bake);
# model_for_attestation deliberately untouched.
prop = f1_final["prop.default"]["body"].decode()
for part in ("system", "vendor", "odm", "product", "system_ext"):
    old = f"ro.product.{part}.model=25079RPDCC\n"
    assert prop.count(old) == 1, old
    prop = prop.replace(old, f"ro.product.{part}.model=REDMI K Pad\n")
f1_final["prop.default"] = {"name": "prop.default",
                            "mode": f1_final["prop.default"]["mode"],
                            "body": prop.encode()}

f1_entries, f1_cpio, f1_lz4 = pack_f1(f1_final)
headroom_final = BUDGET - (F0_LEN + len(f1_lz4))
assert headroom_final >= MIN_HEADROOM, \
    f"STOP: post-patch headroom {headroom_final} < {MIN_HEADROOM}"
stage6_info = {
    "patched_entry": MINUI_TGT,
    "orig_sha256": MINUI_ORIG_SHA,
    "patched_sha256": sha(patched_body),
    "patch_sites": ["0x1c3d4 cbz-imm 0x48->0x28 (target 0x1c3fc -> 0x1c3f8)",
                    "0x1c3f8 cset w8,eq (e8179f1a) -> mov w8,#1 (28008052)"],
    "v21_equivalent_headroom": headroom,
    "final_f1_lz4": len(f1_lz4),
    "final_headroom": headroom_final,
}
print(f"stage-6 patch substituted: {MINUI_TGT} sha={sha(patched_body)[:16]}... "
      f"F1 lz4 {len(f1_lz4)} B, final headroom {headroom_final} B")

# ------------------------------------------------ stage-7: v2.3 delta
# Applied to the finished v2.2-equivalent f1_final. This block is the
# ONLY difference between the v2.2 and v2.3 images.
# (i) orchestration bodies -> stage-7 edited versions.
for tgt, srcp in (("system/etc/init/hybrid-services.rc",
                   os.path.join(S11, "hybrid-services.rc")),
                  ("system/bin/turner-setup.sh",
                   os.path.join(S21, "turner-setup.sh"))):
    body = open(srcp, "rb").read()
    assert body != f1_final[tgt]["body"], tgt
    f1_final[tgt] = {"name": tgt, "mode": f1_final[tgt]["mode"], "body": body}
# (ii) prop.default: bake the installed ROM's release (17) over the
# ramdisk's stale 15 (no resetprop exists in recovery; patch levels in
# the same file already read 2026-10-01 on both sides). default.prop is
# a symlink to prop.default, so one body edit covers both.
prop = f1_final["prop.default"]["body"].decode()
for old, new in (("ro.build.version.release=15\n", "ro.build.version.release=17\n"),
                 ("ro.build.version.release_or_codename=15\n",
                  "ro.build.version.release_or_codename=17\n"),
                 ("ro.build.version.release_or_preview_display=15\n",
                  "ro.build.version.release_or_preview_display=17\n"),
                 ("ro.system.build.version.release_or_codename=15\n",
                  "ro.system.build.version.release_or_codename=17\n")):
    assert prop.count(old) == 1, old
    prop = prop.replace(old, new)
f1_final["prop.default"] = {"name": "prop.default",
                            "mode": f1_final["prop.default"]["mode"],
                            "body": prop.encode()}
# (iii) the four OS4 VINTF manifests for the mitee HALs (original bytes
# from the installed vendor.img, staged in stage7/manifests/), so
# servicemanager knows the declared instances from boot, before the
# vendor mount exists.
man_mode = f1_final["system/etc/vintf/manifest/"
                    "android.hardware.fastboot-service.example.xml"]["mode"]
stage7_manifests = []
for fn in sorted(os.listdir(os.path.join(S7, "manifests"))):
    tgt = "system/etc/vintf/manifest/" + fn
    assert tgt not in f1_final, tgt
    f1_final[tgt] = {"name": tgt, "mode": man_mode,
                     "body": open(os.path.join(S7, "manifests", fn), "rb").read()}
    stage7_manifests.append(tgt)
# (iv) system/etc/hybrid/: the a7 libkmsglog LD_PRELOAD shim (KPad-
# verified bytes from the a7 image) and the bundled touch-module
# fallback copy (OS4 vendor_dlkm bytes) the setup script references.
f1_final["system/etc/hybrid"] = {"name": "system/etc/hybrid",
                                 "mode": 0o040755, "body": b""}
kms = open(os.path.join(S7, "libkmsglog.so"), "rb").read()
assert sha(kms) == "0454981809157d050f5770bd215563e19b9788a635bf34a2d162746d782443d1"
f1_final["system/etc/hybrid/libkmsglog.so"] = {
    "name": "system/etc/hybrid/libkmsglog.so", "mode": 0o100644, "body": kms}
ko = open(os.path.join(S3, "f1_new", "system/etc/hybrid",
                       "nt36536e_touch_turner.ko"), "rb").read()
assert sha(ko) == "151619c748fb836268ab5c652eff92457b15493fe0a617358d75ac40bdecfa5f"
f1_final["system/etc/hybrid/nt36536e_touch_turner.ko"] = {
    "name": "system/etc/hybrid/nt36536e_touch_turner.ko",
    "mode": 0o100644, "body": ko}
# (v) v2.4: the binder trace stub — a hand-crafted aarch64 .so exporting
# only AIBinder_Class_setTransactionCodeToFunctionNameMap (a no-op ret),
# preloaded into keymint/gatekeeper so their library order can return
# to the a7 ramdisk-first arrangement (see stage8 rc header).
stub = open(os.path.join(S9, "libbinder_trace_stub_v25.so"), "rb").read()
assert sha(stub) == "fabb03f6bdf815142a43aebe434c103feec2f3b6d6a44acb38ac26ad843f3567", "v25 stub sha drift"
# v3.0: the stub is NOT shipped — the preload route never satisfied
# rkp's versioned reference (v2.9 CANNOT LINK, captured verbatim).
# Instead the TEE HALs get the installed system's real libbinder_ndk.so
# through the sysndk symlink dir added below.
# (vi) v2.5 leg 1: spawn_touch — static helper turner-setup uses to
# launch the touch HAL directly (a7-style) with stderr to /dev/kmsg.
spt = open(os.path.join(S20, "spawn_hal"), "rb").read()
assert sha(spt) == "a288ad0d8725e84c09e3898d925ea8c43c2b4bb14db08eb59238861e2bb47ae6", "spawn_hal sha drift"
f1_final["system/etc/hybrid/spawn_hal"] = {
    "name": "system/etc/hybrid/spawn_hal",
    "mode": 0o100755, "body": spt}
# v3.0: sysndk dir — contains ONLY libbinder_ndk.so, a symlink to the
# installed system's copy. First in the TEE LD_LIBRARY_PATH, it makes
# DT_NEEDED libbinder_ndk.so resolve to the system generation (which
# natively has AIBinder_Class_setTransactionCodeToFunctionNameMap)
# while libbinder.so still resolves to the ramdisk copy, keeping the
# RECO parcel tag servicemanager accepts.
f1_final["system/etc/hybrid/sysndk"] = {
    "name": "system/etc/hybrid/sysndk",
    "mode": 0o040755, "body": b""}
# v3.2: the payload's own binder pair, symlinked into one dir placed
# first in the HAL namespaces: consistent SDK 36 pair, RECO parcels,
# and its libbinder_ndk exports the LIBBINDER_NDK36 symbol the
# installed system's rkp/gatekeeper NDK libs require. (v3.0/v3.1's
# sysndk pointed at the installed system's ndk, whose own dependency
# on its libbinder internals broke the split pair.)
f1_final["system/etc/hybrid/twrpbinder"] = {
    "name": "system/etc/hybrid/twrpbinder",
    "mode": 0o40755, "body": b""}
# v3.3: log-capture preload (mirrors libbase CHECK messages to
# stderr -> /dev/kmsg; logd is dead in this recovery).
logcap = open(os.path.join(S25, "liblogcapture.so"), "rb").read()
f1_final["system/etc/hybrid/liblogcapture.so"] = {
    "name": "system/etc/hybrid/liblogcapture.so",
    "mode": 0o100644, "body": logcap}
# v3.8: SPLIT pair. libbinder_ndk stays the payload's SDK36 build
# (exports the LIBBINDER_NDK36 symbol the system NDK client libs
# need), but libbinder.so now points at the RAMDISK's SDK35 build --
# the Parcel writer must match servicemanager's generation: with
# the SDK36 libbinder writing, SM's SDK35 AIDL stub rejects the
# mitee HALs' addService parcels (EX_BAD_PARCELABLE -2) before the
# (patched) VINTF gate is even reached, while health (SDK35 stack)
# registers fine. The SDK36 ndk's only binder35-missing imports are
# the unused Accessor family plus get_trace_enabled_tags, the
# latter provided by liblogcapture v3 (preloaded first).
for bn, tgt in (("libbinder.so", "/system/lib64/libbinder.so"),
                ("libbinder_ndk.so", "/system/lib64/twrp16/libbinder_ndk.so")):
    f1_final[f"system/etc/hybrid/twrpbinder/{bn}"] = {
        "name": f"system/etc/hybrid/twrpbinder/{bn}",
        "mode": 0o120777, "body": tgt.encode()}
# v3.1: the real linker namespace configuration. init's early-init
# copy (/system/etc/init/hw/init.rc) installs it at
# /linkerconfig/ld.config.txt; until now the source file did not
# exist in the merged ramdisk, the copy failed, and F0's empty file
# left every process without namespace config.
ldcfg = open(os.path.join(S19, "ld.config.txt"), "rb").read()
f1_final["system/etc/ld.config.txt"] = {
    "name": "system/etc/ld.config.txt",
    "mode": 0o100644, "body": ldcfg}
# ------------------------------------------------ stage-21: v3.5 delta
# (i) VINTF experiment: v3.4's log capture proved servicemanager
# rejects all three HAL registrations with "VINTF declaration
# error." (status -2), although the mitee fragments sit in
# /system/etc/vintf/manifest/ in the same format as the working
# fastboot fragment. Copy every needed declaration INTO the fastboot
# fragment file (proven to be read: IFastboot is found in the
# recovery manifest at runtime). The original mitee files stay as
# the control. The touch declaration was missing from F1 entirely;
# it is added both here and as its own file (odm bytes).
fbp = "system/etc/vintf/manifest/android.hardware.fastboot-service.example.xml"
fb = f1_final[fbp]["body"].decode()
extra = """    <hal format="aidl">
        <name>android.hardware.gatekeeper</name>
        <fqname>IGatekeeper/default</fqname>
    </hal>
    <hal format="aidl">
        <name>android.hardware.security.keymint</name>
        <version>3</version>
        <fqname>IKeyMintDevice/default</fqname>
    </hal>
    <hal format="aidl">
        <name>android.hardware.security.keymint</name>
        <version>3</version>
        <fqname>IRemotelyProvisionedComponent/default</fqname>
    </hal>
    <hal format="aidl">
        <name>android.hardware.security.secureclock</name>
        <fqname>ISecureClock/default</fqname>
    </hal>
    <hal format="aidl">
        <name>android.hardware.security.sharedsecret</name>
        <fqname>ISharedSecret/default</fqname>
    </hal>
    <hal format="aidl">
        <name>vendor.xiaomi.hw.touchfeature</name>
        <fqname>ITouchFeature/default</fqname>
    </hal>
"""
assert "</manifest>" in fb and "IGatekeeper" not in fb
fb_new = fb  # v3.7: duplication reverted (manifest conflict); fragment stays original
f1_final[fbp] = {"name": fbp, "mode": f1_final[fbp]["mode"],
                 "body": fb_new.encode()}
tfp = "system/etc/vintf/manifest/vendor.xiaomi.hw.touchfeature-service.xml"
assert tfp not in f1_final
f1_final[tfp] = {"name": tfp, "mode": 0o100644, "body": b"""<!--
    Input:
        vendor/xiaomi/proprietary/touch/touchfeature_v2/touchfeature/default/vendor.xiaomi.hw.touchfeature-service.xml
-->
<manifest version="8.0" type="device">
    <hal format="aidl">
        <name>vendor.xiaomi.hw.touchfeature</name>
        <fqname>ITouchFeature/default</fqname>
    </hal>
</manifest>
"""}
# (ii) bundle xiaomi_touch_turner.ko (OS4 vendor_dlkm bytes, staged in
# stage20) next to the already-bundled nt36536e; the v3.5 setup tries
# the bundled pair before the vendor_dlkm closure walk.
xko = open(os.path.join(S20, "xiaomi_touch_turner.ko"), "rb").read()
assert len(xko) == 207696
f1_final["system/etc/hybrid/xiaomi_touch_turner.ko"] = {
    "name": "system/etc/hybrid/xiaomi_touch_turner.ko",
    "mode": 0o100644, "body": xko}
# =========================================================================
# v3.10: the HALs become proper init services. v3.9 proved the whole
# library/registration stack works -- all three HALs registered and
# lived -- but they were SIGKILLed at the exact moment the oneshot
# turner-setup exited (23.882s, 65 ms after setup's exit): children of
# a dying oneshot do not survive here, while init services (like
# tee-supplicant, alive in every build) are supervised by init itself.
# The original reason for direct spawn (init swallows stderr) is gone:
# liblogcapture mirrors the HALs' logs to /dev/kmsg via LD_PRELOAD,
# which the rc setenv lines carry. Setup now only ctl.starts them.
# =========================================================================
_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_start_and_check = """
start_and_check() {
    # $1 = label/failure token, $2 = init service name, $3 = grace s.
    # v3.10: HALs are init services now; judge by init.svc state.
    label=$1; svc=$2; grace=$3
    setprop ctl.start "${svc}"
    sleep "${grace}"
    st=$(getprop "init.svc.${svc}")
    if [ "${st}" = "running" ]; then
        log_msg "${label} service ${svc} running after grace (registered)"
        return 0
    fi
    log_msg "${label} service ${svc} state=${st} after grace period"
    FAILURES="${FAILURES} ${label}"
    return 1
}

svc_check() {
    # $1 = label, $2 = service (already started; no extra wait).
    label=$1; svc=$2
    st=$(getprop "init.svc.${svc}")
    if [ "${st}" = "running" ]; then
        log_msg "${label} service ${svc} running (registered)"
        return 0
    fi
    log_msg "${label} service ${svc} state=${st}"
    FAILURES="${FAILURES} ${label}"
    return 1
}

"""
_anchor = "spawn_touch_hal() {"
assert _anchor in _setup
_setup = _setup.replace(_anchor, _start_and_check + _anchor, 1)

_old_touch = """spawn_touch_hal() {
    [ -e /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service ] || {
        log_msg "touch HAL binary missing (odm not mounted?)"
        FAILURES="${FAILURES} touch-hal"
        return 1
    }
    spawn_and_check touch-hal 1000 1000 1000,1004 "/system/etc/hybrid/twrpbinder" "${KMSLOG}" \\
        /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service
}"""
_new_touch = """spawn_touch_hal() {
    [ -e /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service ] || {
        log_msg "touch HAL binary missing (odm not mounted?)"
        FAILURES="${FAILURES} touch-hal"
        return 1
    }
    start_and_check touch-hal vendor.touchfeature 3
}"""
assert _old_touch in _setup
_setup = _setup.replace(_old_touch, _new_touch, 1)

_old_tee = """spawn_tee_chain() {
    spawn_and_check keymint 0 0 0,1000,1009 "/system/etc/hybrid/twrpbinder" "${KMSLOG}" \\
        /vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee
    log_msg "step:keymint handled"
    spawn_and_check gatekeeper 0 0 0,1000 "/system/etc/hybrid/twrpbinder" "${KMSLOG}" \\
        /vendor/bin/hw/android.hardware.gatekeeper-service.mitee
    log_msg "step:gatekeeper handled"
}"""
_new_tee = """spawn_tee_chain() {
    # v3.10: start both TEE HAL services back to back, then judge both
    # after one shared grace window (they register in parallel; the
    # serialized 5s+5s waits of the spawn era are gone).
    setprop ctl.start vendor.keymint-mitee
    setprop ctl.start vendor.gatekeeper-mitee
    sleep 5
    svc_check keymint vendor.keymint-mitee
    log_msg "step:keymint handled"
    svc_check gatekeeper vendor.gatekeeper-mitee
    log_msg "step:gatekeeper handled"
}"""
assert _old_tee in _setup
_setup = _setup.replace(_old_tee, _new_tee, 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()

_rc = f1_final["system/etc/init/hybrid-services.rc"]["body"].decode()
_rc += """
# --- v3.10: the three HALs as init services ------------------------------
# Same binaries, users, groups and library environment the direct-spawn
# route proved in v3.9 (twrpbinder split pair + liblogcapture/libkmsglog
# preload). As init services they are supervised by init and survive
# turner-setup's exit -- the v3.9 spawns were SIGKILLed with it.
service vendor.keymint-mitee /vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee
    class hal
    user root
    group root system drmrpc
    capabilities DAC_OVERRIDE SYS_RAWIO
    setenv LD_LIBRARY_PATH /system/etc/hybrid/twrpbinder
    setenv LD_PRELOAD /system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
    seclabel u:r:recovery:s0
    disabled

service vendor.gatekeeper-mitee /vendor/bin/hw/android.hardware.gatekeeper-service.mitee
    class hal
    user root
    group root system
    setenv LD_LIBRARY_PATH /system/etc/hybrid/twrpbinder
    setenv LD_PRELOAD /system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
    seclabel u:r:recovery:s0
    disabled

service vendor.touchfeature /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service
    class hal
    user system
    group system input
    capabilities SYS_NICE
    setenv LD_LIBRARY_PATH /system/etc/hybrid/twrpbinder
    setenv LD_PRELOAD /system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
    seclabel u:r:recovery:s0
    disabled
"""
f1_final["system/etc/init/hybrid-services.rc"]["body"] = _rc.encode()



# =========================================================================
# v3.11: the touch HAL goes back under spawn_hal -- but this time the
# spawner is a long-lived init service (turner-touch-sup.sh) that never
# exits and respawns the HAL if it dies, so the v3.9 setup-exit kill
# cannot recur. Reason: as a plain init service (v3.10) the HAL
# registers and runs, the panel IRQs fire (IRQ61 +634/15s while
# tapping), enable_touch_raw=1 -- yet event2 stays silent, and the
# service's logs go nowhere (logd dead, stderr /dev/null). Under
# spawn_hal + liblogcapture its ALOG reaches /dev/kmsg (proven v3.3:
# "[THP0] thp_daemon_main start"). The daemon lives in
# /odm/lib64/libtouchreport.so (dlopen'ed by the HAL); we need the
# HAL's own words on why no events come out. TEE services unchanged.
# =========================================================================
_sup = """#!/system/bin/sh
# turner-touch-sup.sh -- v3.11 supervisor for the Xiaomi touch HAL.
# spawn_hal gives the HAL its proven environment (twrpbinder split
# pair + liblogcapture/libkmsglog preload, stderr -> /dev/kmsg) and
# drops it to system:input. This script is an init service that never
# exits; it respawns the HAL whenever it dies.
LOGF=/tmp/spawn-touch-sup.log
while true; do
    /system/etc/hybrid/spawn_hal "${LOGF}" 1000 1000 1000,1004 \
        "/system/etc/hybrid/twrpbinder" \
        "/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so" \
        /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service
    pid=$(sed -n 's/.* pid \\([0-9]*\\).*/\\1/p' "${LOGF}" 2>/dev/null | tail -n 1)
    echo "turner-touch-sup: spawned touch HAL pid=${pid}" > /dev/kmsg
    while [ -n "${pid}" ] && [ -d "/proc/${pid}" ]; do sleep 2; done
    echo "turner-touch-sup: touch HAL exited, respawning in 2s" > /dev/kmsg
    sleep 2
done
"""
f1_final["system/bin/turner-touch-sup.sh"] = {
    "name": "system/bin/turner-touch-sup.sh", "mode": 0o100755,
    "body": _sup.encode()}

_rc = f1_final["system/etc/init/hybrid-services.rc"]["body"].decode()
_old_svc = """service vendor.touchfeature /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service
    class hal
    user system
    group system input
    capabilities SYS_NICE
    setenv LD_LIBRARY_PATH /system/etc/hybrid/twrpbinder
    setenv LD_PRELOAD /system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
    seclabel u:r:recovery:s0
    disabled
"""
_new_svc = """service vendor.touchfeature-sup /system/bin/turner-touch-sup.sh
    class hal
    user root
    group root system input
    seclabel u:r:recovery:s0
    disabled
"""
assert _old_svc in _rc
_rc = _rc.replace(_old_svc, _new_svc, 1)
f1_final["system/etc/init/hybrid-services.rc"]["body"] = _rc.encode()

_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_old_call = "start_and_check touch-hal vendor.touchfeature 3"
_new_call = """start_and_check touch-hal vendor.touchfeature-sup 3
    log_msg "touch-sup spawn log: $(cat /tmp/spawn-touch-sup.log 2>/dev/null || echo MISSING)"
"""
assert _old_call in _setup
_setup = _setup.replace(_old_call, _new_call, 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()


# =========================================================================
# v3.12: stage_touch_owners now chowns EVERY file under
# /sys/class/touch/touch_dev/ (glob), not just the Skyward-toml list.
# v3.11 evidence: the THP daemon (libtouchreport_hal.so) loaded fine,
# then stuck forever retrying
#   "file_access_and_open: open /sys/class/touch/touch_dev/abnormal_event
#    failed, retry!"
# because that node is root:root 0664 and the HAL runs as system. The
# stock odm rc (vendor.xiaomi.hw.touchfeature-service.rc, on boot)
# chowns abnormal_event -- and every other touch_dev node -- to
# system:system 0664; the installed rcs never run in recovery, and the
# toml-derived list we copied missed the nodes that actually exist on
# this machine (abnormal_event, palm_sensor, panel_*, touch_ic_buffer,
# touch_thp_ic_cmd[_data], touch_vendor, ...). The glob mirrors stock.
# =========================================================================
_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_old_loop = """    for n in /dev/xiaomi-touch-knock /dev/xiaomi-thp \\
        /sys/class/touch/touch_dev/enable_touch_raw \\
        /sys/class/touch/touch_dev/resolution_factor \\
        /sys/class/touch/touch_dev/update_rawdata \\
        /sys/class/touch/touch_dev/gesture_single_tap_state \\
        /sys/class/touch/touch_dev/fod_press_status \\
        /sys/class/touch/touch_dev/suspend_state \\
        /sys/class/touch/touch_dev/touch_sensor \\
        /sys/class/touch/touch_dev/touch_sensor_ctrl \\
        /sys/class/touch/touch_dev/touch_active_status \\
        /sys/class/touch/touch_dev/touch_finger_status \\
        /sys/class/touch/touch_dev/touch_thp_cmd \\
        /sys/class/touch/touch_dev/touch_thp_cmd_data \\
        /sys/class/touch/touch_dev/touch_thp_cmd_ready \\
        /proc/tp_selftest /proc/tp_hal_version /proc/tp_fw_version \\
        /proc/tp_lockdown_info; do
        [ -e "${n}" ] || continue
        chown system:system "${n}" 2>/dev/null
        chmod 0664 "${n}" 2>/dev/null
    done
"""
_new_loop = """    for n in /dev/xiaomi-touch-knock /dev/xiaomi-thp \\
        /proc/tp_selftest /proc/tp_hal_version /proc/tp_fw_version \\
        /proc/tp_lockdown_info; do
        [ -e "${n}" ] || continue
        chown system:system "${n}" 2>/dev/null
        chmod 0664 "${n}" 2>/dev/null
    done
    # v3.12: every touch_dev sysfs node, like the stock odm rc's
    # on-boot block (abnormal_event included -- the THP daemon blocks
    # on it). The glob skips the power/ dir and the subsystem symlink.
    for n in /sys/class/touch/touch_dev/*; do
        [ -f "${n}" ] || continue
        chown system:system "${n}" 2>/dev/null
        chmod 0664 "${n}" 2>/dev/null
    done
"""
assert _old_loop in _setup, "staging loop not found"
_setup = _setup.replace(_old_loop, _new_loop, 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()


# =========================================================================
# v3.13: keymint + gatekeeper move under supervisors too (the v3.11
# touch pattern), so their LOGCAP reaches dmesg. Reason: touch is
# fixed (v3.12) and OTG works, but metadata decrypt still fails AFTER
# setup completes with the HALs live -- and as init services the two
# TEE HALs log nowhere (stderr /dev/null, logd dead), so the failure
# is invisible. Spawn parameters are the proven v3.9 ones (keymint
# uid/gid 0/0 groups 0,1000,1009; gatekeeper 0/0 0,1000; twrpbinder
# ldpath; liblogcapture+libkmsglog preload). tee-supplicant stays an
# init service. Nothing else changes.
# =========================================================================
_tee_sup = """#!/system/bin/sh
# turner-tee-sup.sh -- v3.13 supervisor for the mitee TEE HALs.
# Usage: turner-tee-sup.sh keymint|gatekeeper
# spawn_hal gives the HAL the proven v3.9 environment (twrpbinder
# split binder pair + liblogcapture/libkmsglog preload, stderr ->
# /dev/kmsg). This script is an init service that never exits; it
# respawns its HAL whenever it dies.
name="$1"
case "${name}" in
    keymint)
        BIN=/vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee
        GROUPS=0,1000,1009 ;;
    gatekeeper)
        BIN=/vendor/bin/hw/android.hardware.gatekeeper-service.mitee
        GROUPS=0,1000 ;;
    *) echo "turner-tee-sup: unknown target '${name}'" > /dev/kmsg; exit 1 ;;
esac
LOGF=/tmp/spawn-${name}-sup.log
while true; do
    /system/etc/hybrid/spawn_hal "${LOGF}" 0 0 "${GROUPS}" \
        "/system/etc/hybrid/twrpbinder" \
        "/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so" \
        "${BIN}"
    pid=$(sed -n 's/.* pid \\([0-9]*\\).*/\\1/p' "${LOGF}" 2>/dev/null | tail -n 1)
    echo "turner-tee-sup: spawned ${name} pid=${pid}" > /dev/kmsg
    while [ -n "${pid}" ] && [ -d "/proc/${pid}" ]; do sleep 2; done
    echo "turner-tee-sup: ${name} exited, respawning in 2s" > /dev/kmsg
    sleep 2
done
"""
f1_final["system/bin/turner-tee-sup.sh"] = {
    "name": "system/bin/turner-tee-sup.sh", "mode": 0o100755,
    "body": _tee_sup.encode()}

_rc = f1_final["system/etc/init/hybrid-services.rc"]["body"].decode()
_old_km = """service vendor.keymint-mitee /vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee
    class hal
    user root
    group root system drmrpc
    capabilities DAC_OVERRIDE SYS_RAWIO
    setenv LD_LIBRARY_PATH /system/etc/hybrid/twrpbinder
    setenv LD_PRELOAD /system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
    seclabel u:r:recovery:s0
    disabled
"""
_new_km = """service vendor.keymint-mitee-sup /system/bin/turner-tee-sup.sh keymint
    class hal
    user root
    group root system
    seclabel u:r:recovery:s0
    disabled
"""
assert _old_km in _rc, "keymint svc block not found"
_rc = _rc.replace(_old_km, _new_km, 1)
_old_gk = """service vendor.gatekeeper-mitee /vendor/bin/hw/android.hardware.gatekeeper-service.mitee
    class hal
    user root
    group root system
    setenv LD_LIBRARY_PATH /system/etc/hybrid/twrpbinder
    setenv LD_PRELOAD /system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
    seclabel u:r:recovery:s0
    disabled
"""
_new_gk = """service vendor.gatekeeper-mitee-sup /system/bin/turner-tee-sup.sh gatekeeper
    class hal
    user root
    group root system
    seclabel u:r:recovery:s0
    disabled
"""
assert _old_gk in _rc, "gatekeeper svc block not found"
_rc = _rc.replace(_old_gk, _new_gk, 1)
f1_final["system/etc/init/hybrid-services.rc"]["body"] = _rc.encode()

_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_old_chain = """spawn_tee_chain() {
    # v3.10: start both TEE HAL services back to back, then judge both
    # after one shared grace window (they register in parallel; the
    # serialized 5s+5s waits of the spawn era are gone).
    setprop ctl.start vendor.keymint-mitee
    setprop ctl.start vendor.gatekeeper-mitee
    sleep 5
    svc_check keymint vendor.keymint-mitee
    log_msg "step:keymint handled"
    svc_check gatekeeper vendor.gatekeeper-mitee
    log_msg "step:gatekeeper handled"
}"""
_new_chain = """sup_check() {
    _logf="/tmp/spawn-$1-sup.log"
    _pid=$(sed -n 's/.* pid \\([0-9]*\\).*/\\1/p' "${_logf}" 2>/dev/null | tail -n 1)
    if [ -n "${_pid}" ] && [ -d "/proc/${_pid}" ]; then
        log_msg "$1 supervisor-spawned pid ${_pid} alive"
    else
        log_msg "$1 SUPERVISOR FAILURE (pid='${_pid}')"
        FAILURES="${FAILURES} $1"
    fi
    log_msg "$1 spawn log: $(cat "${_logf}" 2>/dev/null || echo MISSING)"
}

spawn_tee_chain() {
    # v3.13: both TEE HALs run under supervisors (the v3.11 touch
    # pattern) so their logs reach dmesg during decrypt attempts.
    setprop ctl.start vendor.keymint-mitee-sup
    setprop ctl.start vendor.gatekeeper-mitee-sup
    sleep 5
    sup_check keymint
    log_msg "step:keymint handled"
    sup_check gatekeeper
    log_msg "step:gatekeeper handled"
}"""
assert _old_chain in _setup, "spawn_tee_chain not found"
_setup = _setup.replace(_old_chain, _new_chain, 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()


# =========================================================================
# v3.14: bring up keystore2 -- the missing middle layer of the decrypt
# chain. v3.13 evidence: with keymint+gatekeeper live and logging, the
# metadata decrypt attempt produced ZERO KeyMint traffic; the recovery
# binary's embedded vold logs "Vold unable to connect to keystore2"
# when the service is absent. Official YARP ramdisks ship keystore2
# (system/bin/keystore2 + keystore2.rc, root, workdir /tmp/misc/
# keystore); our hybrid has none. We run the INSTALLED system's
# keystore2 under a supervisor, with the split binder pair first in
# its library path (its service registration must speak RECO to the
# ramdisk servicemanager) and installed-system libs after.
# =========================================================================
_ks2_sup = """#!/system/bin/sh
# turner-ks2-sup.sh -- v3.14 supervisor for the installed keystore2.
# Never exits; respawns keystore2 if it dies. Logs via spawn_hal ->
# /dev/kmsg (liblogcapture mirrors its ALOG there too).
mkdir -p /tmp/misc/keystore
ulimit -l unlimited 2>/dev/null
LOGF=/tmp/spawn-keystore2-sup.log
LIBS="/system/etc/hybrid/twrpbinder:/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex/com.android.runtime/lib64:/apex/com.android.i18n/lib64:/system/lib64/twrp16"
while true; do
    /system/etc/hybrid/spawn_hal "${LOGF}" 0 0 0,1017,1007 \
        "${LIBS}" \
        "/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so" \
        /mnt/system/system/bin/keystore2 /tmp/misc/keystore
    pid=$(sed -n 's/.* pid \\([0-9]*\\).*/\\1/p' "${LOGF}" 2>/dev/null | tail -n 1)
    echo "turner-ks2-sup: spawned keystore2 pid=${pid}" > /dev/kmsg
    while [ -n "${pid}" ] && [ -d "/proc/${pid}" ]; do sleep 2; done
    echo "turner-ks2-sup: keystore2 exited, respawning in 2s" > /dev/kmsg
    sleep 2
done
"""
f1_final["system/bin/turner-ks2-sup.sh"] = {
    "name": "system/bin/turner-ks2-sup.sh", "mode": 0o100755,
    "body": _ks2_sup.encode()}

_rc = f1_final["system/etc/init/hybrid-services.rc"]["body"].decode()
_ks2_svc = """
service vendor.keystore2-sup /system/bin/turner-ks2-sup.sh
    class hal
    user root
    group root system
    seclabel u:r:recovery:s0
    disabled
"""
assert "vendor.keystore2-sup" not in _rc
_rc = _rc.rstrip("\n") + "\n" + _ks2_svc
f1_final["system/etc/init/hybrid-services.rc"]["body"] = _rc.encode()

_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_ks2_fn = """
spawn_keystore2() {
    # v3.14: run the installed keystore2 (see build note). Its key
    # contexts file must exist at the AOSP path; the ramdisk may not
    # carry it, so link the installed system's copy in if missing.
    mkdir -p /tmp/misc/keystore
    if [ ! -e /system/etc/selinux/plat_keystore2_key_contexts ]; then
        mkdir -p /system/etc/selinux 2>/dev/null
        ln -s /mnt/system/system/etc/selinux/plat_keystore2_key_contexts \
            /system/etc/selinux/plat_keystore2_key_contexts 2>/dev/null
        log_msg "keystore2: linked plat_keystore2_key_contexts from installed system"
    fi
    setprop ctl.start vendor.keystore2-sup
    sleep 3
    sup_check keystore2
    log_msg "step:keystore2 handled"
}
"""
_anchor = "spawn_tee_chain() {"
assert _anchor in _setup
_setup = _setup.replace(_anchor, _ks2_fn.strip() + "\n\n" + _anchor, 1)
# call it right after the tee chain runs in the main flow
_call_anchor = "\nspawn_tee_chain\n"
assert _call_anchor in _setup, "tee chain call site not found"
_setup = _setup.replace(_call_anchor, "\nspawn_tee_chain\nspawn_keystore2\n", 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()


# =========================================================================
# v3.15: mount the installed i18n APEX before starting keystore2.
# v3.14 verdict: keystore2 died at load -- the installed libsqlite
# needs ICU symbol ucol_setStrength_android, which lives only in the
# com.android.i18n APEX (unmounted in recovery; the /system/lib64
# libicuuc is a symlink into the APEX, dangling without the mount, so
# the linker fell back to the payload's older ICU). The .apex is a
# plain zip apex (verified live on the tablet); unzip + losetup both
# exist in the ramdisk. Setup runs as root, so the loop mount is
# attempted there, with every step logged.
# =========================================================================
_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_old = """    mkdir -p /tmp/misc/keystore
    if [ ! -e /system/etc/selinux/plat_keystore2_key_contexts ]; then"""
_new = """    mkdir -p /tmp/misc/keystore
    # v3.15: stage the i18n APEX so the installed ICU resolves.
    if [ ! -e /apex/com.android.i18n/lib64/libicuuc.so ]; then
        mkdir -p /apex/com.android.i18n /tmp/apex-i18n
        unzip -o -q /mnt/system/system/apex/com.android.i18n.apex \
            apex_payload.img -d /tmp/apex-i18n 2>/dev/null
        _loop=$(losetup -f 2>/dev/null)
        log_msg "i18n apex: payload=$(ls /tmp/apex-i18n 2>/dev/null) loop=${_loop}"
        if [ -f /tmp/apex-i18n/apex_payload.img ] && [ -n "${_loop}" ]; then
            losetup "${_loop}" /tmp/apex-i18n/apex_payload.img 2>/dev/null
            mount -o ro "${_loop}" /apex/com.android.i18n 2>/dev/null
        fi
        if [ -e /apex/com.android.i18n/lib64/libicuuc.so ]; then
            log_msg "i18n apex: mounted, libicuuc present"
        else
            log_msg "i18n apex: MOUNT FAILED"
        fi
    fi
    if [ ! -e /system/etc/selinux/plat_keystore2_key_contexts ]; then"""
assert _old in _setup, "spawn_keystore2 head not found"
_setup = _setup.replace(_old, _new, 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()


# =========================================================================
# v3.16: liblogcapture v5 -- adds a no-op stub for
# android::BBinder::setTransactionCodeMap (see stage32/liblogcapture.c
# header). v3.15 verdict: the i18n APEX mount worked (libsqlite's ICU
# symbol resolved), but keystore2 then died at load on this C++
# libbinder symbol needed by the installed android.security.aaid_
# aidl-cpp.so. The split binder pair stays untouched (user directive
# 2026-11-16 12:58); the stub only drops debug tracing names.
# =========================================================================
_llc = open(os.path.join(S32, "liblogcapture.so"), "rb").read()
f1_final["system/etc/hybrid/liblogcapture.so"] = {
    "name": "system/etc/hybrid/liblogcapture.so", "mode": 0o100644,
    "body": _llc}


# =========================================================================
# v3.17: mount tracefs before starting keystore2. v3.16 verdict:
# keystore2 now LOADS (BBinder stub worked, CANNOT LINK = 0), starts,
# connects to KeyMint and reads its version (300) -- then a binder
# thread segfaults at addr 0 ~0.5 ms after printing "cutils-trace:
# Error opening trace file: No such file or directory". Recovery has
# no tracing filesystem mounted; give atrace its trace_marker.
# =========================================================================
_setup = f1_final["system/bin/turner-setup.sh"]["body"].decode()
_old = """    setprop ctl.start vendor.keystore2-sup"""
_new = """    # v3.17: atrace needs a tracing fs; keystore2's binder thread
    # died right after failing to open the trace file.
    if [ ! -e /sys/kernel/tracing/trace_marker ]; then
        mkdir -p /sys/kernel/tracing 2>/dev/null
        mount -t tracefs tracefs /sys/kernel/tracing 2>/dev/null
    fi
    if [ ! -e /sys/kernel/tracing/trace_marker ] && [ ! -e /sys/kernel/debug/tracing/trace_marker ]; then
        mkdir -p /sys/kernel/debug 2>/dev/null
        mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null
    fi
    log_msg "keystore2: trace_marker=$(ls /sys/kernel/tracing/trace_marker /sys/kernel/debug/tracing/trace_marker 2>/dev/null | tr '\\n' ' ')"
    setprop ctl.start vendor.keystore2-sup"""
assert _old in _setup, "ks2 start line not found"
_setup = _setup.replace(_old, _new, 1)
f1_final["system/bin/turner-setup.sh"]["body"] = _setup.encode()


# =========================================================================
# v3.18: replace the installed (SDK37) keystore2 with the official
# YARP build's own keystore2 + its missing library closure, run with
# the FULL payload binder pair (SDK36 libbinder + libbinder_ndk, both
# RECO-generation, from twrp16). v3.16/v3.17 verdict: the installed
# keystore2 loads and reaches KeyMint, but a binder pool thread
# segfaults deterministically ~1 ms after the thread pool starts --
# the SDK37 binary on the split binder pair is not viable. The
# official binary is the same generation as every lib it will load.
# Closure computed locally (DT_NEEDED BFS over official-image libs
# minus what our ramdisk already has): 25 libs, ~2.9 MB.
# =========================================================================
import glob as _glob
_bundle_dir = os.path.join(S34, "ks2bundle")
_ks2_bin = open(os.path.join(_bundle_dir, "keystore2"), "rb").read()
f1_final["system/etc/hybrid/ks2"] = {
    "name": "system/etc/hybrid/ks2", "mode": 0o40755, "body": b""}
f1_final["system/etc/hybrid/ks2lib"] = {
    "name": "system/etc/hybrid/ks2lib", "mode": 0o40755, "body": b""}
f1_final["system/etc/hybrid/ks2/keystore2"] = {
    "name": "system/etc/hybrid/ks2/keystore2", "mode": 0o100755,
    "body": _ks2_bin}
for _p in sorted(_glob.glob(os.path.join(_bundle_dir, "*.so"))):
    _n = "system/etc/hybrid/ks2lib/" + os.path.basename(_p)
    f1_final[_n] = {"name": _n, "mode": 0o100644,
                    "body": open(_p, "rb").read()}
for _ln, _tgt in (("libbinder.so", "/system/lib64/twrp16/libbinder.so"),
                  ("libbinder_ndk.so", "/system/lib64/twrp16/libbinder_ndk.so")):
    _n = "system/etc/hybrid/ks2lib/" + _ln
    f1_final[_n] = {"name": _n, "mode": 0o120777, "body": _tgt.encode()}

_sup = f1_final["system/bin/turner-ks2-sup.sh"]["body"].decode()
_old_libs = 'LIBS="/system/etc/hybrid/twrpbinder:/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex/com.android.runtime/lib64:/apex/com.android.i18n/lib64:/system/lib64/twrp16"'
_new_libs = 'LIBS="/system/etc/hybrid/ks2lib:/system/lib64/twrp16:/system/lib64"'
assert _old_libs in _sup, "ks2 LIBS line not found"
_sup = _sup.replace(_old_libs, _new_libs, 1)
_old_bin = "/mnt/system/system/bin/keystore2 /tmp/misc/keystore"
_new_bin = "/system/etc/hybrid/ks2/keystore2 /tmp/misc/keystore"
assert _old_bin in _sup, "ks2 binary line not found"
_sup = _sup.replace(_old_bin, _new_bin, 1)
f1_final["system/bin/turner-ks2-sup.sh"]["body"] = _sup.encode()

f1_entries, f1_cpio, f1_lz4 = pack_f1(f1_final)
headroom_final = BUDGET - (F0_LEN + len(f1_lz4))
assert headroom_final >= MIN_HEADROOM, \
    f"STOP: v2.3 headroom {headroom_final} < {MIN_HEADROOM}"
stage7_info = {
    "rc_sha256": sha(f1_final["system/etc/init/hybrid-services.rc"]["body"]),
    "setup_sha256": sha(f1_final["system/bin/turner-setup.sh"]["body"]),
    "prop_default_sha256": sha(f1_final["prop.default"]["body"]),
    "manifests": {t: sha(f1_final[t]["body"]) for t in stage7_manifests},
    "libkmsglog_sha256": sha(kms), "touch_ko_sha256": sha(ko),
    "stub_sha256": sha(stub), "spawn_touch_sha256": sha(spt),
    "final_f1_lz4": len(f1_lz4), "final_headroom": headroom_final,
}
print(f"stage-7 delta applied: rc+setup swapped, prop baked to 17, "
      f"{len(stage7_manifests)} manifests, hybrid dir +2 files; "
      f"F1 lz4 {len(f1_lz4)} B, headroom {headroom_final} B")
f1 = f1_final

# ------------------------------------------------------------------- F0 reuse
f0_lz4_stock = open(F0_LZ4_REUSE, "rb").read()
assert len(f0_lz4_stock) == 36330472, len(f0_lz4_stock)
f0_entries, f0_trailer = parse_cpio(lz4_legacy_decompress(f0_lz4_stock))
# v3.6: the servicemanager lives in F0. Patch its addService VINTF
# check in place (see the stage-22 note in the delta manifest): at
# file offset 0x9d04, tbz w0,#0,<error exit> (0x360011c0) -> NOP, so
# a failed declaration check falls through to normal registration.
# v3.5 proved even the payload's own health HAL fails that check
# (status -3) although its declaration IS in the recovery manifest;
# the check sees no usable data in this build and is meaningless in
# a ramdisk where every binary is ours. Everything else in F0 stays
# byte-identical.
_smi = [k for k, e in enumerate(f0_entries) if e["name"] == "system/bin/servicemanager"]
assert len(_smi) == 1
_smb = bytearray(f0_entries[_smi[0]]["body"])
assert _smb[0x9d04:0x9d08] == bytes.fromhex("c0110036"), _smb[0x9d04:0x9d08].hex()
_smb[0x9d04:0x9d08] = bytes.fromhex("1f2003d5")
f0_entries[_smi[0]]["body"] = bytes(_smb)
f0_lz4 = lz4_legacy_compress(write_newc(f0_entries, trailer=f0_trailer))

print(f"F0 (stage-3b fragment + servicemanager patch): lz4 {len(f0_lz4)} B, {len(f0_entries)} entries")
print(f"F1: {len(f1_entries)} entries, cpio {len(f1_cpio)} B, lz4 {len(f1_lz4)} B")
print(f"fragments total = {len(f0_lz4) + len(f1_lz4)} B (budget 66563880)")

# ------------------------------------------------- trees + work artifacts
# (written before assembly so a size failure still leaves the full record)
def write_tree(entries, root):
    os.makedirs(root, exist_ok=True)
    dir_modes = []
    for e in entries:
        name = e["name"]
        if name in (".", ""):
            continue
        p = os.path.join(root, name)
        typ = e["mode"] & 0o170000
        if typ == DIR:
            os.makedirs(p, exist_ok=True)
            dir_modes.append((p, e["mode"] & 0o7777))
        elif typ == LINK:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if os.path.lexists(p):
                os.unlink(p)
            os.symlink(e["body"].decode(), p)
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(e["body"])
            os.chmod(p, e["mode"] & 0o7777)
    for p, m in reversed(dir_modes):
        os.chmod(p, m)


os.makedirs(WORK, exist_ok=True)
open(os.path.join(WORK, "f0.lz4"), "wb").write(f0_lz4)
open(os.path.join(WORK, "f1_v318.cpio"), "wb").write(f1_cpio)
open(os.path.join(WORK, "f1_v318.lz4"), "wb").write(f1_lz4)
open(os.path.join(WORK, "appendage.txt"), "w").write(APPENDAGE)
write_tree(f1_entries, os.path.join(OUT_DIR, "f1_v318"))

delta = {
    "added": sorted(added), "changed": sorted(changed),
    "twrp16": {
        "differing": differing, "needed_payonly": needed_payonly,
        "excluded_payonly": unneeded_payonly,
        "sizes": {n: len(resolve(pay_map, n)[0]) for n in twrp16_set},
    },
    "res_additions": [n for n in res_add if n in f1],
    "stage4b": {
        "cuts_applied": cuts_applied,
        "removed_stock": sorted(removed_stock),
        "kept_parent_dirs": KEEP_DIRS,
        "cut2_removed_additions": sorted(cut2_removed_additions),
        "measurements": measurements,
        "fragments_total": len(f0_lz4) + len(f1_lz4),
        "budget": BUDGET,
        "headroom": BUDGET - (len(f0_lz4) + len(f1_lz4)),
    },
    "stage6": stage6_info,
    "stage7": stage7_info,
    "f0_lz4_sha256": sha(f0_lz4), "f1_lz4_sha256": sha(f1_lz4),
    "image_sha256": None,
}
open(os.path.join(WORK, "delta7.json"), "w").write(json.dumps(delta, indent=1))
print("trees + .work artifacts written; delta manifest at .work/delta7.json")

# ------------------------------------------------------------------ assembly
hs, ds = struct.unpack_from("<II", stock, 2096)
_, ec, es, _ = struct.unpack_from("<IIII", stock, 2112)
rs_old = struct.unpack_from("<I", stock, 24)[0]
ro = align(hs)
dtbo = align(ro + rs_old)
tblo = align(dtbo + align(ds))
hdr = bytearray(stock[:PS])
struct.pack_into("<I", hdr, 24, len(f0_lz4) + len(f1_lz4))
dtb_region = stock[dtbo:dtbo + align(ds)]
tbl = bytearray(stock[tblo:tblo + es * ec])
for i, data in enumerate((f0_lz4, f1_lz4)):
    struct.pack_into("<I", tbl, i * es, len(data))
    struct.pack_into("<I", tbl, i * es + 4, sum(len(x) for x in (f0_lz4, f1_lz4)[:i]))
raw = bytearray()
raw += hdr
raw += f0_lz4 + f1_lz4
raw += b"\0" * (align(len(raw)) - len(raw))
raw += dtb_region
raw += tbl
raw = bytes(raw)
print(f"raw image: {len(raw)} B")
if align(len(raw)) + 512 + 64 > PARTITION_SIZE:
    print(f"FATAL: raw {len(raw)} + vbmeta + footer exceeds partition "
          f"{PARTITION_SIZE} — NOT writing an image (G1 size failure).")
    sys.exit(2)

# ------------------------------------------------------------ AVB hash footer
v5_ois, v5_voff, v5_vsz = struct.unpack_from(">QQQ", v5[-64:], 12)
vbmeta = bytearray(v5[v5_voff:v5_voff + v5_vsz])
assert len(vbmeta) == 512 and vbmeta[:4] == b"AVB0"
do, dsz = struct.unpack_from(">QQ", vbmeta, 96)
assert (do, dsz) == (0, 208)
desc_at = 256 + do
salt = os.urandom(32)
digest = hashlib.sha256(salt + raw).digest()
struct.pack_into(">Q", vbmeta, desc_at + 16, len(raw))
vbmeta[desc_at + 143:desc_at + 175] = salt
vbmeta[desc_at + 175:desc_at + 207] = digest
vbmeta_off = align(len(raw))
img = bytearray(b"\0" * PARTITION_SIZE)
img[:len(raw)] = raw
img[vbmeta_off:vbmeta_off + 512] = vbmeta
footer = b"AVBf" + struct.pack(">IIQQQ", 1, 0, len(raw), vbmeta_off, 512) + b"\0" * 28
img[PARTITION_SIZE - 64:] = footer
out_path = os.path.join(OUT_DIR, "turner-vendor_boot-hybrid-v3.18.img")
open(out_path, "wb").write(bytes(img))
delta["image_sha256"] = sha(bytes(img))
open(os.path.join(WORK, "delta7.json"), "w").write(json.dumps(delta, indent=1))
print(f"image: {out_path} {len(img)} B sha256={sha(bytes(img))}")
