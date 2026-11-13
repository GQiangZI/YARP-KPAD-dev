# Skyward fast/slow MT6991 init findings

Source: two user-provided, boot-tested Skyward OS 3.0.306 vendor_boot images. Both contain the same `init.recovery.mt6991.rc` (SHA-256 `a8df21f25a7bd58770f61f4f63c859dcc3f545caff483328295db56e1f1c11a2`). This is **not** identical to the original YARP turner init file.

## Skyward recovery init excerpts

```rc
import /init.recovery.project.rc

on init
    setprop sys.usb.configfs 1
    setprop sys.usb.controller "16701000.usb0"

on boot
    exec u:r:update_engine:s0 root root -- /system/bin/mtk_plpath_utils

on boot
    setprop sys.usb.config adb
    mkdir /data/vendor 0771 system system
    mkdir /data/vendor/touch 0771 system system
    mkdir /data/vendor/touch_state 0771 system system
    mkdir /data/vendor/mqsas_common 0771 system system
    mkdir /data/vendor/bsplog 0775 system system
    mkdir /data/vendor/bsplog/touch 0775 system system
    setprop vendor.teefs_state ready
```

## Important compatibility caution

The original YARP `recovery/root/init.recovery.mt6991.rc` additionally starts `boot-hal-1-2`, `mitee-helper`, and `health-hal-2-1`, mounts persist, sets TEE permissions, disables raw touch mode, and triggers watchdog/haptics. Replacing it with the shorter Skyward file without verifying service dependencies **could break boot, touch, decryption or charging**.

The Skyward fast/slow `skyward/device.toml` differ around `/vendor/bin/vndservicemanager`. The fast variant starts it; the slow variant documents repeated SIGABRT and omits it. The versions also have differing `system/bin/recovery` executables. Thus service choice cannot be established solely from the names fast/slow.

## Decision

Keep the YARP init file unchanged until the extracted Skyward init and service dependency graph are reconciled. Use the known-working Skyward contents as the hardware baseline, but retain YARP-specific startup dependencies only where demonstrated. Do not upload or publish a flashable image until validated.
