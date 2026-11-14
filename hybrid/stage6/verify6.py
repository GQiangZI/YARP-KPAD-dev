#!/usr/bin/env python3
"""Stage-6 gates on the FINAL v2.2 image (= verify4b adapted:
G1/G2/G4/G5 as v2.1, G2 gains the v2.1-vs-v2.2 F1 comparison and the
libtwrpminui patch checks, plus a new G6-PATCH section):
G1 size/header/cmdline/DTB vs OS4 stock + headroom;
G2-STRICT updated (F1 delta vs os4_f1 = stage-4 enumerated set + CUT-1);
G4 AVB footer digest. G5 script/rc semantics on the f1_v21 tree.
G3 is audit4b.py. Read-only verification.
"""
import hashlib, json, os, struct, subprocess, sys

sys.path.insert(0, os.path.expanduser("~/workspace/yarp-hybrid/stage3"))
from packlib import parse_cpio, lz4_legacy_decompress

H = os.path.expanduser
S1 = H("~/workspace/yarp-hybrid/stage1")
S2 = H("~/workspace/yarp-hybrid/stage2")
S3 = H("~/workspace/yarp-hybrid/stage3")
S4 = H("~/workspace/yarp-hybrid/stage4")
S6 = H("~/workspace/yarp-hybrid/stage6")
WORK = os.path.join(S6, ".work")
IMG_PATH = os.path.join(S6, "turner-vendor_boot-hybrid-v2.2.img")
BUDGET = 66563880
MIN_HEADROOM = 200000
FAILS = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def align(v, a=4096):
    return (v + a - 1) // a * a


def parse(img):
    hs, ds = struct.unpack_from("<II", img, 2096)
    _, ec, es, bc = struct.unpack_from("<IIII", img, 2112)
    rs = struct.unpack_from("<I", img, 24)[0]
    ro = align(hs)
    dtbo = align(ro + rs)
    tblo = align(dtbo + align(ds))
    frags = []
    for i in range(ec):
        size, off, typ = struct.unpack_from("<III", img, tblo + i * es)
        frags.append((size, off, img[ro + off: ro + off + size]))
    return {"header_size": hs, "dtb_size": ds, "entry_num": ec,
            "entry_size": es, "bootconfig": bc, "ramdisk_size": rs,
            "dtb": img[dtbo:dtbo + ds], "frags": frags}


IMG = open(IMG_PATH, "rb").read()
STOCK = open(H("~/workspace/skyward-turner/os4/vendor_boot.img"), "rb").read()
V5 = open(H("~/workspace/yarp/turner-vendor_boot-repack-v5.img"), "rb").read()
fi, fs = parse(IMG), parse(STOCK)
delta = json.load(open(os.path.join(WORK, "delta6.json")))
sf0 = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(fs["frags"][0][2]))[0]}
sf1 = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(fs["frags"][1][2]))[0]}
pf1 = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(parse(V5)["frags"][1][2]))[0]}

print("=" * 78)
print("G1 — size / header / cmdline / DTB vs OS4 stock")
check("image size == 67,108,864 B (partition)", len(IMG) == 67108864, f"{len(IMG)}")
check("magic VNDRBOOT", IMG[:8] == b"VNDRBOOT")
hv_i, hv_s = struct.unpack_from("<I", IMG, 8)[0], struct.unpack_from("<I", STOCK, 8)[0]
check("header_version == stock (4)", hv_i == hv_s == 4, f"{hv_i}")
ps_i, ps_s = struct.unpack_from("<I", IMG, 12)[0], struct.unpack_from("<I", STOCK, 12)[0]
check("page_size == stock (4096)", ps_i == ps_s == 4096, f"{ps_i}")
check("header_size == stock", fi["header_size"] == fs["header_size"],
      f"{fi['header_size']} vs {fs['header_size']}")
check("cmdline bytes == stock", IMG[28:28 + 2048] == STOCK[28:28 + 2048])
check("name field == stock", IMG[2080:2096] == STOCK[2080:2096],
      f"{IMG[2080:2096]!r}")
check("dtb_size == stock", fi["dtb_size"] == fs["dtb_size"], f"{fi['dtb_size']}")
check("DTB bytes == stock DTB", fi["dtb"] == fs["dtb"], f"sha={sha(fi['dtb'])[:16]}")
check("entry_num == 2, entry_size == stock", fi["entry_num"] == 2
      and fi["entry_size"] == fs["entry_size"])
