#!/system/bin/sh
# Runs after upstream cleanup. No mounts of installed filesystems, no writes
# to /data, persist or the installed ODM/vendor. The cache lives in tmpfs.
set -eu
LIVE=/tmp/turner-touch/live
log() { printf 'turner-touch prepare: %s\n' "$*" >> /tmp/recovery.log; }
setprop twrp.turner.touch.ready 0
[ "$(getprop twrp.turner.touch.cached)" = 1 ] || exit 1
[ -x "$LIVE/bin/touchfeature" ] || exit 1
# The destination must be the recovery's own vendor ramdisk, not an installed
# partition or a nested mount. Refuse a suspicious layout instead of writing.
dest=/vendor/etc/vintf/manifest
if awk '$2=="/vendor" || index($2,"/vendor/etc")==1 {found=1} END{exit !found}' /proc/mounts; then
    log 'vendor filesystem still mounted; refusing manifest installation'
    exit 1
fi
[ "$(readlink -f /vendor)" = /vendor ] || exit 1
mkdir -p "$dest"
[ "$(readlink -f "$dest")" = "$dest" ] || exit 1
set -- "$LIVE"/manifest/*.xml
[ "$#" -eq 1 ] && [ -f "$1" ] || exit 1
# A stock manifest fragment is staged under its own recovery-only name.
out="$dest/turner-touch-runtime.xml"
[ ! -e "$out" ] && [ ! -L "$out" ] || exit 1
cp "$1" "$out"
chmod 0644 "$out"
# Avoid the original unverified direct-input write; let the stock HAL handle
# the HTCP path. Apply only the reference ownership of existing touch nodes.
for node in /dev/xiaomi-touch /dev/xiaomi-touch-knock /dev/xiaomi-thp /sys/class/touch/touch_dev/enable_touch_raw /sys/class/touch/touch_dev/resolution_factor /sys/class/touch/touch_dev/update_rawdata /sys/class/touch/touch_dev/gesture_single_tap_state /sys/class/touch/touch_dev/fod_press_status /sys/class/touch/touch_dev/suspend_state /sys/class/touch/touch_dev/touch_sensor /sys/class/touch/touch_dev/touch_sensor_ctrl /sys/class/touch/touch_dev/touch_active_status /sys/class/touch/touch_dev/touch_finger_status /sys/class/touch/touch_dev/touch_thp_cmd /sys/class/touch/touch_dev/touch_thp_cmd_data /sys/class/touch/touch_dev/touch_thp_cmd_ready /proc/tp_selftest /proc/tp_hal_version /proc/tp_fw_version /proc/tp_lockdown_info; do
    [ -e "$node" ] || continue
    chown system:system "$node" || log "chown failed: $node"
    if [ "$node" = /dev/xiaomi-touch ]; then
        chmod 0666 "$node" || log "chmod failed: $node"
    else
        chmod 0664 "$node" || log "chmod failed: $node"
    fi
done
# Only recovery-built framework libraries + the small staged device set.
# The Android linker --list probe must succeed before init launches the HAL.
export LD_LIBRARY_PATH=/system/lib64:/system/lib64/bootstrap:$LIVE/lib64:/vendor/lib64:/vendor/lib64/hw
if ! /system/bin/linker64 --list "$LIVE/bin/touchfeature" >> /tmp/recovery.log 2>&1; then
    log 'native linker could not resolve touch dependencies; HAL not started'
    exit 1
fi
setprop twrp.turner.touch.ready 1
log 'linker probe passed; requesting touch HAL (input events not yet verified)'
