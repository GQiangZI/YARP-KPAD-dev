# diag-v22 forensics — v2.2 decrypt HAL failure (2026-11-14 ~18:35 CST)

Source files (user-sent, local copies):
- `~/workspace/user/files/diag-v22_42_qsqo.txt` — 4,133,669 B, 42,381 lines:
  `dmesg` + `getprop` from the tablet still running hybrid v2.2 recovery.
  Sent by the user 2026-11-14 18:31 CST (message `a2224701-…`), ~9 min after
  the v2.2 boot (18:22 CST). Ring buffer starts at t≈199 s; early boot has
  scrolled off, so first-failure lines for the services are NOT in this file.
- `~/workspace/user/files/recovery-v22_41_sg8g.log` — 63,324 B, 1,619 lines:
  the v2.2 boot's `/tmp/recovery.log`, pulled 18:29 CST.

## 1. What the diag PROVES

All three HALs die the SAME way — not three separate bugs:
- `vendor.touchfeature`, `vendor.keymint-mitee`, `vendor.gatekeeper_mitee`
  each start, then **`exited with status 1` 3–6 ms later**, and init restarts
  them every ~5 s forever (diag lines 137–260 and repeats through the file;
  final getprop: all three `init.svc.* = restarting`, pids 1467/1468/1470).
- `tee-supplicant` is the ONLY chain member alive (`running`, pid 496,
  `vendor.teefs_state=ready`); `vendor.gatekeeper_mitee` never reached
  `running` once. `logd` also crash-loops (`init.svc.logd=restarting`).
- **SELinux is NOT the blocker**: the whole 42k-line dmesg has exactly 5
  `avc: denied` lines, all `permissive=1`, none against these services
  (adbd reading recovery.log; dmesg syslog_read). No denial for keymint,
  gatekeeper, touchfeature, or tee-supplicant anywhere.
- **The mitee_worker "blocked >120 s" lines are NOT a wedged TEE**: the
  hung-task detector fires identically on `g_reclaim_threa` (GPU reclaim)
  and `block2mtd_retry` in the same dump — these are kthreads parked on
  `wait_for_completion` (idle wait), a known detector false positive.
  Do not cite them as TEE evidence.
- Recovery log corroborates: turner-setup's `start_service` polls TIMED OUT
  for both keymint and gatekeeper (30 s each, lines 1602/1604); metadata
  decrypt failed before any PIN was tried (line 192); the GUI Decrypt op
  ended with almost no crypto trace. "凭据不正确" is a downstream symptom —
  no credential was ever actually verified.

## 2. What was checked locally (and ruled in/out)

- **Library FILES are all present on paper.** DT_NEEDED of the OS4
  binaries (`decrypt-stack/bin/`, extracted from the OS4 vendor.img):
  keymint needs 24 libs incl. libtrusty, libcppbor_external,
  libcppcose_rkp, libkeymaster_messages/portable, libpuresoftkeymasterdevice,
  libcrypto, libhidlbase, libbinder_ndk; gatekeeper needs 12.
  Installed OS4 `/vendor/lib64` has every one EXCEPT libbinder_ndk,
  liblog, libc++ — and those three exist in the ramdisk `/system/lib64`,
  which is FIRST in the services' LD_LIBRARY_PATH. So a missing FILE is
  unlikely. A missing SYMBOL in a ramdisk-first copy (libbase/libutils/
  libcrypto/libhidlbase/libbinder_ndk from the stock-recovery ramdisk vs
  the installed-system generation the vendor libs were built against) is
  NOT ruled out — and a linker failure exits 1 in milliseconds with the
  reason on stderr, which init discards and logd (down) never records.
  That matches the observed signature exactly.
- **F1 carries NO VINTF manifests for these HALs.** `stage6/f1_v22/
  system/etc/vintf/manifest/` contains ONLY
  `android.hardware.fastboot-service.example.xml`; there is no
  `vendor/etc/vintf/` in F1 at all. The comment in `stage2/
  hybrid-services.rc` claiming "the payload ramdisk carries the three
  AIDL manifest copies" is WRONG for the shipped v2.2. The installed
  vendor ships all four (56 manifest files incl. manifest.xml). But
  servicemanager started at boot (~t=1 s), BEFORE turner-setup mounted
  /vendor (~t=5–10 s, tee-supplicant boottime 5.3 s, keymint 10.3 s), so
  it plausibly cached a manifest set with no vendor HALs. Whether it
  re-reads after the mount is untested — a 30-second live test (below).
  a7's F1 has the same gap (only the fastboot example) — shared, not
  hybrid-specific. Whether a7's keymint also exit(1)s is UNKNOWN (no a7
  diag was ever pulled).
- **Prop alignment silently failed.** `prop.default`/`default.prop` in
  v2.2 F1 say `ro.build.version.release=15`; the installed OS4 ROM reads
  `17` (recovery log: read from `/mnt/system/system/build.prop`). The
  ramdisk has NO `resetprop` binary, so turner-setup logged "no resetprop
  and setprop refused" for all three props. Patch levels already match
  (2026-10-01 both sides), so the only stale prop is the release number.
  This cannot cause exit(1) (it bites later, at blob binding), but it is
  a real v2.3 fix: bake 17 into prop.default at build time.
