# Stage 6 — Hybrid v2.2: **ALL GATES PASS — IMAGE PRODUCED**

## The image

- **File:** `stage6/turner-vendor_boot-hybrid-v2.2.img`
- **Size:** 67,108,864 B (exact partition size)
- **SHA256:** `7adf15f1c0c7d786026c756b72b4f65acc513aef3f5f4c0817002ac95e7dc4ff`

## What changed vs v2.1

Exactly one thing: the F1 copy of `system/lib64/twrp16/libtwrpminui.so`
is replaced by a binary-patched copy that forces
`MinuiBackendDrm::legacy_modeset = true` (stage-5 Fix 1), so GUI init
takes the legacy `drmModeSetCrtc`/`drmModePageFlip` path and never calls
the SDE-gated `Initdisplay()`. Everything else — F0 fragment (reused
byte-for-byte from stage 3b), the other 73 twrp16 libs, firmware, twres,
fstab, orchestration, rc appends, CUT-1 — is v2.1 verbatim. The build
first re-ran build4b's logic with the **original** lib and reproduced
stage 4's uncut F1 fragment byte-for-byte (sha-asserted in `build6.py`)
and v2.1's CUT-1 size exactly (21,893,422 B), then substituted the
patched body and re-packed: final F1 lz4 21,893,420 B (−2 B — the
patched bytes compress marginally better), headroom 8,339,988 B
(v2.1: 8,339,986 B).

## The patch

### Target

`libtwrpminui.so` as shipped in v2.1 (`stage4/f1_new/system/lib64/
twrp16/libtwrpminui.so`): 268,768 B, sha256
`0615820440c694fe840eb9ad58dcd7dcd22818dde5f0efa78434e414c1d7d269`
(re-verified at stage-6 start; copies kept as `libtwrpminui.so.orig` /
`libtwrpminui.so.patched`, patched sha256
`71aee2540c4995920fe520cdb0cd4c3b4d694462686638eaf6a1c6884e3a1939`).
ELF64 AArch64 DYN, stripped; exported dynsym used for function bounds:
`_ZN15MinuiBackendDrm4InitEv` at vaddr 0x1c0b4, size 2380. In the R-E
PT_LOAD, vaddr == file offset, so all addresses below are both.

### The gate in the original binary

Source semantics (graphics_drm.cpp, per stage-5 research):
`legacy_modeset = version->name && !strcmp(version->name, "virtio_gpu");`
with `legacy_modeset` at `this + 0x352` and `drm_fd` at `this + 0x348`
(x19 = `this`). Compiled form (original disassembly):

```
0x1c3b8:  ldr      w0, [x19, #0x348]        ; drm_fd
0x1c3bc:  cmn      w0, #1
0x1c3c0:  b.eq     #0x1c9b0                 ; fd == -1 -> skip block
0x1c3c4:  cbz      x20, #0x1c9b0            ; resources == NULL -> skip
0x1c3c8:  bl       drmGetVersion@plt        ; x0 = drmVersion*
0x1c3cc:  cbz      x0, #0x1c404             ; version == NULL -> store SKIPPED
0x1c3d0:  ldr      x8, [x0, #0x10]          ; x8 = version->name
0x1c3d4:  cbz      x8, #0x1c3fc             ; name == NULL -> store w8 (=0)
0x1c3d8:  adrp     x1, #0xa000
0x1c3dc:  add      x1, x1, #0x526           ; -> 0xa526 "virtio_gpu"
0x1c3e0:  mov      x21, x0                  ; save version*
0x1c3e4:  mov      x0, x8                   ; arg0 = name
0x1c3e8:  bl       strcmp@plt
0x1c3ec:  mov      w8, w0                   ; w8 = strcmp result
0x1c3f0:  mov      x0, x21                  ; restore version*
0x1c3f4:  cmp      w8, #0
0x1c3f8:  cset     w8, eq                   ; w8 = (name == "virtio_gpu")
0x1c3fc:  strb     w8, [x19, #0x352]        ; legacy_modeset = w8  <-- THE store
0x1c400:  bl       drmFreeVersion@plt
```

Notes on the original flow: on the NULL-name path the compiler reuses
x8 (== 0) as the stored value, landing directly on the `strb`. The
downstream consumer in the same function (untouched by the patch):

