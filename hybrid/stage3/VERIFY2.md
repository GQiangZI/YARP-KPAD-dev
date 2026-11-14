# Stage 3b — Hybrid vendor_boot re-assembly (with the two approved F0 cuts)

## ✅ VERDICT: VALID IMAGE — all gates pass

`turner-vendor_boot-hybrid-v1.img` is a complete, structurally valid
67,108,864-byte vendor_boot image containing the full hybrid merge.

**Supersession:** this image replaces the stage-3 truncated artifact whose
sha256 was `ef0b0764cdb513338e441f0b717a53fb32d29fbd4b651422d0f0238635bab299`.
That file has been renamed to
`turner-vendor_boot-hybrid-v1-TRUNCATED-DO-NOT-FLASH.img` and remains
**INVALID — never flash it**. The new valid image is:

- file: `turner-vendor_boot-hybrid-v1.img`, 67,108,864 B
- **sha256 = `eb55c81b4c217548b3c8635bc195877cc9c88121162e0766f2e97c8249d348f9`**

## What changed vs stage 3

Exactly one change, the two user-approved cuts from
`~/workspace/yarp-hybrid/f0trim/TRIM-ANALYSIS.md`, applied to the OS4 stock
F0 base before adding twrp16 + the setenv line:

- **(a) the entire `res/` tree deleted** (the stock-recovery UI image set;
  no F0 rc/fstab references it — its only consumer is the stock recovery
  userspace the hybrid replaces).
