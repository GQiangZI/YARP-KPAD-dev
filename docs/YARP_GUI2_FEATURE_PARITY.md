# YARP GUI2 feature parity and Wi-Fi policy for Redmi K Pad (turner)

**Status: specification / acceptance criteria; implementation is not yet boot-tested.**

## Non-negotiable goal

Use upstream [TWRP-Test/android_bootable_recovery, branch twrp-16.0](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0) and its **GUI2/LVGL** UI and operation backends. Do not replace it with Skyward's `system/bin/recovery` or a classic TWRP GUI. Skyward is a *hardware/boot/init/driver* reference, not a replacement recovery frontend.

Keep upstream page navigation, font/scaling strategy, translations, status/navigation bars, dialogs, confirmation flows, and backend functions. Device-specific changes should be made in the device tree or narrowly scoped patches. Keep the base GUI2 UI visually and behaviorally consistent with the upstream build; do not redesign it as a bespoke tablet UI.

The Xiaomi Pad 8 Pro (`piano`) YARP tree provides a reference for `landscape_hdpi`, but its panel geometry, touch transforms, recovery partition structure and Qualcomm boot stack are device-specific. The turner panel is 1880×3008 native; do **not** copy `RECOVERY_TOUCHSCREEN_SWAP_XY`, `RECOVERY_TOUCHSCREEN_FLIP_Y`, `landscape_hdpi` or `recoveryimage` settings without validation.

## Core acceptance gates (must be tested on the target device)

| Area | Acceptance criteria | Current evidence |
|---|---|---|
| Boot and rollback | Vendor Boot v4; 2 LZ4 ramdisk fragments; stock-compatible DTB, size and first-stage behavior; normal system boot and rollback | Skyward reference boots; YARP not tested |
| Display/input | GUI2 renders fully with correct orientation, text scaling, touch hit targets, scrolling, buttons and screenshot | YARP not tested |
| File encryption | Unlock PIN/pattern/password, mount decrypted /data and /metadata without destructive writes | YARP not tested |
| Install/sideload | ZIP installation, ADB sideload, safe failure handling | YARP not tested |
| Backup/restore | A/B, dynamic partitions, backup listing, restore and file integrity | YARP not tested |
| Wipe/format | Safe partition selection; no accidental destructive action | YARP not tested |
| USB | ADB, MTP, file transfer, gadget mode and reconnect behavior | YARP not tested |
| Fastbootd/reboot | Fastbootd, reboot to system/recovery/bootloader, slot-aware behavior | YARP not tested |
| Tools & UI pages | Mount, file manager, terminal, logs, settings, time zone, language, battery/brightness | YARP not tested |
| Wi-Fi (optional) | Enable, scan, connect, DHCP, status and networking only if stable | Deferred; **NOT a release blocker** |

## Wi-Fi upstream implementation exists

Upstream GUI2 provides:
- `gui2/pages/wifi_page.cpp`: Wi-Fi UI.
- `gui2/backend/twrp_wifi_backend.cpp`: scanning, association, status and testing.
- `TW_INCLUDE_WIFI`: build-time optional feature, consumed by `twrp.cpp` and `prebuilt/Android.mk`.
- `wifi_backend.h`: the GUI2 interface. When the backend is not supplied, Wi-Fi UI entry points are hidden (e.g. `advanced_page.cpp` handles a null `wifi_target`).

The existing backend expects `wlan0`, init service `wpa_supplicant`, `wpa_cli`, and control sockets under `/tmp/recovery/sockets`. Those **are not proven available/working** on turner recovery. Enabling a flag alone does not bring up the MediaTek Wi-Fi stack; firmware, kernel modules, vendor config, runtime dependencies, service definitions, DHCP and interface naming must be verified.

### Implementation decision

1. **Phase 1:** Keep Wi-Fi disabled at build time, using the upstream optional-backend behavior; do not add `TW_INCLUDE_WIFI := true` to `BoardConfig.mk`. All other GUI2 pages and features remain in scope.
2. **Phase 2 (only after boot, touch, decrypt and USB work):** Identify the MT6991 Wi-Fi interface/firmware/modules and service dependencies from the installed vendor/system. Audit `wpa_supplicant` process and interface, test scan, association, DHCP, reconnect and status.
3. Enable `TW_INCLUDE_WIFI` and add the necessary runtime files **only after** functionality and stability are verified. If unavailable, leave Wi-Fi off without modifying upstream UI to simulate support.

## Release policy

No functional claim is accepted without logs and a real device test on a named firmware build. Compilation, static audit and successful Skyward boot are useful but do **not** establish YARP boot success. The public repository remains development-only; never publish artifacts as flash-ready until all mandatory gates have passed.
