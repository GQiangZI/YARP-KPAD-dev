#!/system/bin/sh
# turner-vibrator-sup.sh -- v3.24 supervisor for the Xiaomi
# vibratorfeature HAL (/odm/bin/hw/vendor.xiaomi.hardware.
# vibratorfeature.service). libtwrpminui's vibrate() calls the AIDL
# instance IVibrator/vibratorfeature; the installed odm ships the
# service but recovery never starts it, so GUI vibration was dead.
# Same spawn pattern as the touch supervisor: twrpbinder split pair +
# liblogcapture/libkmsglog preload, stderr -> /dev/kmsg. The stock
# odm rc runs it as system with groups system/input/audio.
#
# Node staging (subset of the odm rc's post-fs-data block, applied
# before every spawn; missing nodes are skipped — the rc is shared
# across many Xiaomi models and turner's PMIC vibrator may expose
# only the leds class node).
for n in /dev/awinic_haptic /dev/awinic_x_haptic; do
    [ -e "${n}" ] && { chown system:system "${n}" 2>/dev/null; chmod 0666 "${n}" 2>/dev/null; }
done
if [ -d /sys/class/leds/vibrator ]; then
    chown system:system /sys/class/leds/vibrator/brightness 2>/dev/null
    chmod 0666 /sys/class/leds/vibrator/brightness 2>/dev/null
fi
LOGF=/tmp/spawn-vibrator-sup.log
while true; do
    /system/etc/hybrid/spawn_hal "${LOGF}" 1000 1000 1000,1004,1005 \
        "/system/etc/hybrid/twrpbinder" \
        "/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so" \
        /odm/bin/hw/vendor.xiaomi.hardware.vibratorfeature.service
    pid=$(sed -n 's/.* pid \([0-9]*\).*/\1/p' "${LOGF}" 2>/dev/null | tail -n 1)
    echo "turner-vibrator-sup: spawned vibrator HAL pid=${pid}" > /dev/kmsg
    while [ -n "${pid}" ] && [ -d "/proc/${pid}" ]; do sleep 2; done
    echo "turner-vibrator-sup: vibrator HAL exited, respawning in 2s" > /dev/kmsg
    sleep 2
done
