# FBE / KeyMint patch-level and AVB review — blocking risk / 必查风险

> **Static audit only. No change to active build settings yet.**
>
> **Owner-reported device result (2026-11-14): Skyward enters Recovery and display/touch work, but Data decryption fails.** Treat it only as a boot/display/input reference. Exact tested variant, installed firmware and crypto failure logs are not yet established. Do not attribute the failure to MiTEE, Weaver, patch levels or any other component without diagnostic evidence. / 用户实测：Skyward 可启动，显示触控正常，但 Data 解密失败；具体失败阶段和原因尚未确认。
>
> **仅静态风险审查：尚未更改实际构建参数，也不声称发现的问题已造成实际设备故障。**

## Observed values / 已确认的源码配置

The currently imported `BoardConfig.mk` contains:

```make
PLATFORM_VERSION := 99.87.36
PLATFORM_VERSION_LAST_STABLE := $(PLATFORM_VERSION)
PLATFORM_SECURITY_PATCH := 2099-12-31
BOOT_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)
VENDOR_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)
BOARD_AVB_VENDOR_BOOT_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VENDOR_BOOT_ALGORITHM := SHA256_RSA4096
```

It also appends `androidboot.selinux=permissive` to `BOARD_VENDOR_CMDLINE`.

These are imported verbatim from the original turner device tree; they are **not** proof that the values are correct for the installed HyperOS firmware or safe for data decryption.

## New verified AVB evidence from both user-supplied images / 实际镜像 AVB 核查

Both boot-tested Skyward 3.0.306 images have a valid-looking `AVBf` footer at the final 64 bytes, pointing to an `AVB0` vbmeta header:

| Property | Fast and slow images |
|---|---|
| AVB footer version | 1.0 |
| Original image size | 59,207,680 bytes |
| Embedded vbmeta offset | 59,207,680 bytes |
| Embedded vbmeta size | 512 bytes |
| vbmeta algorithm type | **0 = NONE** |
| vbmeta authentication block size | 0 bytes |
| vbmeta rollback index / flags | 0 / 0 |

**Difference from the current device tree:** `BoardConfig.mk` explicitly defines `BOARD_AVB_VENDOR_BOOT_ALGORITHM := SHA256_RSA4096` and `INTERNAL_AVB_VENDOR_BOOT_SIGNING_ARGS := --algorithm SHA256_RSA4096 ...` using an AOSP test key. The known-good Skyward images are **not signed with that algorithm**. This mismatch requires a build-output and boot-chain audit; it does **not** prove RSA4096 images cannot boot on an unlocked device.

严格测试工具 `tools/check_reference_vendor_boot.py` now rejects an exported candidate if its vendor_boot PLATFORM/DTB, required cmdline, or AVB footer algorithm differs from the working Skyward baseline. This is a conservative reference check, **not a security certification**.

## Priority before an image is called safe / 发布前优先处理

**P0 — patch level and OS version consistency:** The synthetic `2099-12-31` security patch and `99.87.36` platform version must be reconciled with real installed firmware properties and KeyMint behavior. Stock KeyMint/Gatekeeper/TEE dependencies and the corresponding Android 16 FBE unwrap flow must be confirmed. Do **not** attempt untested PIN/password decryption with a mismatched key environment on irreplaceable user data. Prefer a verified runtime patch-level strategy (the Xiaomi Pad 8 Pro tree has a `piano-setup.sh` runtime approach, but it is **not** a drop-in MT6991 solution).

**P0 — AVB and rollback:** The current config references AOSP test signing keys. Confirm the actual unlocked boot chain, image footer/layout and rollback fields. A valid build or test-key signature is not a device unlock bypass and does not establish the image can boot.

**P1 — cmdline/SELinux:** Compare `BOARD_VENDOR_CMDLINE` and SELinux settings with the two working Skyward images. The images have `bootopt=64S3,32N2,64N2 erofs.reserved_pages=64`; source YARP adds `androidboot.selinux=permissive`. Validate security and mount implications before production use.

## turner-specific MiTEE / touch follow-up (2026-11-14)