```
0x1c92c:  bl       drmSetClientCap@plt
0x1c930:  ldrb     w8, [x19, #0x352]        ; legacy_modeset
0x1c934:  tbnz     w8, #0, #0x1c958         ; set -> skip Initdisplay
0x1c938:  mov      x0, x19
0x1c93c:  mov      w1, wzr                  ; DRM_MAIN
0x1c940:  bl       Initdisplay@plt          ; only reached if flag clear
0x1c944:  cbz      w0, #0x1c958
0x1c948:  adrp/add x0, -> "Failed to init display" ; puts -> failure path
```

### Patch sites (5 bytes, 2 instructions)

| File offset | Original | Patched | Effect |
|---|---|---|---|
| 0x1c3d4 | `cbz x8, #0x1c3fc` (`48 01 00 b4`) | `cbz x8, #0x1c3f8` (`28 01 00 b4`) | NULL-name path now lands on the force-1 instruction instead of the bare store |
| 0x1c3f8 | `cset w8, eq` (`e8 17 9f 1a`) | `mov w8, #1` (`28 00 80 52`) | strcmp result is discarded; the value stored is always 1 |

Why this forces `legacy_modeset = true` on every path that stores:

- **name != NULL:** strcmp still runs (harmless), its result is loaded
  into w8 and compared, then `mov w8, #1` overwrites it immediately
  before the `strb` — stored value is 1 for *every* driver name,
  including `mediatek`.
- **name == NULL:** the retargeted `cbz` joins the same `mov w8, #1`,
  so this path also stores 1 instead of the original 0.
- **No later reset:** an exhaustive capstone sweep of the whole .text
  (39,828 instructions) finds exactly **one** `strb` to offset 0x352 in
  the entire library — the Init() store above. All other 0x352 accesses
  are `ldrb` reads (Init ×3 more, plus Blank/Flip/pipeline helpers)
  that *consume* the flag to select the legacy paths, as designed.
- **Single gate:** the string `virtio_gpu` occurs exactly once in the
  file (rodata 0xa526) and is referenced exactly once (0x1c3d8/0x1c3dc,
  both in Init). No second occurrence of the gate exists.
- Residual path: if `drmGetVersion` itself returns NULL (0x1c3cc) the
  store is skipped and the flag keeps its pre-Init value. That means
  DRM version query failed outright — no display path can succeed in
  that state anyway — and it is not the target device's behaviour (the
  v2.1 failure log shows mode/buffer setup succeeding, i.e. version
  query worked; the flag was written 0 by the strcmp path).

### After patching (re-disassembly)

```
0x1c3d4:  28 01 00 b4   cbz      x8, #0x1c3f8   ; target 0x1c3f8
...
0x1c3f8:  28 00 80 52   mov      w8, #1
0x1c3fc:  68 4a 0d 39   strb     w8, [x19, #0x352]
```

A full disassembly diff of `MinuiBackendDrm::Init()` (595 instructions)
between orig and patched shows **exactly these 2 instruction lines
changed** and nothing else. The patched file is the same size
(268,768 B), parses as a valid AArch64 ELF, and its DT_NEEDED list is
identical to the original.

### Byte diff (cmp -l, octal values decoded to hex)

| File offset | Orig | Patched |
|---|---|---|
| 0x1c3d4 | 0x48 | 0x28 |
| 0x1c3f8 | 0xe8 | 0x28 |
| 0x1c3f9 | 0x17 | 0x00 |
| 0x1c3fa | 0x9f | 0x80 |
| 0x1c3fb | 0x1a | 0x52 |

Exactly 5 differing bytes, all inside the two documented instructions.

## Size ledger (lz4-legacy HC12)

| Component | v2.1 | v2.2 |
|---|---|---|
| F0 (stage-3b fragment, reused byte-for-byte) | 36,330,472 | 36,330,472 |
| F1 | 21,893,422 | **21,893,420** |
| **Fragments total** | 58,223,894 | **58,223,892** |
| Budget | 66,563,880 | 66,563,880 |
| **Headroom** | +8,339,986 | **+8,339,988** |

## Gate results (all re-run on the final image)

