# Stage 4 — Hybrid v2 (strict isolation): **G1 FAILED on size — NO IMAGE PRODUCED**

Verdict up front: the v2 construction is exactly as specified and passes
G2-STRICT, G3 and G5 on the constructed trees — but the mandated content
does not fit the 64 MiB partition. Fragments total **68,805,966 B** vs the
**66,563,880 B** budget → **overflow 2,242,086 B (~2.14 MiB)**.
`build4.py` hard-asserts the budget and refused to write an image
(exit 2). No `turner-vendor_boot-hybrid-v2.img` exists. The twrp16 set was
NOT trimmed — that decision is above this build's authority. Priced
options are in §6.

All other work is complete and inspectable: `build4.py`, `audit4.py`,
`verify4.py`, `turner-setup.sh` (patched), trees `f0_new/` + `f1_new/`,
`.work/{f0.lz4, f1.cpio, f1.lz4, f1_delta.json, appendage.txt}`.

## 1. Gate results

| Gate | Result | Evidence |
|---|---|---|
| G1 size/header | **FAIL (size)** | fragments 68,805,966 > 66,563,880 budget; raw would be 69,349,592 + vbmeta + footer > 67,108,864. Header/cmdline/DTB are inherited from OS4 stock by construction (same code path as stage 3b, whose G1 passed); moot without an image. |
| G2-STRICT | **PASS** (on the constructed entry set) | F1 delta == enumerated set exactly: 137 added, 2 changed, 0 removed, **zero shared-path lib changes**. F0 fragment byte-identical to stage 3b's; its delta vs OS4 stock F0 == stage 3b's verified delta. |
| G3 closures vs pure OS4 stock | **PASS** | init closure 33 files and servicemanager closure 17 files: identical file sets, **0 winner content diffs**, unresolved sets identical to pure stock. hwservicemanager question: see §4 — exonerated by construction. |
| G4 AVB | moot | No image exists to verify. (Stage-3b-proven footer code path unchanged.) |
| G5 sh -n + rc semantics | **PASS** | See §5 checklist. |

## 2. Size ledger (lz4-legacy HC12, the proven packing method)

Packing fidelity first: re-packing the **pure stock F1** entry set with
this builder's emitter yields **16,551,481 B — exactly the shipped stock
fragment size**. Packing noise is zero; the overflow is 100 % content.

| Component | lz4 size |
|---|---|
| F0 (stage-3b fragment, reused byte-for-byte, sha256 `ee2e68e7…`) | 36,330,472 |
| F1 stock base | 16,551,481 |
| + core (TWRP recovery bin, fstab swap, 2 orchestration files, rc appendage) | +1,715,280 |
| + twrp16 (74 libs, 21,267,824 raw) | +9,023,830 |
| + twres (5 entries) | +46,293 |
| + res additions (fonts, §3) | +3,093,209 |
| + vendor/firmware (47 entries) | +2,045,021 |
| **F1 total** | **32,475,494** (budget share 30,233,408 → over by 2,242,086) |
| **Fragments total** | **68,805,966** (budget 66,563,880) |

## 3. F1 delta (vs `stage1/os4_f1`, archive-level, verified)

- **Added (137)**: `system/bin/recovery` (TWRP bin, sha256 `af0a3aa8…`,
  mode 0755 — an *addition*: stock F1 has no such path; the only stock
  recovery binary lived in F0 and stage 3b deleted it there);
  `system/lib64/twrp16/` dir + 74 libs (§3.1); `twres/` + 4 files
  (languages en/id, portrait.xml); res additions = payload-only paths
  `res/fonts/` + `DroidSansMono.ttf` + `RobotoCondensed-Regular.ttf` +
  `wqy-microhei.ttf` (5,177,387 raw) + README + `res/images/dummyfile`;
  `vendor/` + `vendor/firmware/` + 45 firmware files;
  `system/bin/turner-setup.sh` (stage-4 patched), 
  `system/etc/init/hybrid-services.rc` (stage-2 verbatim, sha256 `68637bf8…`).
  - Note on res/: 101 same-name res files differ between payload and OS4
    stock (OS3-era vs OS4 artwork). They were **not** imported — importing
    them would be shared-path replacement, outside the enumerated set.
    Only the 6 payload-only additions came over.
- **Changed (2)**: `system/etc/recovery.fstab` (body ← payload, mode
  unchanged 0644); `init.recovery.mt8799.rc` (**append-only**: new body ==
  stock body + appendage, mode unchanged 0750; stock lines incl. the
  `mtk_plpath_utils` exec untouched).
