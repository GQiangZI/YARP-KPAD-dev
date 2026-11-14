# Stage 1 — Groundwork Report (turner YARP×Skyward hybrid)

Date: 2026-11-14. Workdir: `~/workspace/yarp-hybrid/stage1/`. Nothing under
`~/workspace/yarp/` or `~/workspace/skyward-turner/` was modified (read-only sources).
No boot image was assembled in this stage.

Tooling: `tools/vboot.py` (written for this stage) — vendor_boot v4 header/table
parser, lz4-legacy decompression via ctypes `liblz4.so.1` `LZ4_decompress_safe`
(legacy streams here have no trailing zero block), hand-written newc cpio extractor.

## 1. twrp_payload/ — YARP TWRP userspace payload (the v5iso F1 tree)

**Inventory:** 588 content entries = **378 regular files + 210 symlinks**, in 32
directories; regular-file bytes total **62,676,784**. Extracted F1 cpio size
62,764,544 B; source fragment (lz4 legacy) 28,991,107 B.
Top level is the merged F1 shape: stock skeleton (apex/, config/, linkerconfig/,
first_stage_ramdisk/, sepolicy, prop.default) + TWRP additions (`twres/`, `res/`,
`init`, `init.recovery.{hardware,mt6991,mt8799}.rc`, `system/bin`, `system/lib64`,
`vendor/firmware/`, `vendor/mitee/ta/`, …). No device-node entries occur in the
archive, so no placeholder markers were needed.

**Recovery binary:** `system/bin/recovery` — **3,270,200 B**,
sha256 `af0a3aa8bc8bf7f5aaf937b84d1c9a66934d8b684558e5789d61cc8c97250c8e`.

### Provenance — exact backup members used

The f1_v5 tree was **re-derived from the backups** by replaying the original
build recipe (`repack-v5-build.sh`, from `backup-v5-final-20261111.tar.gz`):

| Input | Backup member |
|---|---|
| f1_v4 fragment | `backup-pre-shutdown-20261110.tar.gz` → `stock/f1_v4.lz4` (sha256 `c84bc8ff…`) |
| stock F1 tree (merge winners, 16 files) | same tar → `stock/s_f1/**` |
| stock F0 tree (merge winners, 7 deleted paths) | same tar → `stock/s_f0/**` |
| recipe + 23 winner SHA prefixes | `backup-v5-final-20261111.tar.gz` → `repack-v5-build.sh` (+ `audit-v5/01-closure.txt`) |

Derivation (driver: `_src/work/derive_f1_v5.py`, kept in `_src/work/`):
f1_v5 = f1_v4 tree, then for each of the 23 init-closure paths: copy the s_f1
stock build over it (16 paths), or delete it because the stock-merge winner
lives only in s_f0 (7 paths: libkeyutils, liblogwrap, libprocessgroup_setup,
libunwindstack, libvendorsupport, libjsoncpp, liblzma). Every winner SHA
matched its audit prefix.

**Verification — all gates passed:**
- f1_v4 → f1_v5 delta is *exactly* the 23 target paths (no more, no less).
- Merged-outcome gate: all 33 init-closure paths merge to the exact stock
  winner in [f0_new + f1_v5].
- **The derived tree is content-identical to the F1 of the shipped v5iso image**
  (`~/workspace/yarp/turner-vendor_boot-repack-v5.img`, sha256 `e16a5a2d…`):
  snapshot comparison of 588 files/symlinks — 0 only-in-either, 0 differing,
  0 mode-only differences. (v5iso reuses f1_v5 byte-for-byte; its only change
  vs v5-fullstock was in F0, so this F1 *is* the v5iso payload.)

**Negative finding:** `stock/v5_x/` inside the pre-shutdown backup is **not**
the v5iso extraction despite the name — its fragments (frag1.lz4 62,044,950 B,
dated Nov 9) match neither the v5iso image nor v5-fullstock; it is a stale
early-build workspace. It was discarded (not used) and removed from `_src`.

## 2. os4_f0/ and os4_f1/ — OS4 stock vendor_boot split

Source: `~/workspace/skyward-turner/os4/vendor_boot.img`, 67,108,864 B,
sha256 `987a06d00de712b2dc14f1959d0cf0559ea2da1a1cb862b9262de85776b326e9` (verified).
Header v4, page 4096, header_size 2128, bootconfig 0, cmdline
`bootopt=64S3,32N2,64N2 erofs.reserved_pages=64`, 2 table entries (108 B each).
Split manifest saved as `os4_manifest.json`; DTB saved as `os4_dtb.bin`.

| Fragment | Type | lz4 size | lz4 sha256 | cpio size | cpio sha256 | Tree |
|---|---|---|---|---|---|---|
| frag0 | 1 PLATFORM | 46,569,104 | `51cfbc8c…` | 95,892,992 | `2b5bd916…` | os4_f0/ |
| frag1 | 2 RECOVERY ("recovery") | 16,551,481 | `2fc235a7…` | 26,022,912 | `c4634eff…` | os4_f1/ |

**os4_f0/:** 989 regular files + 223 symlinks + 45 dirs (1,257 entries),
95,713,880 file bytes.
**os4_f1/:** 645 regular files + 2 symlinks + 20 dirs (667 entries),
25,925,441 file bytes. Same skeleton shape as OS3 stock F1 (apex/, config/,
linkerconfig/, res/, init present).

### Verification

- **DTB: 533,115 B, sha256 `4f985cad82176ea746ffef6aa960269ef0aec410f294bc157bd766ad74f49bc0`**
  — prefix `4f985cad` as required; byte-identical to the known-genuine stock DTB.
- **Cross-check:** `diff -rq` of both trees against the parent project's
  independent OS4 extraction (`~/workspace/skyward-turner/os4/os4_f0|os4_f1`)
  reports **0 differences**. os4_f1's 645-file count also matches the parent
  OS4 audit.
- **prop.default discrepancy (reported plainly):** the task brief expected the
  F1 `prop.default` version string to read `OS4.0.3.0.XAOCNXM`; the actual value
  in the image (and in the parent's extraction) is
  `ro.build.version.incremental=OS4.0.3.0.XAOCN` — the trailing `XM` exists in
  the OTA package *filename*, not in this ramdisk's prop. Also present:
  fingerprint `Redmi/turner/turner:15/AP3A.240905.015.A2/OS4.0.3.0.XAOCN:user/release-keys`,
  `ro.build.version.sdk=35` (vendor side still SDK 35, as the parent audit found).
  The image is the verified-genuine OS4 stock, so `…XAOCN` is the correct string
  to design against for F1 props.

## 3. Gaps / notes for later stages

- Payload modes were preserved; ownership was not (shared-mount restriction) —
  irrelevant for repacking, noted for completeness.
- `_src/` retains the derivation inputs (s_f0/s_f1 trees, f0_new.lz4/f1_v4.lz4,
  the v5-final scripts, `work/f1_v4`) so the payload can be re-derived
  byte-identically at any time; everything in it is re-extractable from the two
  backup tarballs listed above.
- Stage 2 inputs now ready: `twrp_payload/` (TWRP face), `os4_f0/` + `os4_f1/`
  (OS4 base + skeleton reference), `os4_dtb.bin`, `os4_manifest.json`.
