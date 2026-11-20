# Turner installed-ROM runtime isolation (development candidate)

This directory addresses a reproducible installation hazard in the published
YARP v1.0 hybrid image. TEE, KeyMint, Gatekeeper, touch, vibration, and keystore2
load their executables, libraries and data from vendor, odm, system, and
system_ext. Their supervisors continue restarting them. The original mounted
filesystems therefore remain in use when a full-Super installer needs to release
them. Merely killing a child process or changing block-device read-only flags
does not remove this dependency.

## Candidate behavior

Before starting dependent HALs, snapshot those four exact installed logical
partitions into recovery tmpfs and attach read-only loop devices. Replace their
canonical mounts with the verified snapshots, then create a private mount
namespace. Start the original six services inside that namespace using their
existing library ordering and supervisor scripts. Public mounts can subsequently
be unmounted normally while services continue using RAM snapshots. They never
remount an old mapper after a Super overwrite. The ICU APEX is staged in RAM
before namespace creation. A missing dependency or insufficient RAM fails closed.

The namespace helper must be statically linked: tee-supplicant's service-level
LD_LIBRARY_PATH selects installed-system libc, which is unsuitable for an
intermediate recovery-linked executable. Its constrained init capability list
also needs SYS_ADMIN and SYS_CHROOT for setns and SYS_PTRACE for inspecting the
keeper through procfs. Other service definitions keep their original identities.

The included repacker accepts only the published v1.0 SHA256. It preserves the
complete F0 fragment, DTB, unrelated CPIO entries and metadata, and rewrites only
five specified F1 paths and the existing unsigned AVB hash descriptor. It accepts
the awk binary extracted from the matching installed system as a build input;
no vendor binary or private capture is checked into this repository.

## Validation performed

Hardware: Redmi K Pad / Turner, 12 GiB RAM, OS4.0.3.0.XAOCNXM, current slot A.
The candidate was read back by SHA256 after installation to vendor_boot_a.

- Clean recovery boot: staging ready, namespace ready, setup done=1; TEE running.
- Existing data automatically decrypted and mounted; no credentials were supplied.
- Touch driver input nodes and all dependent HAL processes present. Physical
  touch response after the patch still needs user verification.
- Normal unmounts of vendor, odm, /mnt/system_ext and /mnt/system succeeded.
  Private service mounts remained read-only RAM loops, with all six services alive.
- Real recovery ORS install path: updater exits 0, 37, and 0 were correctly
  displayed; the failure did not prevent a subsequent successful installation.
  The ORS transport itself returns EOF, not the updater's numerical exit status.
- awk remained executable after public vendor was unmounted.
- Existing LK and preloader A/B plus vendor_boot_b matched pre-test hashes before
  candidate installation. Final post-test protection hashes remain pending.
- Recovery backlight was explicitly verified as 0 during service debugging.

Four snapshots occupy 5,166,112 KiB (about 4.93 GiB); copying took roughly 6.4
seconds in a clean boot. About 5.7 GiB remained available afterward. This is a
correctness-first prototype, not a memory-optimized release. The script enforces
1.5 GiB of available-memory headroom and tmpfs capacity checks. Smaller-RAM
devices, other firmware, ext4 logical partitions, low-memory handling, interrupted
staging cleanup, and changes in service dependencies need further review.

## Outstanding acceptance gates — do not release yet

A later live display-library experiment stopped the recovery service while
MTP+ADB was active. USB then disappeared and did not re-enumerate; no subsequent
device-side observation was possible. This experiment did not flash a display
patch to vendor_boot. The persisted image remains the runtime-only candidate.
The recovery-service restart/USB lifecycle must be investigated separately;
do not infer that the display patch executed or that the tablet rebooted.

Pending: recover physical access, Android round trip, final screen-off check,
final protected-partition hashes, physical touch, explicit HAL restart after
public unmount, BootControl, ZIP64 and full-Super streaming validation. No full
ROM or Super write was performed. Keep this change as a draft until these pass.

## Display investigation

Read-only DRM queries report active 1880x3008 at 60 Hz and available modes of
165, 144, 120, 90, 60, 50 and 48 Hz. The published library forces legacy KMS for
MTK, which bypasses both the existing opt-in fast-mode selection and the optional
cached RAM drawing path. The two exact-build changes in patch_display.py map to
display-source.patch. They are experimental, excluded from repack.py, and have
not been validated on hardware. Raising panel Hz alone does not establish GUI FPS.

## Build and host checks

Compile turner-runtime.c using Android NDK aarch64-linux-android28-clang with
-O2 -Wall -Wextra -Werror -static. Python requires lz4. Run:

    python -m unittest discover -s hybrid/runtime-isolation -p test_repack.py
    python hybrid/runtime-isolation/repack.py --base published-v1.0.img \
        --runtime turner-runtime-static --awk matching-system-awk --out candidate.img

The repacker prints a manifest. Device installation is deliberately separate.
Keep a verified original vendor_boot backup and a wired recovery path. Never
write LK, preloader, user data, metadata, or other protected partitions.
