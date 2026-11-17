#!/system/bin/sh
# turner-ks2-sup.sh -- v3.27 supervisor for the INSTALLED keystore2.
# Back to the v3.14/v3.16 recipe: spawn the installed system's own
# keystore2 (/mnt/system/system/bin/keystore2), the only keystore2
# that has ever connected to mitee KeyMint in this hybrid ("KeyMint
# device is current version (Some(300))", v3.16). The payload's
# keystore2 (v3.18-v3.26) failed three different ways, lastly with
# NAME_NOT_FOUND on the genuine path although KeyMint stays alive
# and registered (vibration, which looks its HAL up the same way,
# works). Its two historical killers are both stubbed by
# liblogcapture v7: the BBinder symbol (v5) and the libhidlbase
# getAllHalInstanceNames segfault (v6); v7 also answers the
# declared-instances query. Never exits; respawns on death.
mkdir -p /tmp/misc/keystore
ulimit -l unlimited 2>/dev/null
LOGF=/tmp/spawn-keystore2-sup.log
LIBS="/system/etc/hybrid/twrpbinder:/mnt/system/system/lib64:/apex/com.android.i18n/lib64:/system/lib64/twrp16:/system/lib64"
while true; do
    /system/etc/hybrid/spawn_hal "${LOGF}" 0 0 0,1017,1007         "${LIBS}"         "/system/etc/hybrid/libfaultlog.so:/system/etc/hybrid/liblogcapture.so:/system/etc/hybrid/libkmsglog.so"         /mnt/system/system/bin/keystore2 /tmp/misc/keystore
    pid=$(sed -n 's/.* pid \([0-9]*\).*/\1/p' "${LOGF}" 2>/dev/null | tail -n 1)
    echo "turner-ks2-sup: spawned keystore2 pid=${pid}" > /dev/kmsg
    while [ -n "${pid}" ] && [ -d "/proc/${pid}" ]; do sleep 2; done
    echo "turner-ks2-sup: keystore2 exited, respawning in 2s" > /dev/kmsg
    sleep 2
done
