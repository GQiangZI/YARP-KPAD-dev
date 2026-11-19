#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# init owns the actual keystore2 PID and restarts it after vold seeds tmpfs.
daemon=/mnt/system/system/bin/keystore2
store=/tmp/misc/keystore
mkdir -p "$store" || exit 1
ulimit -l unlimited 2>/dev/null
printf 'spawn_hal: %s pid %s\n' "$daemon" "$$" >> /tmp/spawn-keystore2-sup.log
libs=/system/etc/hybrid/twrpbinder:/mnt/system/system/lib64:/apex/com.android.i18n/lib64:/system/lib64/twrp16:/system/lib64
preload=/system/etc/hybrid/libfaultlog.so:/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so
exec /system/bin/env -i PATH=/system/bin LD_LIBRARY_PATH="$libs" LD_PRELOAD="$preload" \
    "$daemon" "$store" </dev/null >/dev/kmsg 2>&1
