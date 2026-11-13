# Patches: 14.1 tree vs YARP (twrp-16.0) base

The twrp-14.1 minimal-manifest tree carried 8 patches under `patches/`.
Checked one by one against TWRP-Test's `twrp-16.0` branches
(`android_bootable_recovery`, `android_system_vold`, `android_build`,
branch `twrp-16.0`, checked 2026-11-07). Kept patches were test-applied
with `git apply --check` against those branches; dropped ones are listed
with the reason so nobody re-adds them.

## Kept (in this tree)

| Patch | Status on 16.0 |
|---|---|
| `bootable_recovery/0001-drop-git-revision-from-startup-line.patch` | **Re-based.** Same cosmetic fix, new context: the 16.0 startup line uses `TWFunc::GetTwrpVersion().c_str()` instead of `TW_VERSION_STR`. |
| `system_vold/0001-aidl-gatekeeper-and-other-protectors.patch` | **Rewritten for 16.0.** The AIDL Gatekeeper plumbing is already upstream (`Gatekeeper_Verify` tries AIDL first, then HIDL; `gatekeeper-V1-ndk` already linked), so this patch now only carries the turner-specific logic: `unwrapSyntheticPasswordBlob` used the *active* sp-handle for the keystore alias instead of the protector being tried; `Decrypt_User_Synth_Pass` takes an optional `handle_str`; `Decrypt_User_Other_Protectors` retries every protector with Gatekeeper data (`.secdis`) when the active (Weaver/NXP eSE) one fails. |

## Removed after flash testing (do not re-add)

| Patch | Why it was removed |
|---|---|
| `build_make/0001-compress-ramdisk-with-zstd.patch` | **Removed 2026-11-10.** Every zstd-compressed vendor_boot failed on the tablet (black screen / logo loop) on both bases, while both stock ramdisk fragments are lz4 legacy. The bootable route is lz4 throughout (`BOARD_RAMDISK_USE_LZ4`), and the repack route reuses the stock layout as-is; `CONFIG_RD_ZSTD=y` in the kernel config did not translate into a bootable zstd ramdisk. See `MEDIATEK-NOTES.md` section 2. |

## Dropped (already upstream in 16.0 — do not re-add)

| Old patch | Why it is not needed on 16.0 |
|---|---|
| `bootable_recovery/0001-libtar-use-static-fscrypt-policy-api.patch` | Upstream already reverted to the static API: 16.0 `libtar/*.c` use `struct fscrypt_policy_v1/v2`, `system/vold/fscrypt_policy.h` is the static API, and the `TW_USE_FSCRYPT_POLICY` flag is wired through `libtar_defaults.go` / `twrp_flags.go`. |
| `bootable_recovery/0002-link-libvold-dependencies.patch` | The Make `Android.mk` targets are gone (recovery is Soong now) and 16.0 `bootable/recovery/Android.bp` already links `libvold`, `libasync_safe`, `libsysutils`, `android.hardware.gatekeeper-V1-ndk`, `libgatekeeper_aidl`. |
| `bootable_recovery/0003-stub-removed-fde-cryptfs-api.patch` | The FDE calls (`cryptfs_check_passwd`, `delete_crypto_blk_dev`, …) no longer exist in 16.0 `partition.cpp` / `partitionmanager.cpp`. Format Data drops the metadata-encryption dm device with `dmctl delete userdata` instead (`TW_USE_DMCTL := true` in `BoardConfig.mk`). |
| `bootable_recovery/0004-pass-empty-zoned-device.patch` | Upstream fixed the call: 16.0 `fscrypt_mount_metadata_encrypted` takes an explicit `zoned_device` argument and the fstab path is the last argument. |
| `bootable_recovery/0006-keep-data-data-on-wipe-and-backup-once.patch` | Fully upstream and unconditionally enabled: 16.0 `bootable/recovery/Android.bp` defines `-DTW_WORKAROUND_BACKUP_BUG`, and `partition.cpp` already excludes `/data/data` from backups and skips removing it during wipe (same error-255 workaround, same OrangeFox origin). |

## How patches are applied

`.github/workflows/build-twrp.yml` applies `patches/<project>/*.patch` after
`repo sync` and the PR #42 merge, mapping directory names to repo paths
(`bootable_recovery` → `bootable/recovery`, `build_make` → `build/make`,
`system_vold` → `system/vold`). If a patch stops applying after a manifest
update, the build fails at that step — that is the signal to re-check it
here, not to force it.
