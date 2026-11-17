# v3.18 FLASH VERDICT — 2026-11-16 14:08 CST (logs received, tablet ✓)

Source logs: `~/workspace/user/files/recovery-v318_0_h12y.log`
(67,363 B), `~/workspace/user/files/dmesg-v318_1_9zoy.txt`.
User sent both at 06:08 UTC after the 06:03 request; no assistant reply
had been sent as of the 06:32 research snapshot.

## Verdict

Official YARP keystore2 + full payload binder pair **loads cleanly
(CANNOT LINK = 0) but segfaults identically**: `SIGSEGV SEGV_MAPERR,
fault addr 0x0` in the binder pool thread (`binder:595_2`), ~1 ms after
"Starting thread pool now", before any KeyMint handshake. Crash-loops
on every supervisor respawn (19× Fatal signal 11 in dmesg;
`keystore.crash_count=4`; pids 595, 642, 710, …).

Sequence per spawn (dmesg 16.277–16.279 s):
- "Keystore2 is starting." → sqlite logging set up → maintenance thread
  waits on `apexd.status` (absent, expected) → "Starting thread pool now."
- binder thread 600 starts (`globals.rs:474` monitoring
  `sys.boot_completed=1`) → tid 601 SIGSEGV addr 0x0.
- At the same instant: `ServiceManagerCppClient: Waiting for service
  'android.security.compat' on '/dev/binder'...` — keystore2 was
  looking up android.security.compat when the binder thread died.
- init: "Untracked pid 595 … did not have an associated service entry".

## What this rules out

- The segfault is **not** specific to the installed SDK37 keystore2
  (v3.16/17) nor to the split binder pair: the official binary on the
  full payload pair dies the same way, in the same thread, at the same
  point. v3.16's installed binary actually got further (reached the
  KeyMint "current version (Some(300))" handshake before dying);
  v3.18 dies before it.
- The trace-file theory stays dead (v3.17); the ICU/APEX theory stays
  dead (v3.15); the link theory stays dead (v3.16/18 both link).
- Common factor across v3.16/17/18: keystore2 is spawned **outside
  init** (supervisor shell via spawn_hal). The one environment
  variable never yet tried for keystore2 is a proper init service —
  which is exactly what the official rc does, including
  `rlimit memlock unlimited` (spawn_hal cannot raise rlimits).

## Everything else in v3.18 healthy

- keymint supervisor-spawned pid 551 alive; gatekeeper pid 555 alive;
  touch HAL registered; touch modules loaded (panel 1880×3008);
  i18n APEX mounted, libicuuc present.
- Only failure: keystore2 → `step:done WITH FAILURES: keystore2 —
  setup.done NOT set` → "Unable to decrypt metadata encryption".

## v3.19 (stage35, built 06:10 UTC by the live session)

`~/workspace/yarp-hybrid/stage35/turner-vendor_boot-hybrid-v3.19.img`
- 67,108,864 B, sha256
  `b615b386e3a10b62bff94af04a0a8274984424258d8e44b64276a0f7b3182d7b`
- F0 lz4 sha identical to v3.18 (`ac41ecd2…`) — F0 untouched.
- F1 delta vs v3.18 = exactly {`system/etc/init/hybrid-services.rc`,
  `system/bin/turner-setup.sh`} (verified by tree diff).
- Change: keystore2 becomes a real init service `vendor.keystore2`
  (official rc shape): `rlimit memlock unlimited unlimited`,
  `LD_LIBRARY_PATH ks2lib:twrp16:/system/lib64`,
  `LD_PRELOAD liblogcapture+libkmsglog`; setup starts it and
  `svc_check`s it. HALs untouched.
- Header `VNDRBOOT`, AVB0 magic at offset 61394944 — same assembly
  path as v3.18, which flashed and booted.

Next flash: `fastboot flash vendor_boot <v3.19>`, recovery, wait 20 s,
pull `dmesg-v319` + `recovery-v319`. Discriminator: if keystore2
survives past "Starting thread pool now" and reaches the KeyMint
handshake, the init-service/memlock theory is confirmed; if it dies
identically, spawn environment is exonerated and the fault is inside
the binder pool itself (next: strace-equivalent / a binder-pool
workaround, or keystore2 bypass via vold's keymaster path).
