# F0 trim analysis — can OS4 stock F0 be slimmed by ≥ 11,272,408 B (compressed)?

**Verdict, up front:**

- **By cutting modules: NO — structurally impossible on this F0.**
  275 of the 277 modules in F0 sit inside a first-stage load closure
  (`modules.load` ∪ `modules.load.recovery` + `modules.dep` transitive deps).
  Everything outside the closures is exactly **two** modules worth
  **18,933 B compressed** — 0.17 % of the target.
  - Tier 0 alone: **2,287 B** saved → short by **11,270,121 B**.
  - Tier 0 + Tier 1: **18,933 B** saved → short by **11,253,475 B**.
- **The target IS reachable — but only from the non-module payload class:**
  cutting `res/` (the stock-recovery UI image set) **and** the F0 copy of
  `system/bin/recovery` recovers a measured **12,315,675 B compressed**,
  i.e. the target is met with **~1.04 MB to spare**. Applied to the hybrid
  as built (fragment total 77,833,392 B), the fragments drop to
  65,517,717 B vs the 66,563,880 B budget → **~1.05 MB headroom**.
  Both cuts are exactly the surgeries the v5/dash repack recipe already
  performed on the OS3 F0 (see growth section) — which is also where the
  "missing" 11 MB went in the first place.

All compression figures below are **measured**, not ratio estimates: archives
were rebuilt with the stage-3 packlib (newc + lz4-legacy HC12, the parameters
proven byte-identical against stock/v5iso) from the entries parsed out of the
real OS4 stock fragment, with the candidate entries removed, and re-compressed.
Method validation: a tree-built OS4 F0 archive compresses to 46,569,151 B vs
the image's 46,569,104 B (Δ47 B, trailer dialect) — and all removal deltas were
measured on the image-parsed archive itself, so they are exact for stock F0
and carry over to the hybrid F0 (stock + twrp16 + 1 line) within ~3 KB of
block-boundary noise (observed).

---

## 1. Inventory of OS4 stock F0 (95,892,992 B raw cpio, 1,257 entries)

| group | raw bytes | files | share of raw |
|---|---|---|---|
| `lib/modules/*.ko` | 47,471,370 | 277 | 49.5 % |
| `system/` (bin + lib64 + etc, first-stage userspace) | 34,758,995 | 328 | 36.3 % |
| `res/` (stock-recovery UI images) | 11,314,685 | 577 | 11.8 % |
| root files & other dirs (sepolicy 1,496,665, contexts, props, …) | 1,991,248 | 67 | 2.1 % |
| `lib/modules` metadata (dep/alias/load/softdep) | 159,508 | 5 | 0.2 % |
| `first_stage_ramdisk/` (fstab.mt6991, fstab.mt8799) | 19,670 | 2 | 0.0 % |

## 2. What actually grew OS3 → OS4 (the "+11.75 MB" is not OS growth)

Measured stock-vs-stock with the identical toolchain: OS3 stock F0 compresses
to **45,002,186 B** (tree-built from `stock310_f0`), OS4 stock F0 is
**46,569,104 B**. **Real growth = +1,566,918 B compressed** (+3,152,328 B raw).

Raw growth attribution (file-level diff, 5 added / 2 removed / 29 resized):

| contributor | raw delta |
|---|---|
| `lib/modules/ufs-mediatek-mod-ise.ko` (11,904,672 → 14,904,760) | **+3,000,088 (95 % of all growth)** |
| everything else in `lib/modules/*.ko` (incl. 5 new `mi_*`/`node_cache` modules, +156,968) | +126,392 |
| `system/` (mostly `libpcre2.so` +16,728) | +16,800 |
| root files (`sepolicy` +6,043, contexts) | +8,826 |
| `res/` | **0 — byte-count identical** |

The 34,815,121 B "OS3 F0" figure in the stage-3 ledger is the **v5iso F0**,
i.e. OS3 stock *after* the dash-recipe surgeries: `res/` deleted
(−10,580,187 B compressed-equivalent), `system/bin/recovery` deleted
(−1,728,430 B), twrp16 added (+2,076,873 B). 45,002,186 − 10,580,187
− 1,728,430 + 2,076,873 ≈ 34.77 MB ≈ the v5iso fragment. **The hybrid's
overflow is, almost exactly, the two stock components the v5 recipe had
already cut coming back at full size** — there is no new OS4 bloat to hunt.

## 3. First-stage load closure

Inputs in `lib/modules/`: `modules.load` (248 modules), `modules.load.recovery`
(266), `modules.dep` (277 entries), `modules.alias` (1,778 lines, 48 distinct
modules), `modules.softdep` (5 distinct targets). **There is no
`modules.blocklist` anywhere in F0** — so the strict Tier-0 definition
("blocklisted AND …") is vacuous on this build; Tier 0 below uses the
functional equivalent (no load path of any kind).

Closures (list ∪ transitive `modules.dep` deps):

| set | listed | closure |
|---|---|---|
| normal boot (`modules.load`) | 248 | 251 |
| recovery boot (`modules.load.recovery`) | 266 | 267 |
| **union (keep set)** | — | **275 of 277** |

Modalias/softdep reachability beyond the closures: of the 48 alias-listed
modules, 47 are already in the closures; of the 5 softdep targets, all are in
the closures. The modalias class therefore adds exactly **one** module
(`rfkill.ko`) to the reachable set. First-stage init loads what the lists say;
ueventd can only add alias-driven loads, and they are already accounted for.

