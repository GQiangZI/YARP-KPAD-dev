# Turner recovery runtime, display and installer repairs (development candidate)

The published YARP v1.0 hybrid runs TEE, KeyMint, Gatekeeper, touch, vibration
and keystore2 directly from Super-backed logical partitions. Its supervisors
keep those filesystems busy. It also forces direct drawing in the MTK legacy
KMS path, does not start its early_hal BootControl service, and uses a ziptool
stdout implementation that failed the tested member larger than 4 GiB.

## Exact-build changes

- Snapshot the exact installed vendor, odm, system and system_ext images into
  RAM before HAL startup. Verify read-only loop mounts, stage ICU APEX, and
  start the original service chain in a private mount namespace. Public mounts
  can be unmounted normally. Never remount old Super mappers after replacement.
  A verified awk is included in ramdisk. The namespace helper is static.
- Retain MTK legacy KMS but allow cached RAM drawing and the existing opt-in
  fastest same-resolution mode. --display cached60 isolates drawing changes;
  cached-fast enables both. Check the entire original library hash and both
  instructions before applying the exact-build patch.
- --bootctl starts the existing vendor.boot-default service explicitly because
  this recovery only starts default/hal classes, not early_hal. A static client
  launcher clears GUI/installer LD_LIBRARY_PATH and LD_PRELOAD before executing
  the verified client against the stock ramdisk Binder ABI.
- --ziptool and --ziparchive supply the bounded stdout extractor previously
  tested in Turner R97. A static launcher selects a private libziparchive and
  compatible recovery SDK libraries. Other processes keep their libraries.
  unzip/zipinfo aliases preserve argument semantics. The source change is in
  ziptool-streaming-stdout.patch. Binaries are verified build inputs, not checked
  into this repository. CRC and output length are checked during streaming.

The repacker accepts only the published v1.0 base SHA256. F0, DTB and unrelated
F1 entries/metadata stay unchanged. The existing unsigned AVB hash is updated.
Every changed/added path is listed in the manifest. This is not a cross-version
binary patcher. The optional inputs are hash-pinned.

## Hardware validation, 2026-11-20

Turner / Redmi K Pad, 12 GiB RAM, OS4.0.3.0.XAOCNXM, current slot A.
Final candidate rc8 SHA256:
587dbb6d449a92362016a43b82c57bdd29dda22892bf0aeee83062a3a55d8760

Only vendor_boot_a was written and completely read back. F0/DTB were unchanged.
Final vendor_boot_b, LK A/B and preloader A/B hashes matched saved originals.
No complete ROM, Super, userdata or metadata write was performed.

| Check | Observed result |
|---|---|
| Clean boot and existing-data automatic decryption | Passed; setup.done=1, data readable, six services running |
| Active DRM mode after clean rc8 boot | 1880x3008 at 165 Hz |
| Normal public vendor/odm/system/system_ext unmount | Passed; six services kept running from RAM |
| Real ORS updater success / exit 37 / retry | Passed on final rc8 after mount release |
| awk and BootControl after public unmount | 42; current slot 0; snapshot none |
| BootControl startup queries | Current 0, count 2, active 0, snapshot none; no slot mutation tested |
| ZIP64 4,296,015,872-byte deflated member | Full SHA256 matched; exit 0 |
| Small stored and deflated ZIP64 members | Matching SHA256 |
| Corrupt stored-member CRC | Rejected, exit 1 |
| Output consumer closes pipe | Nonzero exit 141 |
| Large-member stdout memory | Maximum sampled RSS 2,212 KiB |
| Android return | boot_completed=1, candidate hash still matches |
| Final screen state | Asleep, display OFF, backlight 0 |

### Display measurements

An independent init-owned harness switched USB to pure ADB before stopping
recovery, bounded each benchmark, restarted recovery and blanked the backlight.
These are rendering/presentation microbenchmarks, not LVGL animation FPS or
human touch acceptance. minui-bench.c must never run beside the active GUI.

| Drawing path | Full-frame gr_blit_raw + flip | Partial-region blit + flip |
|---|---:|---:|
| Original direct, 60 Hz | 33.332 ms / 30.00 FPS | 16.668 ms / 60.00 FPS |
| Cached, 60 Hz | 16.666 ms / 60.00 FPS | 16.666 ms / 60.00 FPS |
| Cached, fastest mode | 6.053 ms / 165.22 FPS | 6.053 ms / 165.22 FPS |

Private dumb-buffer measurements: full-frame RAM-to-DRM 1.856 ms, DRM-to-RAM
20.542 ms, DRM-to-DRM 20.187 ms. The original Flip copies damage between scanout
buffers; cached drawing avoids that expensive readback. A separate scalar-fill
stress test timed out on the original path; do not confuse it with GUI blits.
drm-memory-bench.c only allocates private buffers, without DRM master, modesets
or active framebuffer writes.

## Remaining acceptance gates

Keep the PR draft. Full-Super/complete ROM installation, physical touch response,
sideload/OTG, credential-protected decryption and actual slot mutation remain
unverified. These probes do not certify the whole recovery.

KeyMint, Gatekeeper, touch, vibration and keystore2 restarted successfully after
public unmount. Deliberately restarting TEE did not: /dev/teepriv0 returned EBUSY
in both namespaces, with no remaining userspace fd found. A clean recovery
reboot restored TEE. The exact driver/secure-world cleanup cause is unresolved;
it is not proven to be caused by mount isolation. Keep TEE alive during install,
and never use kill/restart as a mount-release mechanism. The tested normal
release/retry path leaves it alive and passed.

Four RAM snapshots cost 5,166,112 KiB (about 4.93 GiB), take about 6.4 seconds,
and leave about 5.7 GiB available here. Smaller-memory variants, interrupted
staging and other firmware dependencies need review.

An earlier stop-recovery command inside an MTP+ADB shell lost USB before its
remaining commands could be observed. Later tests used an independent init-owned
guard and pure ADB. Do not reuse the unsafe sequence or misreport its outcome.

Existing ROM packages prepend an older bundled libc++ and invoke their own
bootctl. That can break even timeout under GUI SDK libraries. The next explicit
Turner/YARP package profile must select the verified /system/bin/bootctl contract.
Installing this REC does not rewrite existing ZIP updater scripts. Do not
generalize its library paths to Sheng/Byron. Skyward renderer, BootControl and
ZIP handling require separate implementation-specific checks; these offsets
must never be copied across devices or builds.

## Build

Compile turner-runtime.c with Android NDK aarch64-linux-android28-clang:
-O2 -Wall -Wextra -Werror -static

Python requires lz4. Run:

    python -m unittest discover -s hybrid/runtime-isolation -p test_repack.py
    python hybrid/runtime-isolation/repack.py --base published-v1.0.img \
      --runtime turner-runtime-static --awk matching-system-awk \
      --bootctl verified-bootctl --ziptool r97-streaming-ziptool \
      --ziparchive r97-streaming-libziparchive.so --display cached-fast \
      --out candidate.img

Flashing is separate. Keep an original backup and wired recovery path. Never
write LK, preloader or other protected partitions.