| Gate | Result | Evidence |
|---|---|---|
| G1 size/header | **PASS** | Image exactly 67,108,864 B; header_version 4, page 4096, header_size 2128, cmdline bytes, name field, bootconfig 0 all == OS4 stock; DTB byte-identical to stock (sha `4f985cad…`); header ramdisk_size == fragment sum 58,223,892; headroom 8,339,988 B ≥ 200,000 B. |
| G2-STRICT | **PASS** | F0: fragment bytes == stage-3b's; delta vs OS4 stock F0 identical in kind to v2.1. F1 vs OS4 stock F1: added == stage-4 enumerated set exactly (137), removed == CUT-1 set exactly (576), changed == {recovery.fstab, mt8799 rc append-only}, zero shared-path lib changes. **F1 vs v2.1 F1 (stage4/.work/f1_v21.cpio): added == ∅, removed == ∅, changed == {system/lib64/twrp16/libtwrpminui.so} exactly.** The other 73 twrp16 libs are payload-byte-identical; the in-image libtwrpminui.so == the patched deliverable, and its byte diff vs the original == the 5 documented patch bytes only. |
| G3 closures vs pure OS4 stock | **PASS — identical to v2.1** | `audit6.py` output matches `audit4b.py` line-for-line on every figure: init closure 33 files, unresolved 5 == stock; servicemanager closure 17 files, unresolved 7 == stock; 0 winner content diffs; no new/resolved-away unresolved symbols; hwservicemanager and vndservicemanager absent from both worlds. (The patched lib is in neither closure, as expected.) |
| G4 AVB | **PASS** | Footer `AVBf` v1.0, vbmeta algorithm NONE, descriptor image_size == footer original_image_size (58,765,528), digest verifies: sha256(salt ‖ image[:orig_size]) matches. |
| G5 sh -n + rc semantics | **PASS** | Same checklist as stage 4/4b, re-run against the `f1_v22` tree: `sh -n` clean and byte-identical to the stage-4 source; hybrid-services.rc byte-identical to stage 2; setup started only via non-blocking `start`, never `exec`; bounded polls with TURNER-SETUP TIMEOUT kmsg logs; step breadcrumbs; all hybrid services `disabled`. |
| G6-PATCH | **PASS** | Orig lib 268,768 B / sha `06158204…`; patched lib same size / sha `71aee254…`; byte diff of the deliverables == the documented 5 bytes at 0x1c3d4 + 0x1c3f8–0x1c3fb; readelf parses the patched lib as valid AArch64 ELF; DT_NEEDED identical orig vs patched; full `Init()` disassembly diff == exactly the 2 patched instructions (`cbz x8 -> #0x1c3f8`, `mov w8, #1`); downstream `ldrb`/`tbnz` gate at 0x1c930/0x1c934 verified intact, so with the flag forced, Initdisplay is skipped. |

Verifier outputs: `.work/verify6-output.txt` (**73 PASS / 0 FAIL**;
verify4b had 59 — the delta is the new v2.1-comparison + G6 checks),
`.work/audit6-output.txt` (G3 PASS). Build manifest:
`.work/delta6.json` (incl. the `stage6` section with patch record and
final headroom).

## Artifacts

- `build6.py` (build4b clone + stage-6 substitution), `verify6.py`,
  `audit6.py`
- `libtwrpminui.so.orig`, `libtwrpminui.so.patched`
- `.work/`: `f1_v22.cpio`, `f1_v22.lz4` (sha `a33b715b…`), `f0.lz4`,
  `delta6.json`, `appendage.txt`, `patch.py`, `adis.py` (capstone
  disassembler, venv in `.work/venv`), `init_orig.asm`,
  `init_patched.asm`, `text_orig.asm` (full .text sweep),
  `verify6-output.txt`, `audit6-output.txt`
- `f1_v22/` tree. Nothing outside `stage6/` was modified.

## Standing caveats

- The patch is proven statically (control flow, single store, byte
  diff). Whether the legacy modeset path fully drives the MT6991 panel
  (page-flip vsync behaviour is the known presentational risk from the
  stage-5 research) is settled only by the first flash — the image
  keeps v2.1's early-adb insurance and HYBRID-BREADCRUMB / TURNER-SETUP
  kmsg breadcrumbs for that test.
- All stage-2 risks R1–R7 (decrypt chain etc.) are unchanged from
  v2.1 and likewise await on-device settlement.
