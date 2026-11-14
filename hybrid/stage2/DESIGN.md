# Stage 2 — Design: YARP × Skyward hybrid recovery for turner

Status: DRAFT for review. Deliverables of this stage:
`turner-setup.sh`, `hybrid-services.rc`, this document. No image was
assembled; nothing outside `stage2/` was modified.

Inputs: a7 `device.toml` (proven orchestration, source of truth per the
user's rule), `piano-setup.sh` / `piano-stage.sh` (runtime pattern),
stage-1 trees + REPORT, OS4 service-layout audit (all toml paths verified
present on OS4).

## 1. Architecture in one paragraph

The hybrid F1 is the stage-1 TWRP payload (the v5iso-verified F1 tree)
plus two files: `system/bin/turner-setup.sh` and
`system/etc/init/hybrid-services.rc`. At `on boot`, init starts the
`turner-setup` oneshot. The script mounts the installed vendor/odm at
their canonical points and the installed system/system_ext at
`/mnt/system` / `/mnt/system_ext` (the extra points the toml's library
lists name), reads the installed ROM's OS version and patch levels and
resetprops them, mounts persist + metadata, loads the touch module from
the installed vendor_dlkm, stages device-node owners, and then starts —
in the toml's order, with the toml's waits — tee-supplicant, KeyMint,
Gatekeeper and the Xiaomi touch HAL, all running the **installed
system's binaries** with the toml's per-service `LD_LIBRARY_PATH`
reproduced as `setenv` in `hybrid-services.rc`. TWRP then finds
`IKeyMintDevice/default` and `IGatekeeper/default` already registered
on /dev/binder when the user enters the lock-screen credential.

## 2. Decisions

### 2.1 Services run in place from the installed partitions (not ramdisk copies)

The payload already carries ramdisk copies of the whole mitee stack in
`/vendor/bin{,/hw}` plus `vendor/mitee/ta` and 9 vendor libs — and,
verified in this stage, **all three service binaries are byte-identical
to the installed OS4 ones** (tee-supplicant `f4c6911c…`, keymint
`7fdd096e…`, gatekeeper `68e24c8b…`, matching the OS4 audit exactly;
the copies are OS3.0.310-era and OS4 did not change them). Running the
installed binaries anyway, for three reasons:

1. It is the proven pattern on this device (Skyward/a7) and the parent
   design's locked direction; the ramdisk copies exist only because the
   original TWRP tree bundled them, with their rc files zeroed out in
   the v5 merge — they were never a running configuration.
2. In-place execution tracks future OTAs for free (binaries, TAs and
   libraries all come from the same installed build — no mixed
   generations inside one service's closure).
3. The byte-identity means the fallback is free: if an installed binary
   ever fails to start, stage 3 can flip the rc path to the ramdisk
   copy without new provenance work. Not the default.

The piano `/twrplib` bind-mount trick is **not** adopted: it exists
because piano's services run *ramdisk* binaries that TWRP would kill
when it mounts the installed partitions over `/vendor` and `/odm`.
Ours run the installed binaries, so being mounted over is the desired
end state, not a hazard. (Residual interaction noted as risk R4.)

### 2.2 The KeyMint patch-level alignment (the piano lesson)

KeyMint binds key blobs to the OS version and patch levels presented
when it runs; on mismatch it refuses the blobs (or, worse, upgrades
them). The payload's build-time props present the OS3.0.310 build
(fingerprint `OS3.0.310.0.WAOCNXM`, `ro.build.version.security_patch =
2026-08-01` in `prop.default`), while the installed OS4 ROM is at patch
**2026-10-01**. Without correction, KeyMint/TWRP would present stale
levels and decrypt would fail. `turner-setup.sh` therefore resetprops
exactly the three properties piano-setup.sh sets, from the same
sources, before KeyMint starts:

| property | read from |
|---|---|
| `ro.build.version.release` | installed system `build.prop` |
| `ro.build.version.security_patch` | installed system `build.prop` |
| `ro.vendor.build.security_patch` | installed vendor `build.prop` |

If a read fails, the build-time value stays — and because the fallback
(2026-08-01) is *older* than the installed ROM's level, the failure
mode is "decrypt refused", never "keys silently upgraded" (piano's
deliberate-old-fallback principle, satisfied by the existing payload).

This is also the leading theory for the user-reported a7-on-OS4
decrypt failure (2026-11-14): Skyward 0.1.2 has no equivalent of this
alignment step. It remains a theory until a hybrid first flash — see R1.

### 2.3 Touch module: load from the installed vendor_dlkm (runtime)

**Decision: runtime load wins; a bundled copy is only a fallback.**
Rationale:

- **Kernel match by construction.** The hybrid boots whatever stock
  kernel the installed ROM ships (F0 is the installed generation's own
  first stage). A module taken from the *installed* vendor_dlkm always
  matches that kernel's vermagic; a bundled OS4 `.ko` would break
  silently on the next kernel-changing OTA. This is exactly why piano
  uses `TW_LOAD_VENDOR_MODULES` (loads from the installed vendor_dlkm)
  and why Skyward's `[modules]` lists `vendor_dlkm` among its sources.
- **Dependency handling exists there.** The installed vendor_dlkm
  ships `modules.dep` / `modules.load` / `modules.softdep` (verified
  present in the OS4 image); the script tries `modprobe -d` first,
  then a dependency-ordered `insmod` driven by `modules.dep` itself —
  no hand-maintained dep list to rot.
- The toml loads only `nt36536e_touch_turner`; `xiaomi_touch_turner.ko`
  and `touch_boost.ko` are explicitly not needed for basic touch.

Fallback (only if vendor_dlkm cannot be mounted at all): insmod
`/system/etc/hybrid/nt36536e_touch_turner.ko`, a copy extracted from
`~/workspace/skyward-turner/os4/vendor_dlkm.img`. Stage 3 must pin its
size/sha256 in the merge report when extracting it (extraction was not
re-run in this stage: the only `dump.erofs` copies on this VM are ARM
builds from the ramdisks and do not execute here; the audit already
verified the file's presence at `/lib/modules/nt36536e_touch_turner.ko`
in the OS4 vendor_dlkm). The script logs loudly when the fallback is
used, because a vermagic mismatch there means "touch dead until the
primary path is fixed", not a silent degradation.

### 2.4 Service identities: stock names, toml privileges

Init service names are the stock ones from the OS4 rc files
(`vendor.tee-supplicant`, `vendor.keymint-mitee`,
`vendor.gatekeeper_mitee`) so anything that polls `init.svc.*` or
reproduces stock `enable` chains behaves as in Android. Privileges are
the toml's, not the stock rc's, where they differ — concretely
tee-supplicant and KeyMint run as **root** (stock rc: `system`): the
toml's reason is device-measured (`/odm/mitee/ta` is root-owned; a
system supplicant fails with "loading ta … failed"), and the toml is
the proven source of truth on this device. The touch HAL's init name
(`vendor.touchfeature`) is ours — nothing else references it, and the
setup script starts it by that name.

All four services are `disabled` in the rc. This is load-bearing:
`hw/init.rc` runs `class_start default` and `class_start hal` at
`on boot`, and KeyMint is class `early_hal` in stock; without
`disabled`, class start could fire services before the patch-level
props are aligned and before tee-supplicant is serving. Explicit
`start` by the setup script (piano's `start_service` retry pattern,
30 × 1 s, absorbing TWRP's transient mount-over refusals) is the only
start path.

### 2.5 SELinux label: `u:r:recovery:s0` for all four services

The F1 sepolicy is the stock recovery policy, which has no reason to
contain the Android vendor-HAL domains for mitee services; the one
domain guaranteed present and able to run daemons is `recovery`
(the TWRP service itself runs under it). All hybrid services therefore
get `seclabel u:r:recovery:s0`. Their unix user/group and capabilities
still follow the toml. Whether the recovery domain may ioctl the TEE
devices is a first-flash question (risk R3); the alternative (adding
policy) is impossible in a repack — there is no sepolicy compiler in
the pipeline — so if the label is wrong, the fix is a different
existing domain, chosen from the first boot's denial log.

### 2.6 What was deliberately NOT carried over from the toml

- `LD_PRELOAD=/skyward/libkmsglog.so` — the shim ships with the
  Skyward binary package; it does not exist in the hybrid F1. Services
  log via the normal logd/kmsg path. (If first-flash debugging needs
  it, the file can be lifted from the a7 extraction
  `x_a7_f1/skyward/libkmsglog.so` under the user's extracted-original
  rule — noted as an option, not in the draft.)
- `ready_service` / `registers` — not configuration: the names
  register because the HAL binaries register them, provided
  servicemanager can see all three KeyMint VINTF manifests. That
  visibility is doubly covered: the payload ramdisk already carries
  the AIDL manifest copies (`vendor/etc/vintf/manifest/`:
  keymint/secureclock/sharedsecret/gatekeeper `-aidl.xml`), and the
  installed vendor ships its own set, which the OS4 audit verified
  file-by-file.
- `[update] server`, `[display]`, `[device]` — Skyward-UI concerns,
  not init concerns.

## 3. Stage-3 merge plan (exact)

Base principle (v5iso recipe, stage-1 verified): the payload tree *is*
the v5iso F1 — its merge winners are already decided and byte-verified
against the shipped image. Stage 3 does not re-merge from scratch; it
starts from the payload and applies the deltas below.

**F0 (from `stage1/os4_f0/`, OS4 stock):**

1. DTB, kernel, first-stage modules, cmdline: verbatim, no edits.
2. `system/lib64/twrp16/`: add the TWRP-private library set (the v5iso
   F0 addition; source them from the v5 F0 tree retained in
   `stage1/_src/` — the F1 payload has no `twrp16/` directory, it
   lived on the F0 side).
3. `system/etc/init/hw/init.rc`, `service recovery` block (line ~95):
   add the one line `setenv LD_LIBRARY_PATH /system/lib64/twrp16:/system/lib64`
   — the v5iso isolation, and the **only** content edit inside F0.
   Everything it protects (init's own closure) stays stock OS4 builds,
   per the v5 symbol-pairing lesson.
4. Nothing else. In particular the OS4 `servicemanager.recovery.rc`
   stays as-is and **no vndservicemanager service is added anywhere**
   (OS4 recovery init does not start one; §2 of the audit + a7's
   SIGABRT finding agree).

**F1 (from `stage1/twrp_payload/`):**

Wins (payload over everything): `system/bin` (TWRP set, with the v5
recipe's exclusions already embodied — stock `init`/`linker64`/`adbd`/
`toybox` were kept by the original merge, stock `fastbootd` kept),
`system/lib64` (TWRP builds, incl. its `libcrypto.so`; the stock
libcrypto pairing lives on the twrp16/F0 side), `res/`, `twres/`,
`init.recovery.mt8799.rc` (already carries the `enable_touch_raw 0`
write), `system/etc/recovery.fstab`.

Additions (new files only):
- `system/bin/turner-setup.sh` (mode 0755) — this stage's draft.
- `system/etc/init/hybrid-services.rc` — this stage's draft. (The
  payload's `system/etc/init/` currently holds only the stock fastboot
  example rc; recovery init parses this directory.)
- `system/etc/hybrid/nt36536e_touch_turner.ko` — the §2.3 fallback,
  extracted from the OS4 vendor_dlkm image, sha256 pinned in the
  stage-3 merge report.
- Optional, only if first-flash logs demand it:
  `skyward/libkmsglog.so` from the a7 extraction + the rc `setenv
  LD_PRELOAD` lines.

Kept as-is, deliberately:
- `vendor/etc/init/*.rc` stay **0-byte** (their state in the payload).
  They must not resurrect the stock service definitions: those would
  start the services with stock users, no library isolation and no
  ordering. Our definitions live in `system/etc/init/` instead.
- `vendor/bin{,/hw}`, `vendor/mitee/ta`, `vendor/lib64` (9 libs),
  `vendor/etc/vintf/manifest/*` — the bundled mitee stack stays as the
  §2.1 fallback material and manifest backstop; it is shadowed by the
  installed partitions once mounted, which is fine (byte-identical).
- `prop.default` — its OS3.0.310 fingerprint/patch values stay as the
  deliberate-old fallback (§2.2). Stage 3 should *not* "refresh" them
  to OS4 values: a too-new fallback is the dangerous direction.

Reference-only: `stage1/os4_f1/` (OS4 skeleton) is not merged in. Two
stage-3 checks against it are required before assembly:
(a) diff `sepolicy` and the `*_file_contexts`/`*_property_contexts`
between os4_f1 and the payload (they **differ** — verified in this
stage); prefer the OS4 versions for any file the TWRP merge did not
intentionally change, because the hybrid boots the OS4 kernel/userland
generation. If the diff is large, escalate rather than guess.
(b) confirm no OS4 F1 skeleton file exists that the payload lacks and
the TEE/touch flow needs (the audit's F1 comparison says the skeleton
shape is unchanged from OS3; expected outcome: none).

**Verification gates for stage 3** (carry over the project rules):
F0 tree diff vs `stage1/os4_f0/` shows exactly the two intended deltas
(twrp16 add + one rc line); init-closure and hwservicemanager-closure
symbol audits re-run against the merged tree (the v5 defect class);
image structure vs OS4 stock (header, table, DTB byte-identical,
lz4-legacy fragments, AVB hash footer); first flash in daylight with
the 追梦 OS4 vendor_boot at hand and misc BCB cleared first.

## 4. Reconciling with TWRP 16's own crypto flow

What TWRP 16 (this payload) expects, from the payload itself:

- The recovery binary links the AIDL NDK stubs
  (`android.hardware.security.keymint-V4-ndk`,
  `android.hardware.gatekeeper-V1-ndk`, secureclock/sharedsecret stubs
  are all in `system/lib64`) and contains the GateKeeper password-key
  logic (`/data/system/users/0/gatekeeper.password.key`, auth-token
  handling strings). It is a *client*: it looks the HALs up on
  /dev/binder's servicemanager by AIDL fqname
  (`android.hardware.security.keymint.IKeyMintDevice/default`,
  `android.hardware.gatekeeper.IGatekeeper/default`). It does not
  start HALs itself and does not mandate init service names — the
  contract is simply "registered before the credential is entered".
  Our stock-named services + boot-time start satisfy it with margin.
- Metadata decryption comes first in TWRP's flow and needs KeyMint
  only; user decryption then needs GateKeeper + KeyMint. The setup
  script's order (tee → keymint → gatekeeper) matches that dependency
  order (and piano starts KeyMint first for the same reason).
- TWRP reads the patch-level properties when forming KeyMint calls;
  §2.2's resetprops therefore serve both consumers (the HAL process
  and the TWRP client) from one alignment step.
- No Weaver on this device: turner's credential chain is the mitee
  Gatekeeper (no `libmi_weaver` — that is a Qualcomm/piano concern).
  Nothing to start, nothing to select.
- One race to be aware of: TWRP starts its GUI immediately and may
  attempt metadata decrypt before `turner-setup` finishes (the whole
  chain takes ~10 s of mandated waits). TWRP re-runs the decrypt flow
  on each credential attempt, so the user-visible worst case is "first
  PIN entry too early fails, second succeeds". Acceptable for v1;
  if it bites, the lever is an earlier trigger for the oneshot
  (`on late-init` + the script's own mount waits), not shorter waits.

## 5. What init rc cannot express (and where the script covers it)

| toml / piano element | why rc can't | covered by |
|---|---|---|
| `wait_ms` sequencing + start retries | rc has no conditional wait on `init.svc.*` with retry | `start_service()` + `sleep 4/5` in turner-setup.sh |
| `ready_service` registration polling | shell cannot query servicemanager | proxy: `init.svc` running + the toml's fixed waits; final proof is TWRP's own lookup |
| persist `[[owners]] create=true` after a late mount | rc `mkdir` runs at fixed triggers, before persist is mounted | script §3 (mount, mkdir, chown, chmod) |
| `[partitions]` mounting (metadata/persist/nvdata semantics) | recovery fstab does not mount persist for the TEE chain | script §1/§3 ensure-mounted logic. (nvdata is *not* mounted: Skyward mounts it for its own modem/NVRAM features; nothing in the TEE/touch flow reads it. Flagged, not copied.) |
| Per-ROM prop values | rc `setprop` is static and cannot read files | `read_prop`/`set_prop` (resetprop) in the script |
| Module loading with dependency resolution | rc has no insmod-with-deps primitive at this trigger level | `load_touch_module()` (modprobe → modules.dep order → bundled fallback) |
| Node staging *after* driver probe/HAL start | `on boot` chown runs before the nodes exist | rc first pass + script re-staging after HAL start |

## 6. Open questions / risks

- **R1 — TWRP ↔ mitee KeyMint has no precedent, and a7 already failed
  decrypt on OS4.** The hybrid removes the two known structural causes
  (no patch-level alignment in Skyward 0.1.2; library-generation
  mixing), but if the a7 failure turns out to be the
  credential-regeneration issue from the upstream community (keys need
  one lock-screen password change inside OS4 after the OS3→OS4
  upgrade), *no recovery build* will decrypt until the user does that
  once. First-flash interpretation must keep these causes separate:
  check the kmsg/recovery log for patch-level complaints vs.
  gatekeeper auth failures before changing anything.
- **R2 — libbinder RECO/SYST.** The OS4 audit could not find the
  marker literally in any libbinder; the working split (TEE services
  on installed-system libs, touch HAL on ramdisk-libbinder-first,
  TWRP client on ramdisk libs) is inherited from the toml unchanged.
  If KeyMint registration or TWRP's first KeyMint call aborts with a
  parcel-header mismatch in the log, this is where to look; the
  candidate lever is giving the keymint service the touch-HAL-style
  library order. Not pre-applied: the toml's order is the proven one
  and pre-changing it would discard evidence.
- **R3 — SELinux.** `u:r:recovery:s0` for vendor services is a
  reasoned default, not a verified one (§2.5). First-flash denial
  lines in kmsg decide; also possible: the whole recovery runs
  permissive enough that this never matters.
- **R4 — mount-over interactions.** Services execute from the mounted
  installed /vendor and /odm; a later TWRP operation that unmounts or
  remounts them (e.g. flashing a vendor image) can find them busy.
  Decrypt happens before such operations in practice. If it bites,
  the fix is stopping the four services on TWRP's mount transitions —
  a stage-4 concern, noted now.
- **R5 — APEX availability.** The toml library lists reference
  `/apex/com.android.runtime` and `/apex/com.android.i18n` — in the
  hybrid those are the recovery's own activated APEX mounts. TWRP
  activates them early (its FBE flow needs them), and turner-setup
  starts services at `on boot`, after apexd; but this ordering has
  never been observed on this device. Missing APEX dirs degrade
  gracefully (the linker skips nonexistent search paths; the bionic
  libs also exist under the bootstrap entries) — flagged for the
  first-flash log check.
- **R6 — mount state at `on boot` is assumed, not observed.** v5iso
  never reached userspace, so nobody has seen this ramdisk's actual
  mount table at setup time. The script is written defensively
  (checks `/proc/mounts`, mounts what is missing, tolerates EBUSY),
  but the first flash should capture `mount` output + the setup log
  (`turner-setup:` lines in kmsg / /tmp/recovery.log) before judging
  any downstream failure.
- **R7 — gatekeeper service name in the toml's ready check.** The
  toml itself warns its gatekeeper `ready_service` string came from a
  Skyward source constant and a mismatch "only logs a kmsg". Our
  contract is with TWRP's lookup of `IGatekeeper/default`, which the
  OS4 VINTF manifest confirms — no action, just don't chase the toml
  string if logs disagree.

## 7. File list (this stage)

- `turner-setup.sh` — boot-time oneshot (mounts, prop alignment,
  persist/metadata, module load, owner staging, ordered service
  starts). POSIX sh, follows piano-setup.sh patterns throughout.
- `hybrid-services.rc` — four `disabled` service definitions with
  toml-verbatim `LD_LIBRARY_PATH` setenv lines + the `turner-setup`
  oneshot, its `on boot` start, the a7-parity `/data/vendor` mkdirs
  and the first-pass node staging.
- `DESIGN.md` — this document.
