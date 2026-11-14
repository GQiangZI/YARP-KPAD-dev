# Stage 4b — Hybrid v2.1: **ALL GATES PASS — IMAGE PRODUCED**

## The image

- **File:** `stage4/turner-vendor_boot-hybrid-v2.img`
- **Size:** 67,108,864 B (exact partition size)
- **SHA256:** `f33623cb65dacdb8a9f08ee6799c9935eadc2938a226dd14dd8a7167788b96b9`

## What changed vs stage 4

Stage 4's v2 construction was exact but 2,242,086 B over budget, so no
image existed. Stage 4b applied exactly **one** authorized deviation from
the "verbatim OS4 stock F1 skeleton" rule:

- **CUT-1 (applied, sufficient alone):** the OS4 stock F1 `res/` tree
  (stock recovery UI resources — orphaned once `system/bin/recovery` is
  TWRP's; same cut the Skyward a7 adapter made — its F1 has no stock res
  content at all and booted on this tablet).
  - Removed: **576 of 578** stock res entries — all 572 stock res files
    plus the 4 sub-directory entries (`res/images/ch|en|jp|tc`).
    Full list: `.work/delta4b.json` → `stage4b.removed_stock`.
  - Retained: the two 0-byte directory entries `res` and `res/images`,
    kept **only** as parent paths for the retained payload additions
    (`res/fonts/*`, `res/images/dummyfile`) so the archive stays
    well-formed. Every stock res *file* is gone.
  - Measured saving (rebuilt F1 archive): **−10,582,072 B** lz4.
- **CUT-2 (NOT applied):** CUT-1 alone left headroom 8,339,986 B, far
  above the 200,000 B minimum, so the payload res/fonts additions
  (wqy-microhei + DroidSansMono + RobotoCondensed + README +
  `res/images/dummyfile`) are **all retained** — no UI-text font risk
  was taken.

Untouched, as mandated: twrp16 (all 74 libs, byte-identical to stage 4),
`vendor/firmware` (all 46 payload files), the F0 fragment (byte-identical
to stage 3b's, sha256 `ee2e68e7…`), the TWRP recovery binary
(`af0a3aa8…`), twres, recovery.fstab, both orchestration files, and the
append-only mt8799 rc changes.

Build integrity note: before cutting, the refactored packer in
`build4b.py` re-packed the **uncut** stage-4 F1 entry set and reproduced
stage 4's fragment byte-for-byte (lz4 32,475,494 B, sha matches
`f1_delta.json`) — the measured CUT-1 saving is therefore directly
comparable to stage 4's ledger, with zero packing drift.

## Size ledger (lz4-legacy HC12)

| Component | Stage 4 | Stage 4b (v2.1) |
|---|---|---|
| F0 (stage-3b fragment, reused byte-for-byte) | 36,330,472 | 36,330,472 |
| F1 | 32,475,494 | **21,893,422** |
| **Fragments total** | 68,805,966 | **58,223,894** |
| Budget | 66,563,880 | 66,563,880 |
| **Headroom** | −2,242,086 (overflow) | **+8,339,986** |

## Gate results (all re-run on the final image)

| Gate | Result | Evidence |
|---|---|---|
| G1 size/header | **PASS** | Image exactly 67,108,864 B; header_version 4, page 4096, header_size 2128, cmdline bytes, name field, bootconfig 0 all == OS4 stock; DTB byte-identical to stock (sha `4f985cad…`); header ramdisk_size == fragment sum 58,223,894; headroom 8,339,986 B ≥ 200,000 B. |
| G2-STRICT (updated) | **PASS** | F0: fragment bytes == stage-3b's; delta vs OS4 stock F0 == {+11 twrp16, −579 (res/ + stock recovery bin), hw/init.rc +1 setenv line}. F1 vs OS4 stock F1: added == stage-4 enumerated set exactly (137, incl. 74 twrp16 libs with payload-identical bodies and all 46 firmware files); removed == CUT-1 set exactly (576); changed == {recovery.fstab ← payload, mt8799 rc append-only}; **zero shared-path lib changes**; res/fonts additions retained. |
| G3 closures vs pure OS4 stock | **PASS** | init closure 33 files, servicemanager closure 17 files: identical file sets, 0 winner content diffs, unresolved sets identical to pure stock (5 / 7). **hwservicemanager and vndservicemanager confirmed absent** from both the hybrid image and pure OS4 stock — the v1/v5iso hang's prime suspect chain is not shipped. (`audit4b.py`, output in `.work/audit4b-output.txt`.) |
| G4 AVB | **PASS** | Footer `AVBf` v1.0, vbmeta algorithm NONE, descriptor image_size == footer original_image_size (58,765,528), digest verifies: sha256(salt ‖ image[:orig_size]) matches. |
| G5 sh -n + rc semantics | **PASS** | Same checklist as stage 4, re-run against the `f1_v21` tree: `sh -n` clean (source + in-image copy, byte-identical); hybrid-services.rc byte-identical to stage 2 (`68637bf8…`); setup started only via non-blocking `start`, never `exec`; both polling loops bounded with TURNER-SETUP TIMEOUT kmsg logs; 10 step breadcrumbs; all hybrid services `disabled`. |

Verifier outputs: `.work/verify4b-output.txt` (59 PASS / 0 FAIL),
`.work/audit4b-output.txt` (G3 PASS). One stage-4 documentation miscount
found along the way: VERIFY.md §3 says "45 firmware files" — the payload
ground truth is **46** (its own §2 figure of 47 entries = dir + 46 files
agrees); v2.1 ships all 46, verified name- and body-exact against the
payload.

## Artifacts

- `build4b.py` (stage-4 builder + CUT-1 logic; hard-asserts budget),
  `verify4b.py`, `audit4b.py`
- `.work/f1_v21.cpio`, `.work/f1_v21.lz4` (sha `b0a2629b…`),
  `.work/delta4b.json` (full added/removed lists, measurements,
  image sha256), `f1_v21/` tree. Stage 4's `f1_new/`, `.work/f1.*` and
  `VERIFY.md` are untouched.

## Standing caveats (unchanged from stage 4)

- All stage-2 risks R1–R7 (mitee KeyMint precedent, RECO/SYST parcel
  markers, SELinux labels, first-boot mount state) are settled only by
  the first flash — this build carries the early-adb insurance and the
  `HYBRID-BREADCRUMB` / `TURNER-SETUP` kmsg breadcrumbs for exactly
  that.
- Payload `system/bin` helper binaries are not imported (enumerated set
  = recovery binary only); the bundled fallback touch .ko is not in F1
  (touch module load is installed-vendor_dlkm-only). Both were stage-4
  design decisions, unaffected by CUT-1.