check("bootconfig_size == stock (0)", fi["bootconfig"] == fs["bootconfig"] == 0)
frag_sizes = [f[0] for f in fi["frags"]]
check("header ramdisk_size == sum of fragment sizes",
      fi["ramdisk_size"] == sum(frag_sizes), f"{fi['ramdisk_size']} vs {sum(frag_sizes)}")
total = sum(frag_sizes)
headroom = BUDGET - total
check("fragments within budget, headroom >= 200,000 B",
      total <= BUDGET and headroom >= MIN_HEADROOM,
      f"total={total} budget={BUDGET} headroom={headroom}")
check("headroom == delta6 stage6.final_headroom record",
      headroom == delta["stage6"]["final_headroom"],
      f"{delta['stage6']['final_headroom']}")

print("=" * 78)
print("G2-STRICT — F0 fragment (reused stage-3b, from final image)")
f0b = open(os.path.join(S3, ".work", "f0.lz4"), "rb").read()
check("image F0 fragment bytes == stage3 .work/f0.lz4", fi["frags"][0][2] == f0b,
      f"sha={sha(fi['frags'][0][2])}")
hy0 = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(fi["frags"][0][2]))[0]}
added0 = sorted(set(hy0) - set(sf0))
removed0 = sorted(set(sf0) - set(hy0))
changed0 = sorted(n for n in set(hy0) & set(sf0)
                  if hy0[n]["body"] != sf0[n]["body"] or hy0[n]["mode"] != sf0[n]["mode"])
is_cut = lambda n: n == "res" or n.startswith("res/") or n == "system/bin/recovery"
check("F0 added == 11 twrp16 entries",
      added0 == sorted(n for n in hy0 if n.startswith("system/lib64/twrp16"))
      and len(added0) == 11, f"{len(added0)}")
check("F0 removed == res/ tree + system/bin/recovery",
      removed0 == sorted(n for n in sf0 if is_cut(n)), f"{len(removed0)}")
check("F0 changed == hw/init.rc only", changed0 == ["system/etc/init/hw/init.rc"],
      f"{changed0}")
a = sf0["system/etc/init/hw/init.rc"]["body"].decode().split("\n")
b = hy0["system/etc/init/hw/init.rc"]["body"].decode().split("\n")
check("init.rc change == +1 setenv line",
      len(b) == len(a) + 1 and
      b == a[:98] + ["    setenv LD_LIBRARY_PATH /system/lib64/twrp16:/system/lib64"] + a[98:])

print("=" * 78)
print("G2-STRICT — F1 (from final image) vs OS4 stock F1 + CUT-1")
check("image F1 fragment == .work/f1_v22.lz4",
      fi["frags"][1][2] == open(os.path.join(WORK, "f1_v22.lz4"), "rb").read(),
      f"sha={sha(fi['frags'][1][2])}")
hy1 = {e["name"]: e for e in parse_cpio(lz4_legacy_decompress(fi["frags"][1][2]))[0]}
added1 = sorted(set(hy1) - set(sf1))
removed1 = sorted(set(sf1) - set(hy1))
changed1 = sorted(n for n in set(hy1) & set(sf1)
                  if hy1[n]["body"] != sf1[n]["body"] or hy1[n]["mode"] != sf1[n]["mode"])
exp_added = sorted(delta["added"])
check("F1 added == stage-4 enumerated set exactly (CUT-2 not applied)",
      added1 == exp_added, f"{len(added1)} entries (expected {len(exp_added)})")
if added1 != exp_added:
    print(f"    extra: {sorted(set(added1) - set(exp_added))}")
    print(f"    missing: {sorted(set(exp_added) - set(added1))}")
exp_removed = sorted(delta["stage4b"]["removed_stock"])
check("F1 removed == CUT-1 set exactly", removed1 == exp_removed,
      f"{len(removed1)} entries (expected {len(exp_removed)})")
if removed1 != exp_removed:
    print(f"    extra: {sorted(set(removed1) - set(exp_removed))[:10]}")
    print(f"    missing: {sorted(set(exp_removed) - set(removed1))[:10]}")
check("kept parent dirs res + res/images present, stock bodies/modes",
      all(n in hy1 and hy1[n]["body"] == sf1[n]["body"]
          and hy1[n]["mode"] == sf1[n]["mode"] for n in ("res", "res/images")))
