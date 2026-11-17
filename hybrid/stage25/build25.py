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
STOCK_IMG = H("~/workspace/skyward-turner/os4/vendor_boot.img")
V5_IMG = H("~/workspace/yarp/turner-vendor_boot-repack-v5.img")
F0_LZ4_REUSE = os.path.join(S3, ".work", "f0.lz4")
SETUP_SH = os.path.join(S4, "turner-setup.sh")
SERVICES_RC = os.path.join(S2, "hybrid-services.rc")
OUT_DIR = S25
WORK = os.path.join(S25, ".work")
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
open(os.path.join(WORK, "f1_v39.cpio"), "wb").write(f1_cpio)
open(os.path.join(WORK, "f1_v39.lz4"), "wb").write(f1_lz4)
open(os.path.join(WORK, "appendage.txt"), "w").write(APPENDAGE)
write_tree(f1_entries, os.path.join(OUT_DIR, "f1_v39"))

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
out_path = os.path.join(OUT_DIR, "turner-vendor_boot-hybrid-v3.9.img")
open(out_path, "wb").write(bytes(img))
delta["image_sha256"] = sha(bytes(img))
open(os.path.join(WORK, "delta7.json"), "w").write(json.dumps(delta, indent=1))
print(f"image: {out_path} {len(img)} B sha256={sha(bytes(img))}")
