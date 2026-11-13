# YARP-KPAD-dev — Redmi K Pad (turner)

Development-only staging repository for the YARP / TWRP 16.0 GUI2 recovery device tree for Redmi K Pad (MT6991).

## Status

**Incomplete import — not buildable yet.** Initial text configuration files have been imported from [GQiangZI/twrp_device_xiaomi_turner](https://github.com/GQiangZI/twrp_device_xiaomi_turner). Binary prebuilts, recovery ramdisk contents, scripts, patches, and CI have **not** been fully migrated. Do not flash any output until image structure and on-device behavior have been verified.

## Device-specific constraints

- Recovery is packaged into **vendor_boot.img** (vendor boot v4), not a standalone recovery partition image.
- Keep LZ4 legacy vendor ramdisk compression and the stock vendor ramdisk layout. Do not copy the Xiaomi Pad 8 Pro recovery partition/boot chain.
- Preserve MT6991-specific DTB, first-stage fstab, modules, init services, and FBE/KeyMint/Gatekeeper integrations.
- Baseline display dimensions in BoardConfig are 1880 × 3008. Orientation, touchscreen mapping, brightness and GUI2 scaling require real-device verification.

## Tablet UI reference

[Xiaomi Pad 8 Pro (piano) recovery device tree](https://github.com/xiaomi-pad-8-pro-development/android_device_xiaomi_piano-recovery) supports YARP GUI2 and configures `TW_THEME := landscape_hdpi`, `RECOVERY_TOUCHSCREEN_SWAP_XY := true`, and `RECOVERY_TOUCHSCREEN_FLIP_Y := true`. These are **piano-specific**, not validated for turner, and have not been copied. In particular, the piano tree produces `recovery.img`, while turner needs `vendor_boot.img`.

## Migration checklist

- [x] Import initial core text device configurations
- [ ] Import all original text files, patches, scripts, init/recovery resources, and license
- [ ] Audit large prebuilts and their provenance before importing
- [ ] Diff Skyward fast/slow vendor_boot recovery ramdisks and document boot behavior
- [ ] Inspect YARP GUI2 orientation and scaling before any tablet UI changes
- [ ] Restore a safe manual-only CI workflow and validate build
- [ ] Validate image layout, size, and hardware behavior before any flashing guidance

The original repository is not modified by this staging work.