check("no other stock res/ entry survives",
      [n for n in sf1 if (n == "res" or n.startswith("res/")) and n in hy1]
      == ["res", "res/images"])
check("F1 changed == {recovery.fstab, init.recovery.mt8799.rc}",
      changed1 == ["init.recovery.mt8799.rc", "system/etc/recovery.fstab"],
      f"{changed1}")
check("recovery binary sha == TWRP payload af0a3aa8...",
      sha(hy1["system/bin/recovery"]["body"]) ==
      "af0a3aa8bc8bf7f5aaf937b84d1c9a66934d8b684558e5789d61cc8c97250c8e",
      f"mode={oct(hy1['system/bin/recovery']['mode'])}")
check("recovery.fstab == payload version",
      hy1["system/etc/recovery.fstab"]["body"] == pf1["system/etc/recovery.fstab"]["body"]
      and hy1["system/etc/recovery.fstab"]["mode"] == sf1["system/etc/recovery.fstab"]["mode"])
lib_changes = [n for n in changed1 if n.startswith("system/lib64/")]
check("zero shared-path system/lib64 changes", lib_changes == [], f"{lib_changes}")
tw = sorted(n for n in added1 if n.startswith("system/lib64/twrp16/"))
check("twrp16 additions == 74 libs (untouched by cuts)", len(tw) == 74, f"{len(tw)}")
bad = [n for n in tw
       if n.rsplit("/", 1)[-1] != "libtwrpminui.so"
       and hy1["system/lib64/twrp16/" + n.rsplit("/", 1)[-1]]["body"]
       != pf1["system/lib64/" + n.rsplit("/", 1)[-1]]["body"]]
check("every twrp16 lib body == payload bytes (except patched libtwrpminui)",
      bad == [], f"{bad}")
MINUI = "system/lib64/twrp16/libtwrpminui.so"
patched_deliv = open(os.path.join(S6, "libtwrpminui.so.patched"), "rb").read()
orig_deliv = open(os.path.join(S6, "libtwrpminui.so.orig"), "rb").read()
check("in-image libtwrpminui.so == stage6 patched deliverable (sha 71aee254...)",
      hy1[MINUI]["body"] == patched_deliv
      and sha(hy1[MINUI]["body"]) ==
      "71aee2540c4995920fe520cdb0cd4c3b4d694462686638eaf6a1c6884e3a1939",
      f"sha={sha(hy1[MINUI]['body'])[:16]}")
EXP_BYTE_DIFF = {0x1C3D4: (0x48, 0x28), 0x1C3F8: (0xE8, 0x28),
                 0x1C3F9: (0x17, 0x00), 0x1C3FA: (0x9F, 0x80),
                 0x1C3FB: (0x1A, 0x52)}
got_diff = {i: (orig_deliv[i], patched_deliv[i]) for i in range(len(orig_deliv))
            if orig_deliv[i] != patched_deliv[i]}
check("lib byte diff == documented 5 patch bytes only",
      got_diff == EXP_BYTE_DIFF,
      "; ".join(f"{k:#x}:{v[0]:#04x}->{v[1]:#04x}" for k, v in sorted(got_diff.items())))
fw = sorted(n for n in added1 if n.startswith("vendor/firmware/")
            and (hy1[n]["mode"] & 0o170000) == 0o100000)
exp_fw = sorted(n for n in pf1 if n.startswith("vendor/firmware/")
                and (pf1[n]["mode"] & 0o170000) == 0o100000)
check("vendor/firmware files == payload set exactly (46 files, bodies incl.)",
      fw == exp_fw and all(hy1[n]["body"] == pf1[n]["body"] for n in fw),
      f"{len(fw)} files (VERIFY.md §3 said 45 — its own §2 implies 46; "
      f"payload ground truth is 46)")
app = open(os.path.join(WORK, "appendage.txt"), "rb").read()
new_rc = hy1["init.recovery.mt8799.rc"]["body"]
check("mt8799 rc == stock body + appendage (append-only)",
      new_rc == sf1["init.recovery.mt8799.rc"]["body"] + app
      and hy1["init.recovery.mt8799.rc"]["mode"] == sf1["init.recovery.mt8799.rc"]["mode"])
