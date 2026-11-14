# Stage 3 — Hybrid vendor_boot assembly: verification report

## ⚠️ VERDICT: DO NOT FLASH — the hybrid does not fit the 64 MiB partition

The merge itself is **correct and fully verified at content level** (G2, G3, G5
pass exactly as designed). But the assembled content is **11,272,408 bytes
(~10.8 MiB) larger than the vendor_boot partition can hold**, so no valid
67,108,864-byte image containing all of it exists. The file
`turner-vendor_boot-hybrid-v1.img` in this directory is the direct output of
the specified construction and is **INVALID**: it was truncated at the
partition size during assembly (the tail of the F1 fragment, the DTB region,
the fragment table and the vbmeta are missing; the last 64 bytes are the AVB
footer struct overwriting F1 data). It is left in place as the failing
artifact, per the stop rule. **Do not flash it.**

Root cause, in one line: the OS4 stock F0 ramdisk grew ~11.75 MB (compressed)
over the OS3 F0 that the v5iso payload F1 was sized against, and
F0 (OS4 stock + twrp16) + F1 (payload + additions) now exceeds the fixed
64 MiB vendor_boot partition.

## Size ledger (lz4-legacy fragment bytes)

| image | F0 fragment | F1 fragment | fragments total |
|---|---|---|---|
| OS4 stock | 46,569,104 | 16,551,481 | 63,120,585 |
| v5iso (OS3-based) | 34,815,121 | 28,991,107 | 63,806,228 |
| **hybrid (as built)** | **48,645,977** | **29,187,415** | **77,833,392** |

- Fixed overhead (header page 4096 + DTB region 536,576 + table 216) = 540,888 B.
- Max raw image size (vbmeta 512 + footer 64 must still fit) = 67,104,768 B →
  fragment budget = 66,563,880 B.
- Hybrid raw would be 78,377,176 B → **overflow 11,272,408 B**.
- Fragments are already at maximum compression effort (lz4 HC level 12,
  the parameters that reproduce stock/v5iso fragments byte-identically);
  no packing parameter closes an 11 MB gap. Even deleting all of twrp16
  (+2,076,873 B over stock F0) would not come close.

## Gate results

### G1 — image structure: **FAIL**
- File size is nominally 67,108,864 B, but only because assembly truncated
  the oversized raw image at the partition size.
- Header fields that are present do match OS4 stock: header_version 4,
  page_size 4096, header_size 2128, dtb_size 533,115, cmdline byte-identical,
  bootconfig_size 0.
- The header's ramdisk_size field declares 77,833,392 B; the DTB region
  (would start at offset 77,840,384) and the fragment table lie beyond EOF.
  DTB identity check therefore fails (region absent).

### G2 — tree diffs of the merged fragments: **PASS** (content level)
Run on the built fragment archives (`.work/f0.cpio`, `.work/f1.cpio`);
an image-level unpack is impossible because the image is truncated.

F0 vs OS4 stock F0 (1,257 stock entries → 1,268):
- Added: exactly the 11 twrp16 entries, nothing else:
  - `system/lib64/twrp16/` (dir, 0755)
  - `libbase.so` 219,784 B, `libbootloader_message.so` 152,264 B,
    `libc++.so` 1,049,704 B, `libcrypto.so` 1,513,712 B (TWRP build,
    sha256 `e2e4effefa6adb0fa2a016087061d2982157bf856c48a32d55c64e7ebdf104da`),
    `libcutils.so` 118,416 B, `libfs_mgr.so` 632,280 B, `liblog.so` 102,096 B,
    `liblp.so` 202,200 B, `libprotobuf-cpp-lite.so` 579,816 B,
    `libutils.so` 134,776 B — all mode 0644, bytes taken from the v5 F0 archive
    (libcrypto from the stage-1 TWRP build tree).
- Removed: 0.
- Changed: exactly 1 file, `system/etc/init/hw/init.rc`, exactly +1 line,
  inserted after `user root` in the `service recovery` block:
  `    setenv LD_LIBRARY_PATH /system/lib64/twrp16:/system/lib64`
  (line text and position taken verbatim from the v5 F0 archive).

F1 vs (v5iso payload + intended changes):
- Added: exactly 4 entries — `system/etc/hybrid/` (dir, 0755),
  `system/etc/hybrid/nt36536e_touch_turner.ko` (0644, 1,026,728 B),
  `system/bin/turner-setup.sh` (0755, 10,870 B),
  `system/etc/init/hybrid-services.rc` (0644, 6,580 B).
- Removed: 0. Metadata changes on inherited entries: 0.
- Content-changed: exactly the 4 DESIGN §3(a) swaps, each byte-identical to
  the OS4 F1 version: `sepolicy` 1,475,619 → 1,477,869 B,
  `vendor_file_contexts` 141,068 → 142,537 B,
  `vendor_property_contexts` 79,206 → 79,900 B,
  `vendor_service_contexts` 18,794 → 18,916 B.
  (Pre-assembly check (a): these 4 were the only material sepolicy/context
  differences; all plat/product/system_ext/odm contexts were already
  identical. Payload copies equaled OS3 stock in every differing case, i.e.
  none was an intentional TWRP change, so the OS4 versions were adopted.
  Check (b): os4_f1 has 478 files the payload lacks, zero of them
  TEE/touch-relevant — nothing else to merge.)
