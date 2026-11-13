# YARP Recovery — Redmi K Pad (turner)

[简体中文](README.md) | [**English**](README.en.md)

> **Project status: In development · Not fully built or device-tested · DO NOT FLASH**
>
> This repository stages a **YARP / TWRP 16.0 GUI2** Recovery port for Redmi K Pad (MT6991). The tree remains incomplete; source files, scripts and future CI artifacts are **not proof of a safe, flash-ready image**.

## Project goals

Bring the upstream **YARP GUI2/LVGL user interface and core recovery functions** to Redmi K Pad, using the known-booting Skyward turner images as primary hardware/boot references for MediaTek services, touch, encryption and USB.

- **Preserve upstream YARP UI**: navigation, visual behavior, file manager, installation, backup/restore, mounts, terminal, settings and other functions. Do not replace YARP's interface with Skyward.
- **Prioritize essential operation**: boot, display, touch, ADB/MTP, data decryption, backup/restore and Fastbootd.
- **Wi-Fi is optional**: the upstream UI and backend already exist, but the turner drivers/services are unverified. Keep Wi-Fi disabled in the first phase rather than compromising the core recovery.
- **Safety first**: compilation, static analysis or Skyward booting successfully does **not** imply that a newly assembled YARP image has passed on-device validation.

## Device specifications

| Item | Target |
| --- | --- |
| Device | Redmi K Pad |
| Codename | `turner` |
| Platform | MediaTek MT6991 |
| OS baseline | Android 16 / HyperOS (verify exact firmware on-device) |
| Display configuration | 1880 × 3008 (current device-tree setting) |
| Recovery upstream | [TWRP-Test / twrp-16.0](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0) |
| Image target | **`vendor_boot.img`**, not a standalone `recovery.img` |
| Boot layout | Vendor Boot v4, two ramdisk fragments, legacy LZ4 |

> The Xiaomi Pad 8 Pro (`piano`) YARP tree is a useful tablet UI reference, **not** a source of drop-in Qualcomm drivers, touch transforms or recovery partition settings for turner.

## Development status

| Item | Status |
| --- | --- |
| Core device-tree configuration | Partially imported |
| MT6991 init, fstab and vold patches | Partially imported; dependencies still need review |
| Skyward fast/slow images | Layout and init comparison documents recorded; file dependencies not fully audited |
| Prebuilt drivers, firmware and HALs | **Not fully imported** |
| YARP GUI2, tablet display and touch | Build and device tests pending |
| Data decryption, ADB/MTP, backup/restore | Device tests pending |
| Wi-Fi | Optional / deferred |
| Full build, image validation and flashing tests | **Not completed** |

## Safety notice

**This is not yet a complete buildable or flash-ready device tree.** Vendor Boot v4 header, DTB, PLATFORM/RECOVERY ramdisks, vendor modules, fstab, init and HAL dependencies must all be verified. The resulting image must fit the 64 MiB vendor_boot partition. A successful build alone is not sufficient to distribute an image to other users.

Before testing on hardware, prepare a verified stock image, a recovery/rollback method and the exact device/firmware details. Untested artifacts must never be labeled stable.

- [Safety and pre-flash checklist (English)](SAFETY.md) · [简体中文](SAFETY.zh-CN.md)
- [YARP GUI2 feature parity & Wi-Fi policy (English)](docs/YARP_GUI2_FEATURE_PARITY.md) · [简体中文](docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md)
- [Skyward Vendor Boot structure analysis](analysis/SKYWARD_VENDOR_BOOT_COMPARISON.md)
- [Skyward init comparison](analysis/SKYWARD_INIT_AUDIT.md)
- [Read-only Vendor Boot layout verifier](tools/verify_vendor_boot.py)

## References and credits

- [TWRP-Test: YARP / TWRP 16.0 and GUI2](https://github.com/TWRP-Test/android_bootable_recovery)
- [Original Redmi K Pad device tree](https://github.com/GQiangZI/twrp_device_xiaomi_turner)
- [Skyward Recovery](https://github.com/kirklin/skyward) · [skyward-extra](https://github.com/echoskies-works/skyward-extra)
- [Xiaomi Pad 8 Pro recovery tree](https://github.com/xiaomi-pad-8-pro-development/android_device_xiaomi_piano-recovery)

Retain applicable upstream licenses and copyright notices. **This is a development/testing repository; the original device-tree repository is not changed by this work.**