Non-module first-stage needs (all Tier 2, not cut candidates): `system/bin`
init/ueventd/modprobe/insmod + `system/lib64`, `first_stage_ramdisk/fstab.*`
(storage bring-up for first-stage mount), `sepolicy` + `*_contexts`,
`prop.default`, linker config. The only non-module payloads with no
first-stage consumer are `res/` and `system/bin/recovery` (below).

## 4. Cut tiers and measured recovery

### Tier 0 — provably never loaded (1 module)
Not in any closure, no `modules.dep` edge points at it, no alias, no softdep.

| file | raw | compressed saved |
|---|---|---|
| `lib/modules/libarc4.ko` | 11,465 | **2,287** |

### Tier 1 — not in closures, modalias-reachable (1 module)

| file | raw | compressed saved | reachability |
|---|---|---|---|
| `lib/modules/rfkill.ko` | 59,737 | **17,022** | `modules.alias`: `char-major-10-242 rfkill`, `devname:rfkill` — ueventd could load it if the rfkill device appears |

Tier 0 + Tier 1 joint measurement: **18,933 B** (block-boundary non-additivity
vs the 19,309 B sum). **Module trimming is a dead end — full stop.**

### Tier 2 — do not cut
275 modules (47,400,168 B raw) in the closures + all of `system/`, metadata,
fstab, sepolicy/contexts. Full kept-module list: `appendix-tier-lists.txt`.

### The non-module class that actually reaches the target

| cut | raw | compressed saved (measured) | consumer analysis |
|---|---|---|---|
| `res/` (577 entries: stock recovery UI PNGs — battery/charging screens, wipe/flash dialogs, per-language text images) | 11,314,685 | **10,580,187** | No F0 rc, fstab or init config references `/res` (grep-clean; only false-positive "rescue" partition hits). First-stage init/ueventd/modprobe render no UI. Its only consumer is the stock recovery userspace — which the hybrid design deletes anyway. |
| `system/bin/recovery` (F0 copy) | 3,386,360 | **1,728,430** | In this split-fragment layout, recovery mode switch_roots into F1 and runs F1's recovery service; the platform-fragment copy is the fallback for devices *without* a recovery fragment. Dead here. |
| **`res/` + `system/bin/recovery`** | **14,701,045** | **12,315,675** | **MEETS target, +1,043,267 B margin** |
| (memo) + Tier 0+1 modules | 14,772,247 | 12,334,972 | modules add only ~19 KB; optional |

## 5. Sanity anchors — all in the kept set

- **Touch (nt36536e):** no touch module exists in F0 at all (zero `*.ko`
  matching `*touch*`); `nt36536e_touch_turner.ko` lives in vendor_dlkm and
  the hybrid already carries its fallback copy in F1. Nothing to cut —
  anchor satisfied by construction.
- **Storage (UFS):** `phy-mtk-ufs.ko`, `ufs-mediatek-dbg.ko`,
  `ufs-mediatek-mod-ise.ko` — all Tier 2 (in the load closures).
- **USB:** `xhci-mtk-hcd-v2.ko`, `usb_boost.ko`, `usb_dp_selector.ko`,
  `usb_meta.ko`, `extcon-mtk-usb.ko`,
  `phy-mtk-mt6379-eusb2-repeater.ko`, `phy-mtk-nxp-eusb2-repeater.ko`
  — all Tier 2.
- **Display (bonus):** `mediatek-drm.ko`, `mtk-cmdq-drv-ext.ko`,
  `drm_dma_helper.ko`, `drm_display_helper.ko` — in `modules.load.recovery`,
  Tier 2.

## 6. Risks

1. **`res/` + recovery-binary are a pair.** The only plausible reader of
   `res/` is the stock recovery userspace whose binary is the other cut.
   Cutting both is self-consistent; cutting `res/` alone while keeping the
   F0 recovery binary would not be. Residual unknowns: an MTK first-stage
   component rendering a pre-recovery screen from the ramdisk (boot-warning /
   dm-verity screens are drawn by lk, not the ramdisk; offline-charging UI
   likewise does not come from this fragment on this platform) — not
   device-verified. The OS3 v5 line shipped with both already cut (its boot
   failure was never attributed to either).
2. **`system/bin/recovery` removal assumes the split-fragment switch_root
   path** — the same assumption the v5 recipe ran on. First flash of a
   trimmed build should watch for any platform-recovery fallback exec.
3. **Headroom after the fix is ~1.05 MB.** Any future F1 growth eats it;
   the two stray modules would add only ~19 KB more. If more room is ever
   needed, the next candidates would have to come out of `system/`
   (e.g. duplicated adbd/fastbootd) — **not** measured or endorsed here:
   F0 copies can serve first-stage/fastbootd transitions.
4. **The tier analysis is load-list-version-specific.** MTK ships nearly
   the entire module set in the recovery load list; a future OTA that
   changes the lists invalidates the (already negligible) module tiers —
   but the `res/` + recovery-binary cuts do not depend on the lists.
5. Nothing else in F0 is fat: after modules, `system/` is 34.7 MB of
   first-stage userspace that recovery genuinely boots through, and the
   remaining root files total ~2 MB. There is no third lever of this size.

## Files

- `TRIM-ANALYSIS.md` — this report.
- `appendix-tier-lists.txt` — Tier 0 / Tier 1 / full Tier-2 kept-module list.
- `analysis.json` — machine-readable inventory, growth diff, tiers, measurements.
- `analyze.py`, `measure2.py` — the measurement scripts (read-only; rerunnable).

No tree was modified; all cuts are proposals.