- **Removed: none.**
- **Shared-path libraries changed: ZERO.** Every stock `system/lib64`
  entry in the merged view is the OS4 stock build, byte for byte.

### 3.1 twrp16 set (computed mechanically by hashing; 74 libs)

Rule: payload `system/lib64` regular files whose resolved bytes differ
from the merged OS4-stock counterpart (32), plus payload-only libs the
TWRP binary needs (42) — "needs" = DT_NEEDED closure of
`system/bin/recovery` within the payload world ∪ `.so` names in the
binary's string table (dlopen candidates).

- **Differing (32)**: android.hardware.boot-V1-ndk, boot@1.0/1.1/1.2,
  fastboot-V1-ndk, fastboot@1.0/1.1, health-V3-ndk, health@1.0/2.0,
  libadbd_auth, libadbd_fs, libasyncio, libbinder, libbinder_ndk,
  libboot_control_client, libcap, libext2_blkid, libext2_com_err,
  libext2_e2p, libext2_misc, libext2_quota, libext2fs, libhidlbase,
  liblz4, libpcre2, libpng, libselinux, libsysutils, libtinyxml2,
  libvintf, libziparchive. (5,806,184 raw bytes total.)
- **Payload-only, needed (42)**: android.frameworks.stats@1.0,
  authsecret@1.0, gatekeeper-V1-ndk, gatekeeper@1.0, health-V4-ndk,
  health-translate-ndk, health@2.1, oemlock@1.0,
  security.keymint-V4-ndk, security.secureclock-V1-ndk, vibrator-V2-cpp,
  vibrator-V2-ndk, weaver-V2-ndk, weaver@1.0, security.authorization-ndk,
  security.maintenance-ndk, system.keystore2-V5-ndk,
  lib_android_keymaster_keymint_utils, libandroidicu, libblkid,
  libdl_android, libf2fs_sparseblock, libft2, libgatekeeper_aidl,
  libgui2 (1,484,960), libhardware, libicui18n (2,832,648), libicuuc
  (1,971,328), libkeystoreinfo, liblvgl_twrp (1,522,872), libresetprop,
  libsqlite (1,324,632), libstdc++, libsync, libtwrpdigest,
  libtwrpminui, libtwrpmtp-ffs, libtwrpperf, libusbhost, libvndksupport,
  libvpx (2,076,120), libwebm_mkvmuxer. (15,461,640 raw bytes total.)
- **Payload-only, excluded as not needed (22)**: health.storage-V1-ndk,
  health.storage@1.0, hidl.token@1.0, suspend-V1-ndk,
  libaconfig_storage_read_api_cc, libchrome, libdebuggerd_client,
  libevent, libfs_mgr_binder, libfuse-lite, libhardware_legacy,
  libincfs, libkeymint_support, liblpdump, liblpdump_interface-cpp,
  libncurses, libncurses_recovery, libntfs-3g, libprocinfo,
  libprotobuf-cpp-full, libsnapshot, server_configurable_flags.
- **By design not in F1 twrp16**: libbase, libc++, libcutils, libfs_mgr,
  liblog, liblp, libprotobuf-cpp-lite, libutils, libkeyutils et al. have
  no payload build at shared paths — the v5 design carried the TWRP
  builds of these **only in F0's twrp16** (10 libs), reached by the
  recovery service via its F0 setenv `LD_LIBRARY_PATH`. v2 keeps that:
  the merged view serves the recovery service F0's private copies while
  init/servicemanager resolve only stock builds. `libcrypto.so` needs no
  F1 copy either — the payload's shared-path build is byte-identical to
  OS4 stock's; the differing TWRP build (`e2e4effe…`) is F0 twrp16's.

## 4. G3 detail — the hwservicemanager/libvintf question, settled

