# Skyward turner Recovery payload inventory / 镜像文件对照

> Verified locally from the **extracted RECOVERY ramdisk file trees** of the two user-provided OS 3.0.306 images. This is **not** a complete file manifest for the PLATFORM ramdisk or installed HyperOS system.
>
> 本报告只统计两个上传镜像 **RECOVERY ramdisk 已解包的普通文件**；不代表 PLATFORM ramdisk 或系统固件的全部文件。

## Verified comparison / 已核对结果

| Field / 项目 | Fast / 快版 | Slow / 慢版 |
| --- | --- | --- |
| Whole `vendor_boot.img` size | 67,108,864 bytes | 67,108,864 bytes |
| Whole image SHA-256 | `5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855` | `9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a` |
| Extracted RECOVERY regular files / 已解包普通文件 | **40** | **40** |
| Regular files with identical paths and SHA-256 | **38** | **38** |
| Files with changed contents (same path) | **2** | **2** |
| Paths only present on one variant | **0** | **0** |

### The only two differing files / 仅有两个普通文件内容不同

| Path | Fast SHA-256 | Slow SHA-256 |
| --- | --- | --- |
| `system/bin/recovery` | `b1e773c6e38aa8854c89faabec1203f2649a2f27f34ea344f50836b0a2ebae26` | `9da83e129ba892d71716554f3ad8ffb1d0d1d43696e1fe9e3f66940322ae557e` |
| `skyward/device.toml` | `c95d676d1a463912bc9502a6e4774bb582e1ad3d6011a51e7bbee637973f0181` | `f2eab1ac7f02d3c1bcaef715677f16d9c6ea89ca3593fc18404f30eb6a845983` |

The fast `device.toml` explicitly launches `/vendor/bin/vndservicemanager`; the slow one comments out that service due to repeated SIGABRT observed by the author. Because `system/bin/recovery` also differs, **this alone does not establish the cause of fast/slow boot time**.

快版 `device.toml` 明确启动 `vndservicemanager`；慢版备注该服务会重复 SIGABRT，因此取消启动。由于 `system/bin/recovery` 也不同，**无法据此认定实际快慢原因**。

### Identical files relevant to the YARP port / 可复用的一致文件

| Extracted file | SHA-256 | Equivalent original turner tree |
| --- | --- | --- |
| `init.recovery.mt6991.rc` | `a8df21f25a7bd58770f61f4f63c859dcc3f545caff483328295db56e1f1c11a2` | Differs; kept as noninstalled reference |
| `system/etc/recovery.fstab` | `13f5bd1abf777a293a7bc74bb14e41757bced12c4fb2d130cf7b0829d35ab6a9` | Matches `recovery/root/system/etc/recovery.fstab` and `recovery/root/first_stage_ramdisk/fstab.mt6991` by Git blob SHA-1 `496cfca863e03c53e2c82b280686044d7ad37cc5` |
| `first_stage_ramdisk/fstab.emmc` | `912a4a651d2197883e46cf9a7afc3035261c1e7a8263709f91d0146ddfd68bfb` | Matches `recovery/root/first_stage_ramdisk/fstab.emmc` by Git blob SHA-1 `5b416f861fa4103c5bd9d576ba55767d1606524b` |
| `system/etc/init/skyward-mtp.rc` | `194135bdc994f399a348eb27e208ec197b016a357323da2d36e8d5f1e952c8a5` | Skyward-only reference; **not enabled in YARP** |

Platform ramdisk, DTB and per-fragment hashes are recorded in [vendor_boot comparison](SKYWARD_VENDOR_BOOT_COMPARISON.md). An offline, pinned-hash exporter lives at [`tools/extract_vendor_boot_reference.py`](../tools/extract_vendor_boot_reference.py). Both known images were processed successfully and their outputs matched expected hashes.

## Integration rules / 整合要求

- Keep Skyward hardware init, MTP and other recipes as **noninstalled references** until relevant YARP init dependencies are reconciled.
- Preserve the common PLATFORM ramdisk and DTB by exact hash for the initial test-image structure; do not mix fast/slow RECOVERY binaries.
- Keep YARP GUI2 core and functional backends. Skyward `system/bin/recovery` must **not** replace the YARP recovery executable.
- No feature/boot/flash safety claims without a YARP device test.

## Follow-up

Compare individual HAL ELF `DT_NEEDED` and symbol versions, actual module/service dependencies, runtime properties and OS build patch levels. The currently extracted RECOVERY payload does **not** by itself contain the complete vendor HAL stack required to run on turner.

**Status: ANALYSIS ONLY — NOT FLASH-READY / 仅供研究，禁止作为刷机验证。**