Evidence: locally re-read the supplied fast and slow 64 MiB vendor_boot images (SHA-256 respectively 5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855 and 9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a). Both PLATFORM fragments have SHA-256 2330b412e7d93d81d0f336b5e2141e983a49d2e5483bdd526eebc2d34132c081. Read the actual RECOVERY fragment's skyward/device.toml; these are the port author's configuration/comments, not new hardware test results.

- The shared configuration expects persist at /mnt/vendor/persist, including data and fdsd; tee-supplicant uses the installed vendor/odm MiTEE TA files. Start supplicant before KeyMint and check actual readiness, not simply a fixed delay. Preserve credential validation, hardware rate limiting, and on-disk key material.
- KeyMint process expects AIDL device, secure clock and shared secret registration; Gatekeeper has its own AIDL service. Fast/slow configs differ on vndservicemanager: slow disables it after repeated SIGABRT reported in comments. Do not infer the cause of boot speed from this alone or start duplicate service managers without checking their binder context.
- The turner touch configuration names Novatek NT36536E and nt36536e_touch_turner in vendor_dlkm plus a Xiaomi touchfeature HAL in odm. Neither the primary touch module nor the optional xiaomi_touch_turner module is present in the common 274-module PLATFORM fragment. Thus copying those 274 modules alone cannot establish touch independence from super. Keep runtime module/firmware/service dependencies available across mount cleanup; verify driver source and actual input events.
- Skyward comments specifically identify binder header incompatibility between recovery and installed-system libraries. Treat this as a lead to test with real logs, not as proof of the same YARP crash. Do not mix arbitrary libbinder, libbinder_ndk, libutils, linker or crypto libraries.
- Current GitHub device tree has three zero-byte MiTEE init rc files (tee-supplicant, KeyMint, Gatekeeper) and four zero-byte security manifest fragments (Gatekeeper, KeyMint, SecureClock, SharedSecret). They may be intentional stubs or inputs generated elsewhere; resolve their provenance and inspect the actual build output. Current persist.fstab already uses /mnt/vendor/persist and omits formattable. Do not introduce destructive changes.
- Upstream TWRP-Test twrp-16.0 partitionmanager.cpp mounts/unmounts vendor/odm during fstab and startup processing, then sets twrp.storage.ready; kernel_module_loader.cpp supports a cache-device-runtime.sh hook and publishes readiness after cleanup. Use this existing lifecycle where possible. Do not neutralize UnmountMainPartitions globally or kill processes merely to make decryption pass.
- The existing alternate-protector patch is not proof of a usable decrypt implementation. Reevaluate against normal upstream credential-backed unlock, without bypassing it. If installed slot properties are unavailable, fail closed rather than upgrading keys under fictitious future patch levels.

中文结论：先处理 MiTEE 服务与 VINTF、真实版本属性、触控依赖及挂载生命周期，再测试原生 YARP 解密。未确认前不改实际解密算法或启用配置。本次没有 YARP 实机测试。

Upstream references:
- https://github.com/TWRP-Test/android_bootable_recovery/blob/twrp-16.0/partitionmanager.cpp
- https://github.com/TWRP-Test/android_bootable_recovery/blob/twrp-16.0/kernel_module_loader.cpp
- https://github.com/kirklin/skyward/tree/v0.1.2/crates/skyward-crypto/src

## Required actions / 后续验证

1. Record the target firmware build, installed `ro.build.version.security_patch`, `ro.vendor.build.security_patch`, `ro.product.first_api_level` and related KeyMint properties; do not guess.
2. Audit actual `init`, `vold`, `libcrypto`, KeyMint and Gatekeeper ABI/ELF dependencies against the exact vendor/system image.
3. Trace the version/patch values Recovery passes to KeyMint and how key upgrades or rejected unwraps are handled.
4. Verify first on non-destructive mounts and a test device with a verified stock backup. Do not wipe or mutate live /data to force a decrypt test.
5. Keep **UNTESTED-DO-NOT-FLASH** status until the checks are complete.

For device-level priority, see [Safety / 安全规范](../SAFETY.zh-CN.md) and [feature parity / 功能验收要求](../docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md).