- init closure (33 files) and servicemanager closure (17 files):
  hybrid vs **pure OS4 stock** — identical file sets, 0 winner diffs,
  unresolved sets identical (5 and 7 respectively, stock's own baseline).
- **There is no `system/bin/hwservicemanager` in OS4 stock at all**
  (nor `vndservicemanager`). HAL registration in this layout is done by
  the stock `servicemanager` binary from F0. hwservicemanager existed
  only in v5iso's merged tree (TWRP build, 137,384 B, added by F1), and
  the 3 unresolved `android::base::Join` instantiations lived in that
  TWRP binary's pairing with TWRP's libvintf.
- In v2, hwservicemanager/vndservicemanager are **absent** (verified in
  both v2 and pure stock), servicemanager is the stock binary with a
  stock-identical closure. **The prime suspect chain of the v1/v5iso
  hang is exonerated by construction: v2 does not ship it.**
  (Audit note: an earlier draft of audit4 audited the non-existent
  hwservicemanager path and degenerated to a vacuous 1-file closure in
  both worlds; the audit was corrected to servicemanager + explicit
  absence checks before any result was relied on.)

## 5. G5 — semantics audit checklist

- (a) `turner-setup` is started **only** via `start turner-setup` in
  hybrid-services.rc `on boot`. Verified by grep: hybrid-services.rc is
  the *only* rc in F1 referencing turner-setup; no `exec` of it anywhere;
  all 5 hybrid services + the setup service are `disabled` (no
  class_start race).
- (b) Every polling loop in the patched `turner-setup.sh` is bounded:
  block-device waits 10×1 s with a post-loop
  `TURNER-SETUP: TIMEOUT after 10s waiting for <dev>` kmsg log;
  service-start poll 30×(ctl.start + 1 s) with
  `TURNER-SETUP: TIMEOUT: <svc> did not reach running within 30s`.
  Remaining sleeps are fixed one-shot waits (4 s / 5 s, from a7's toml).
  `sh -n` passes on the stage-4 source and the F1 copy (byte-identical).
  10 `step:` breadcrumbs are written to /dev/kmsg via the TURNER-SETUP
  tag (begin / mounts / props aligned / persist+metadata / touch module
  / tee / keymint / gatekeeper / touch HAL / done).
- (c) Orchestrated service starts use `setprop ctl.start <svc>` —
  asynchronous by definition; nothing in the script or rc waits on a
  service synchronously except the bounded poll in (b), which runs
  inside the setup *service*, never in init's trigger queue.
- Breadcrumbs in `init.recovery.mt8799.rc` (appended triggers):
  `HYBRID-BREADCRUMB:early-init|init|late-init|boot|late_boot` via
  `write /dev/kmsg …`, plus the Skyward block on boot (setprop
  sys.usb.config adb; the 6 /data/vendor mkdirs; setprop
  vendor.teefs_state ready). Caveats: (i) the appended `on boot`
  breadcrumb runs *after* the stock block containing the blocking
  plpath exec in action order — a plpath hang therefore presents as
  "late-init present, boot absent", which still localizes; (ii) whether
  `on late_boot` is ever queued by this init build is unverifiable
  statically — the block is syntactically valid and harmless if never
  triggered.
- Patch delta stage-2 → stage-4 script is limited to: semantics header,
  `LOG_TAG=TURNER-SETUP`, the two TIMEOUT logs, step breadcrumbs, and a
  comment noting the bundled touch .ko fallback is not shipped in v2's
  F1 (the strict delta has no `system/etc/hybrid/` path; the script
  tolerates its absence; the primary installed-vendor_dlkm load path is
  unaffected). hybrid-services.rc is byte-identical to stage 2.

## 6. What it would take to fit (priced options — NOT applied)

| Option | Δ lz4 | Resulting headroom | Cost |
|---|---|---|---|
| Drop res additions (fonts) | −3,093,209 | **+851,123 (fits)** | TWRP loses wqy-microhei (CJK) + 2 Latin fonts from res/fonts; whether GUI2 renders text without them is untested — twres carries no fonts. UI text risk. |
| Drop vendor/firmware | −2,045,021 | −197,065 (still over) | Loses the bundled touch-firmware fallback; runtime touch relies on installed-system files only. Not sufficient alone. |
| Drop both | −5,138,230 | +2,896,144 (fits) | Both costs above. |
| Trim twrp16 | — | — | Not available within the rules: all 74 libs are mandated by the mechanical differing/needed computation; the big ones (libicui18n, libvpx, libicuuc, liblvgl_twrp, libgui2, libsqlite) are all DT_NEEDED-reachable from the recovery binary. |
| Shrink F0 | — | — | F0 is mandated byte-for-byte reuse of stage 3b's verified fragment. |

## 7. Known v2 limitations (had it fit)

- Payload `system/bin` helper binaries (twrp's toybox applets, tar,
  etc.) are not imported — the enumerated set includes only the
  recovery binary. Runtime gaps are possible and would surface in the
  UI/log on first boot.
- The bundled fallback touch .ko (stage-3 extraction, sha `151619c7…`)
  is not in F1; touch module load is installed-vendor_dlkm-only.
- All stage-2 risks R1–R7 (mitee KeyMint precedent, RECO/SYST markers,
  SELinux labels, mount-overs, APEX ordering, first-boot mount state)
  stand unchanged — they were always going to be settled by the first
  flash's kmsg breadcrumbs, which this build does carry.