- **(b) `system/bin/recovery` deleted** (the platform-fragment copy; in
  this split-fragment layout recovery mode switch_roots into F1 and runs
  F1's recovery service — the same assumption the v5 recipe ran on).

F1 was **not** rebuilt: the verified stage-3 F1 fragment is reused
byte-for-byte (lz4 sha256
`79810914642d167ac77601e8e08e816fa4394e1e96f0f6b3d14c1a99ef473bbd`), and the
stage-3 `f1_new/` tree is untouched.

## Size ledger (lz4-legacy fragment bytes)

| image | F0 fragment | F1 fragment | fragments total |
|---|---|---|---|
| OS4 stock | 46,569,104 | 16,551,481 | 63,120,585 |
| hybrid stage 3 (no cuts) | 48,645,977 | 29,187,415 | 77,833,392 (**overflow 11,272,408**) |
| **hybrid stage 3b (this build)** | **36,330,472** | **29,187,415** | **65,517,887** |

- Fixed overhead (header page 4096 + DTB region 536,576 + table 216) = 540,888 B.
- Max raw image size = 67,104,768 B → fragment budget = 66,563,880 B.
- **Headroom vs budget: 1,045,993 B (~1.0 MB).**
- Raw image (header + fragments + DTB + table) = 66,060,504 B; vbmeta at
  66,064,384 (512 B); AVB footer at 67,108,800.
- F0 compressed saving vs stage 3: 12,315,505 B (TRIM-ANALYSIS predicted
  12,315,675 B measured on stock F0; Δ170 B is the lz4 block-boundary noise
  the analysis itself flagged). Removed raw content: 14,701,045 B —
  byte-exactly the figure TRIM-ANALYSIS measured for the two cuts.

## Gate results (verify2.py + audit3.py, run on the final image)

### G1 — image structure: **PASS**
- File size exactly 67,108,864 B (genuine construction, no truncation).
- header_version 4, page_size 4096, header_size 2128, dtb_size 533,115 —
  all match OS4 stock; cmdline byte-identical to stock; bootconfig_size 0.
- Header ramdisk_size 65,517,887 = sum of fragment sizes; fragment table
  (2 × 108 B) at offset 66,060,288, fully inside the file; all fragments
  within the ramdisk region.
- DTB bytes identical to `stage1/os4_dtb.bin` (533,115 B); the whole padded
  DTB region is byte-identical to stock's.

### G2 — content diffs (final image unpacked): **PASS**
F0 vs OS4 stock F0 (1,257 stock entries → 689):
- Added: exactly the 11 twrp16 entries, nothing else:
  - `system/lib64/twrp16/` (dir, 0755)
  - `libbase.so` 219,784 B, `libbootloader_message.so` 152,264 B,
    `libc++.so` 1,049,704 B, `libcrypto.so` 1,513,712 B (TWRP build,
    sha256 `e2e4effefa6adb0fa2a016087061d2982157bf856c48a32d55c64e7ebdf104da`),
    `libcutils.so` 118,416 B, `libfs_mgr.so` 632,280 B, `liblog.so` 102,096 B,
    `liblp.so` 202,200 B, `libprotobuf-cpp-lite.so` 579,816 B,
    `libutils.so` 134,776 B — all mode 0644, same bytes as stage 3.
- Removed: exactly 579 entries — the `res/` tree (578 entries) and
  `system/bin/recovery` (3,386,360 B). Nothing else.
- Changed: exactly 1 file, `system/etc/init/hw/init.rc`, exactly +1 line,
  inserted after `user root` in the `service recovery` block:
  `    setenv LD_LIBRARY_PATH /system/lib64/twrp16:/system/lib64`
- Unexplained diffs: 0.

F1 vs the stage-3 verified F1: **0 diffs** across all 625 entries (names,
modes, uid/gid/nlink/mtime, bodies); the fragment bytes in the final image
are identical to the stage-3 fragment. The stage-3 G2 findings therefore
carry over unchanged (4 additions, 4 OS4 policy/context swaps, the fallback
touch module `nt36536e_touch_turner.ko` sha256
`151619c748fb836268ab5c652eff92457b15493fe0a617358d75ac40bdecfa5f`).

### G3 — symbol audits (v5iso methodology): **PASS**
- Init closure: 33 files in hybrid, v5iso and OS3-stock worlds; no missing
  DT_NEEDED; every hybrid closure file byte-identical to its v5iso winner
  (0 content diffs, no new shadowing); unresolved-symbol sets identical to
  v5iso (5, all pre-existing in pure OS3 stock).
- hwservicemanager closure: 22 files, byte-identical resolution to v5iso,
  unresolved sets identical (15). `libvintf.so` has exactly **3 unresolved
  GLOBAL `android::base::Join` instantiations — the identical symbol set to
  the v5iso baseline** (set × const-ref, set × ref, vector × ref), no more,
  no new.

### G4 — AVB hash footer: **PASS**
- Footer present (`AVBf`, v1.0): original_image_size 66,060,504,
  vbmeta_offset 66,064,384, vbmeta_size 512 — all inside the file.
- vbmeta: algorithm **NONE** (0), stock/v5iso-style avbtool construction
  (single hash descriptor, partition `vendor_boot`, fresh salt).
- Descriptor image_size == footer original_image_size; digest verifies:
  SHA-256(salt ‖ image[:66,060,504]) matches the stored digest.

### G5 — rc / script validity: **PASS**
- `sh -n` clean on stage-2 `turner-setup.sh` and on the copy inside F1.
- `hybrid-services.rc` inside F1 is byte-identical to the stage-2 source
  (sha256 `68637bf8da909bd0c85c22ce2cf3c88690af3083195ef296e928eac311a65495`):
  5 service blocks + 3 `on boot` triggers, 5 toml-verbatim
  `setenv LD_LIBRARY_PATH` isolation lines, no `vndservicemanager` service
  anywhere (comments only, per DESIGN).

## Residual risks carried from earlier stages (unchanged, for the record)

- TRIM-ANALYSIS risk 2: removing F0's `system/bin/recovery` assumes the
  split-fragment switch_root path — first flash should watch for any
  platform-recovery fallback exec.
- Headroom is ~1.0 MB; any future F1 growth eats it.

## Deliverables in stage3/
- `turner-vendor_boot-hybrid-v1.img` — **the valid hybrid image** (sha256 above).
- `turner-vendor_boot-hybrid-v1-TRUNCATED-DO-NOT-FLASH.img` — the stage-3
  truncated artifact (sha256 `ef0b0764…`), kept only as the failing record.
- `VERIFY2.md` — this file. (`VERIFY.md` remains the stage-3 record.)
- `f0_new/` — updated tree reflecting the cuts (no `res/`, no
  `system/bin/recovery`); `f1_new/` — untouched stage-3 tree.
- `build2.py`, `verify2.py` — stage-3b construction + gates; `build.py`,
  `verify.py`, `audit3.py`, `packlib.py` — stage-3 tooling (audit3.py is
  shared). `.work/` holds the new fragment archives plus the stage-3
  backups (`f0_stage3.*`, `f1_stage3.*`).