- **persist mount failed in setup.** Recovery log line 183:
  "TURNER-SETUP: cannot mount persist" — the fdsd key store
  (`/mnt/vendor/persist/data|fdsd`) therefore sits on the rootfs, not the
  real persist partition. Cause unknown (by-name path? fstype?); needs the
  mount error from the live tablet. Secondary suspect, not the exit(1)
  cause on its own (touchfeature doesn't use persist).
- **Stock rc files (OS4 vendor.img, via dump_files.py):** keymint runs as
  `user system / group system drmrpc`, gatekeeper as `user system`,
  tee-supplicant (stock name has NO `vendor.` prefix) as `user system`.
  The hybrid runs all three as root — a superset, not a plausible
  exit(1) cause. No `seclabel`/`socket` in stock that the hybrid dropped.
- **touchfeature binary DT_NEEDED NOT checked**: extracting it from
  odm.img needs `dump.erofs`, which is not installed here. Its exit(1)
  may be independent (the xiaomi_touch_turner.ko insmod failed in setup,
  line 187 — its /sys nodes may be missing). Touch works without it
  (driver-level events), so it is P2 behind keymint/gatekeeper.

## 3. Decisive live test (no rebuild — run while the tablet is still in v2.2 recovery)

Run the keymint binary by hand so its stderr is visible (init discards it,
logd is down — this is the ONLY way to see a linker error):

```
export HOME=/data/data/com.termux/files/home
/data/data/com.termux/files/usr/bin/adb shell "LD_LIBRARY_PATH=/system/lib64:/system/lib64/bootstrap:/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex/com.android.i18n/lib64:/apex/com.android.runtime/lib64:/apex/com.android.runtime/lib64/bionic:/vendor/lib64:/mnt/system_ext/lib64 /vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee; echo EXIT=\$?"
```

Read the output:
- `CANNOT LINK EXECUTABLE ... library ... not found` / `cannot locate symbol ...`
  → linker failure; the named lib/symbol is the v2.3 fix (swap that lib's
  load order to the installed-system copy, or ship the missing lib).
- `Could not find ... in the VINTF manifest` / registration failure
  → manifest-timing cause; go to test 2.
- Silent exit 1 → main() returned 1 on a failed early check (persist/
  fdsd dir? /dev/tee0? ro.hardware.gatekeeper prop?); try test 3 then
  strace-equivalent probing.
- Hangs (registers and waits) → the binary is FINE standalone and init's
  environment (seclabel/caps/working dir) is the difference.

Test 2 — servicemanager manifest refresh (only if test 1 points at registration,
or if test 1 hangs but init-started services still loop):

```
/data/data/com.termux/files/usr/bin/adb shell "setprop ctl.restart servicemanager; sleep 5; getprop init.svc.vendor.keymint-mitee; getprop init.svc.vendor.gatekeeper_mitee"
```

If either flips to `running`, the cause is servicemanager caching the
pre-mount manifest set; v2.3 must carry the manifests in the ramdisk
(see §4a) and/or restart servicemanager after the vendor mount.

Test 3 — persist mount error (secondary, do any time):

```
/data/data/com.termux/files/usr/bin/adb shell "ls -la /mnt/vendor/persist/; ls -l /dev/block/bootdevice/by-name/persist; mount -t ext4 /dev/block/bootdevice/by-name/persist /mnt/vendor/persist"
```

Report the mount error verbatim.

## 4. v2.3 fix list (staged in ~/workspace/yarp-hybrid/stage7/)

Staged and verified this run; build only AFTER the live test answers §3
(the manual run may change which of (a)/(b) matters most, but both are
safe to ship regardless):

- (a) `stage7/manifests/` — the 4 manifest XMLs extracted from the
  installed OS4 vendor.img (original bytes, dump_files.py/erofs_read.py):
  keymint-service.mitee (527 B; IKeyMintDevice + IRemotelyProvisionedComponent),
  secureclock-service.mitee (318 B), sharedsecret-service.mitee (321 B),
  gatekeeper-service.mitee (305 B). Copy into the ramdisk
  `system/etc/vintf/manifest/` (currently only the fastboot example).
  This is what the a7 toml comment prescribes and the hybrid rc comment
  wrongly claimed was already done.
- (b) `stage7/libkmsglog.so` — 13,904 B, sha256
  `0454981809157d050f5770bd215563e19b9788a635bf34a2d162746d782443d1`,
  copied from the a7 extraction (`x_a7_f1/skyward/libkmsglog.so`,
  KPad-verified bytes per the user's rule). LD_PRELOAD it for the three
  services (as the a7 toml does) so the next LOG(FATAL)/CHECK failure
  lands in kmsg even with logd down. The hybrid deliberately omitted it;
  that omission is why this failure has no stated reason.
- (c) Bake `ro.build.version.release=17` (and `release_or_codename` /
  `release_or_preview_display`) into the ramdisk `prop.default` /
  `default.prop` at build time (installed-ROM value, verified from the
  recovery log). Do NOT rely on resetprop — the binary doesn't exist in
  recovery. Patch levels already agree (2026-10-01).
- (d) Fix or log the persist mount: capture the mount error (test 3)
  before changing the mount command (fstype/by-name path).

## 5. What NOT to claim

- Do NOT claim the TEE is wedged (see §1 mitee_worker note).
- Do NOT claim a7 shares the exit(1) — only the decrypt-failure symptom
  is shared; a7's service states were never captured.
- Do NOT claim the linker is the cause until the manual run prints it —
  it is the best-fitting hypothesis for a 3–6 ms exit(1) with zero trace,
  not a verdict.
- The "凭据不正确" PIN rejection is NOT a credential verdict: no
  credential was ever verified (metadata decrypt failed first, HALs down).
  Do NOT tell the user to change the lock-screen password yet — that step
  only makes sense once keymint/gatekeeper actually reach `running`.
