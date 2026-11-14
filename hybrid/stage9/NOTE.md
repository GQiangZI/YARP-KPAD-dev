# stage9 — v2.4 post-flash diagnosis prep (2026-11-14 ~20:40 CST)

User flashed hybrid v2.4 at 19:41 CST; verdict 19:41: touch STILL dead.
Pending evidence (user on night shift, resumes tomorrow morning 2026-11-15):
/tmp/recovery.log pull + `ls /dev/input` + init.svc states for
vendor.touchfeature / vendor.keymint-mitee / vendor.gatekeeper_mitee.
Do NOT build v2.5 until that log is read — it decides between the two branches below.

## What was verified offline tonight (no tablet needed)

### 1. The v2.4 touch-module loader SHOULD work on paper
- OS4 vendor_dlkm modules.dep (extracted with erofs-utils 1.7.1, installed
  tonight; the ARM dump.erofs in the ramdisk cannot run on this x86 VM):
  `nt36536e_touch_turner.ko: /vendor_dlkm/lib/modules/xiaomi_touch_turner.ko`
  — exactly ONE dep, and `xiaomi_touch_turner.ko:` has no deps.
- modinfo cross-check: nt36536e also needs sc96231 + mediatek-drm, but BOTH
  are already first-stage loaded: sc96231.ko, mediatek-drm.ko and miev.ko are
  all in OS4 F0 lib/modules/modules.load (display working proves mediatek-drm).
  xiaomi_touch_turner.ko exports all 7 symbols nt36536e was missing in v2.3
  (register_touch_panel, xiaomi_register_panel_notifier,
  xiaomi_unregister_panel_notifier, unregister_touch_panel, get_raw_data_base,
  notify_raw_data_update, driver_get_touch_mode — verified by readelf).
- v2.3 log re-read (~/workspace/user/files/recovery-v23_56_tvio.log):
  canonical /vendor_dlkm was NOT mounted (dev.mnt.blk.vendor_dlkm empty) but
  the scratch mount /tmp/hybrid/vendor_dlkm WAS (dm-11, sdc82) — so the v2.3
  failure was purely the doubled-path bug, which v2.4's basename closure
  loader fixes. v2.4 image re-verified tonight: verify8.py ALL PASS
  (sha 554cac23…, headroom 8,144,798 B).
- Consequence: if the v2.4 log shows `insmod xiaomi_touch_turner.ko ok` +
  `insmod nt36536e_touch_turner.ko ok` and /dev/input gains a touch node,
  the module layer is DONE and the fault is HAL-only (branch B). If the
  loader still fails, the log's exact insmod error is the next clue (branch A).

### 2. NEW FINDING — the v2.4 stub may not satisfy a VERSIONED reference
- rkp-V3-ndk.so (OS4 system copy, user-pulled) references the symbol as
  `AIBinder_Class_setTransactionCodeToFunctionNameMap@LIBBINDER_NDK36`
  (readelf -W --dyn-syms, entry 39; version 7 = LIBBINDER_NDK36).
- System libbinder_ndk defines it as `@@LIBBINDER_NDK36`.
- The v2.4 stub (stage8/libbinder_trace_stub.so, hand-crafted 4 KB ELF)
  exports the name with NO version information at all
  (`readelf -W -V`: "No version information found in this file").
- A version-checking linker skips an unversioned definition when the
  reference demands LIBBINDER_NDK36 — so keymint/gatekeeper may STILL die
  with the same CANNOT LINK in v2.4, and the stub would be a silent no-op.
  This is a hypothesis with strong ELF evidence, NOT proven: the v2.4 log
  settles it (grep CANNOT LINK). If the log shows keymint running, the
  hypothesis is dead and the stub worked.
- Touch HAL note: vendor.touchfeature does NOT link rkp, so the stub is
  irrelevant to it; its v2.2/v2.3 TIMEOUT (never `running`) is a separate,
  still-open cause — in v2.4 its library order is back to a7 ramdisk-first,
  which is the arrangement the a7 toml prescribes for registration with the
  recovery servicemanager. If touchfeature still times out in v2.4, check
  its own link/registration lines in the log, not the stub.

### 3. HTCP reminder (a7 device.toml, already known — restated for the branch)
Even with the driver loaded and the input node present, the NT36536E in
Xiaomi HTCP mode produces NO evdev events until vendor.touchfeature is
running. So "module loaded but touch dead" == "HAL dead", not "driver dead".

## v2.4 log reading checklist (first grep, in order)
1. `grep "touch module closure" recovery.log` — v2.4 loader ran? closure =
   `xiaomi_touch_turner nt36536e_touch_turner`?
2. `grep "insmod.*\.ko ok\|insmod.*failed" recovery.log` — which modules landed?
3. `grep "touch diag: /dev/input" recovery.log` — touch input node present?
4. `grep "CANNOT LINK" recovery.log` — stub hypothesis live or dead?
5. `grep "TIMEOUT: vendor\." recovery.log` + `getprop init.svc.vendor.*`
   — which HALs reached `running`?
6. `grep -i "nt36536\|xiaomi_touch" recovery.log` (dmesg lines) — Unknown
   symbol lines mean a dep is still missing; none + no input node means
   probe failed for another reason (firmware / enable_touch_raw).

## v2.5 branches (do not build before the log)
- Branch A (loader still fails): fix from the exact insmod error in the log.
- Branch B (module loaded, HAL dead): if CANNOT LINK persists → swap in the
  versioned stub below (drop-in replacement, same SONAME/path) and rebuild;
  if touchfeature alone times out → read its registration/link lines first.
- Branch C (module loaded AND keymint/gatekeeper running, touchfeature dead):
  touch HAL is the sole remaining fault; do not touch the TEE side.

## Prepared artifact: versioned stub (built + verified tonight)
- Files: ~/workspace/yarp-hybrid/stage9/stub.c, stub.map,
  libbinder_trace_stub_v25.so (68 KB, sha256
  fabb03f6bdf815142a43aebe434c103feec2f3b6d6a44acb38ac26ad843f3567)
- Built with aarch64-linux-gnu-gcc + version script; verified by readelf:
  `AIBinder_Class_setTransactionCodeToFunctionNameMap@@LIBBINDER_NDK36`,
  verdef LIBBINDER_NDK36 present, exactly one GLOBAL FUNC export, no NEEDED
  libs, SONAME libbinder_trace_stub.so (same path as v2.4's stub).
- Function is void and only registers a trace map; no-op body is safe.
- NOT yet put into any image — that waits for the v2.4 log verdict.