- Unexplained diffs: 0.

Fallback touch module (DESIGN §2.3), extracted from OS4 `vendor_dlkm.img`
(`/lib/modules/nt36536e_touch_turner.ko`, EROFS reader + dump.erofs 1.7.1):
- size 1,026,728 B (exact inode size), ELF64 AArch64 ET_REL, no raw-stored
  clusters during extraction.
- **sha256 = `151619c748fb836268ab5c652eff92457b15493fe0a617358d75ac40bdecfa5f`**
- vermagic `6.6.118-android15-8-g54a15cf3acba-4k SMP preempt mod_unload
  modversions aarch64`; contains "Novatek Touchscreen Driver" — the genuine
  OS4-generation module.

### G3 — symbol audits (v5iso methodology): **PASS**
Worlds compared as overlays (later fragment wins): hybrid (f0_new+f1_new),
v5iso (v5 F0 + payload), OS3 stock (s_f0+s_f1).

- Init closure: 33 files in all three worlds; no missing DT_NEEDED.
  Every closure file in the hybrid is **byte-identical** to its v5iso winner
  (0 content diffs) — the same stock winners, no new shadowing (all 33
  resolve from F1, so the OS4-generation F0 changes nothing here).
  Unresolved-symbol sets identical to v5iso (5, all also present in pure
  OS3 stock — pre-existing stock behaviour, not a hybrid defect).
- hwservicemanager closure: 22 files, byte-identical resolution to v5iso,
  unresolved sets identical (15). `libvintf.so` has exactly **3 unresolved
  GLOBAL `android::base::Join` instantiations — the identical symbol set to
  the v5iso baseline** (set/vector × const-ref variants), no more, no new.

### G4 — AVB hash footer: **FAIL**
- A footer struct exists at the file end (`AVBf`, v1.0), cloned from the
  v5iso/avbtool construction (algorithm NONE, single hash descriptor,
  partition `vendor_boot`, fresh salt, digest = SHA-256(salt ‖ image)).
- But it declares original_image_size 78,377,176 and vbmeta_offset
  78,381,056 — both beyond the truncated file. The vbmeta is **absent**;
  the digest cannot verify. (The builder itself was validated against both
  stock and v5iso images, whose digests verify under the same code path;
  the failure is purely the size overflow.)

### G5 — rc / script validity: **PASS**
- `sh -n` on `turner-setup.sh` (stage-2 source and the f1_new copy): rc 0.
- `hybrid-services.rc` manual syntax review: 5 service blocks
  (`vendor.tee-supplicant`, `vendor.keymint-mitee`, `vendor.gatekeeper_mitee`,
  `vendor.touchfeature`, `turner-setup`) + 3 `on boot` triggers; 5
  `setenv LD_LIBRARY_PATH` lines (toml-verbatim isolation). No
  `vndservicemanager` service exists anywhere — it appears only in comments
  stating it must never be started, per DESIGN.
- `turner-vendor_boot-hybrid-v1.img` (INVALID, truncated — see verdict):
  sha256 `ef0b0764cdb513338e441f0b717a53fb32d29fbd4b651422d0f0238635bab299`

## What would make it fit (design decision needed — not done here)

The gap is 11,272,408 B of compressed fragment data. Options, in order of
likely acceptability:

1. **Trim OS4 F0.** F0 is 95.9 MB uncompressed; it is the stock first-stage
   ramdisk, most of which recovery mode never uses. Dropping provably-unused
   F0 content (e.g. duplicate/secondary-arch modules, non-essential firmware)
   could plausibly free >11 MB compressed — but it breaks the "F0 verbatim"
   lock and needs a stage-2-level analysis of what first-stage init actually
   touches before switch_root to the recovery fragment.
2. **Slim the F1 payload** (bundled mitee fallback stack, twres resources).
   Realistic gain is a few MB at most — insufficient alone, and DESIGN keeps
   the fallback material deliberately.
3. Re-examine whether the recovery kernel path can accept a different
   ramdisk compression — stock format is lz4-legacy; no evidence the OS4
   kernel decompresses anything else for vendor_boot. Not recommended.

## Deliverables in stage3/
- `turner-vendor_boot-hybrid-v1.img` — INVALID (truncated overflow artifact).
- `f0_new/`, `f1_new/` — the assembled trees; content-verified per G2/G3.
- `VERIFY.md` — this file.
- `build.py`, `verify.py`, `audit3.py`, `packlib.py` — construction + gate
  tooling (packing parameters proven byte-identical against stock and v5iso
  fragments before assembly). `.work/` holds the built fragment archives
  (f0/f1 cpio+lz4) and the unpacked v5 F0 tree used by the audit.
- `nt36536e_touch_turner.ko` — the extracted fallback module (sha256 above).