for token in (b"HYBRID-BREADCRUMB:early-init", b"HYBRID-BREADCRUMB:init",
              b"HYBRID-BREADCRUMB:late-init", b"HYBRID-BREADCRUMB:boot",
              b"HYBRID-BREADCRUMB:late_boot", b"setprop sys.usb.config adb",
              b"mkdir /data/vendor 0771 system system",
              b"mkdir /data/vendor/bsplog/touch 0775 system system",
              b"setprop vendor.teefs_state ready",
              b"exec u:r:update_engine:s0 root root -- /system/bin/mtk_plpath_utils"):
    check(f"mt8799 rc contains {token[:44]!r}", token in new_rc)

print("=" * 78)
print("G2-STRICT — F1 (from final image) vs stage-4 v2.1 F1: delta == patch only")
v21 = {e["name"]: e for e in parse_cpio(
    open(os.path.join(S4, ".work", "f1_v21.cpio"), "rb").read())[0]}
a22 = sorted(set(hy1) - set(v21))
r22 = sorted(set(v21) - set(hy1))
c22 = sorted(n for n in set(hy1) & set(v21)
             if hy1[n]["body"] != v21[n]["body"] or hy1[n]["mode"] != v21[n]["mode"])
check("vs v2.1 F1: added == none", a22 == [], f"{a22}")
check("vs v2.1 F1: removed == none", r22 == [], f"{r22}")
check("vs v2.1 F1: changed == {twrp16/libtwrpminui.so} exactly",
      c22 == [MINUI], f"{c22}")

print("=" * 78)
print("G4 — AVB footer")
foot = IMG[-64:]
check("footer magic AVBf", foot[:4] == b"AVBf", f"{foot[:4]}")
ver, flags, ois, voff, vsz = struct.unpack_from(">IIQQQ", foot, 4)
print(f"  footer: version={ver}.0 orig_size={ois} vbmeta_off={voff} vbmeta_size={vsz}")
check("footer vbmeta inside file", voff + vsz <= len(IMG) and IMG[voff:voff + 4] == b"AVB0")
vb = IMG[voff:voff + vsz]
algo, = struct.unpack_from(">I", vb, 28)
check("algorithm == NONE (0)", algo == 0, f"algo={algo}")
do, dsz = struct.unpack_from(">QQ", vb, 96)
d = vb[256 + do:256 + do + dsz]
isz, = struct.unpack_from(">Q", d, 16)
pnl, sl, dl = struct.unpack_from(">III", d, 56)
salt = d[132 + pnl:132 + pnl + sl]
digest = d[132 + pnl + sl:132 + pnl + sl + dl]
print(f"  descriptor: image_size={isz} partition_name_len={pnl} salt_len={sl} digest_len={dl}")
check("descriptor image_size == footer original_image_size", isz == ois)
check("vbmeta digest verifies: sha256(salt || image[:orig_size])",
      hashlib.sha256(salt + IMG[:ois]).digest() == digest)

print("=" * 78)
print("G5 — script / rc semantics (f1_v22 tree)")
for p in (os.path.join(S4, "turner-setup.sh"),
          os.path.join(S6, "f1_v22/system/bin/turner-setup.sh")):
    r = subprocess.run(["sh", "-n", p], capture_output=True, text=True)
    check(f"sh -n {p.replace(H('~'), '~')}", r.returncode == 0, r.stderr.strip())
sh_f1 = open(os.path.join(S6, "f1_v22/system/bin/turner-setup.sh"), "rb").read()
check("F1 turner-setup.sh == stage-4 patched source",
      sh_f1 == open(os.path.join(S4, "turner-setup.sh"), "rb").read())
rc_f1 = open(os.path.join(S6, "f1_v22/system/etc/init/hybrid-services.rc"), "rb").read()
check("F1 hybrid-services.rc == stage-2 source verbatim",
      rc_f1 == open(os.path.join(S2, "hybrid-services.rc"), "rb").read(),
      f"sha={sha(rc_f1)}")
txt = sh_f1.decode()
check("setup script kmsg tag is TURNER-SETUP", "LOG_TAG=TURNER-SETUP" in txt)
check("setup script has 2 bounded TIMEOUT logs", txt.count("TIMEOUT") >= 2,
      f"count={txt.count('TIMEOUT')}")
check("setup script polls bounded (10s device wait, 30x1s service wait)",
      '"${i}" -lt 10' in txt and '"${i}" -lt 30' in txt)
check("setup script service starts are ctl.start (async)",
      'setprop ctl.start "$1"' in txt and "ctl.restart" not in txt)
