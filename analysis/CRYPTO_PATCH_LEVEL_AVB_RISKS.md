# FBE / KeyMint patch-level and AVB review — blocking risk / 必查风险

> **Static audit only. No change to active build settings yet.**
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

## Required actions / 后续验证

1. Record the target firmware build, installed `ro.build.version.security_patch`, `ro.vendor.build.security_patch`, `ro.product.first_api_level` and related KeyMint properties; do not guess.
2. Audit actual `init`, `vold`, `libcrypto`, KeyMint and Gatekeeper ABI/ELF dependencies against the exact vendor/system image.
3. Trace the version/patch values Recovery passes to KeyMint and how key upgrades or rejected unwraps are handled.
4. Verify first on non-destructive mounts and a test device with a verified stock backup. Do not wipe or mutate live /data to force a decrypt test.
5. Keep **UNTESTED-DO-NOT-FLASH** status until the checks are complete.

For device-level priority, see [Safety / 安全规范](../SAFETY.zh-CN.md) and [feature parity / 功能验收要求](../docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md).