check("setup script step breadcrumbs present", txt.count("step:") >= 8,
      f"count={txt.count('step:')}")
rcs = []
for root, _, files in os.walk(os.path.join(S6, "f1_v22")):
    for f in files:
        if f.endswith(".rc"):
            p = os.path.join(root, f)
            rcs.append((p, open(p, "rb").read().decode("utf-8", "replace")))
mentions = [(p, t) for p, t in rcs if "turner-setup" in t]
check("only hybrid-services.rc references turner-setup",
      len(mentions) == 1 and mentions[0][0].endswith("hybrid-services.rc"),
      f"{[os.path.basename(p) for p, _ in mentions]}")
hs = mentions[0][1] if mentions else ""
check("turner-setup started via non-blocking `start`, never exec",
      "start turner-setup" in hs and "exec" not in
      "\n".join(ln for ln in hs.split("\n") if "turner-setup" in ln))
check("hybrid services are disabled (no class_start race)",
      hs.count("disabled") >= 5, f"disabled count={hs.count('disabled')}")

print("=" * 78)
print("G6-PATCH — libtwrpminui.so force-legacy patch evidence")
check("orig lib size/sha (268,768 B, 06158204...)",
      len(orig_deliv) == 268768 and sha(orig_deliv) ==
      "0615820440c694fe840eb9ad58dcd7dcd22818dde5f0efa78434e414c1d7d269",
      f"{len(orig_deliv)} B sha={sha(orig_deliv)[:16]}")
check("patched lib size unchanged + sha 71aee254...",
      len(patched_deliv) == len(orig_deliv)
      and sha(patched_deliv) ==
      "71aee2540c4995920fe520cdb0cd4c3b4d694462686638eaf6a1c6884e3a1939")
for f, lbl in ((os.path.join(S6, "libtwrpminui.so.orig"), "orig"),
               (os.path.join(S6, "libtwrpminui.so.patched"), "patched")):
    r = subprocess.run(["readelf", "-h", f], capture_output=True, text=True)
    check(f"readelf parses {lbl} lib as valid ELF", r.returncode == 0
          and "AArch64" in r.stdout)
def needed(f):
    r = subprocess.run(["readelf", "-d", f], capture_output=True, text=True)
    return [ln.split("[")[1].split("]")[0] for ln in r.stdout.splitlines()
            if "NEEDED" in ln]
check("DT_NEEDED identical orig vs patched",
      needed(os.path.join(S6, "libtwrpminui.so.orig"))
      == needed(os.path.join(S6, "libtwrpminui.so.patched")),
      f"{len(needed(os.path.join(S6, 'libtwrpminui.so.patched')))} entries")
VPY = os.path.join(WORK, "venv", "bin", "python")
ADIS = os.path.join(WORK, "adis.py")
def init_asm(f):
    r = subprocess.run([VPY, ADIS, f, "init"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()
asm_o, asm_p = init_asm(os.path.join(S6, "libtwrpminui.so.orig")), \
    init_asm(os.path.join(S6, "libtwrpminui.so.patched"))
diff_lines = [(a, b) for a, b in zip(asm_o, asm_p) if a != b]
check("Init() disassembly diff == exactly the 2 patched instructions",
      len(asm_o) == len(asm_p) and len(diff_lines) == 2,
      f"{len(diff_lines)} changed lines")
check("patched @0x1c3d4: cbz x8 -> #0x1c3f8 (NULL-name path joins force-1)",
      any(ln.startswith("0x0001c3d4:") and "cbz" in ln and "#0x1c3f8" in ln
          for ln in asm_p))
check("patched @0x1c3f8: mov w8, #1 (strcmp result discarded)",
      any(ln.startswith("0x0001c3f8:") and "mov" in ln and "w8, #1" in ln
          for ln in asm_p))
check("downstream gate intact @0x1c930/34: ldrb + tbnz skips Initdisplay",
      any(ln.startswith("0x0001c930:") and "ldrb" in ln and "#0x352" in ln
          for ln in asm_p)
      and any(ln.startswith("0x0001c934:") and "tbnz" in ln for ln in asm_p)
      and any(ln.startswith("0x0001c940:") and "Initdisplay" in ln
              for ln in asm_p))

print("=" * 78)
print("image sha256:", sha(IMG))
print("RESULT:", "ALL PASS" if not FAILS else f"FAILURES: {FAILS}")
sys.exit(1 if FAILS else 0)
