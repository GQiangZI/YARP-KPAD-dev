#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Called after original read-only mounts and persist/metadata preparation,
# but before HAL services start. Only writes tmpfs and attaches read-only loops.
set -eu
ROOT=/tmp/turner-runtime
SLOT=$(getprop ro.boot.slot_suffix)
case "$SLOT" in _a|_b) ;; *) echo 'invalid slot' >&2; exit 1;; esac
log() { echo "I:TURNER-RUNTIME: $*" >> /tmp/recovery.log; }
mounted_source() {
    while read -r src point rest; do
        [ "$point" = "$1" ] && { echo "$src"; return 0; }
    done < /proc/mounts
    return 1
}
[ "$(getprop vendor.turner.runtime.staged)" = 1 ] && exit 0
mkdir -p "$ROOT/images"
TOTAL=0
for name in vendor odm system system_ext; do
    case "$name" in system|system_ext) point=/mnt/$name;; *) point=/$name;; esac
    src=$(mounted_source "$point") || { log "missing mount $point"; exit 1; }
    [ "$src" = "/dev/block/mapper/$name$SLOT" ] || { log "unexpected source $src"; exit 1; }
    sectors=$(blockdev --getsz "$src")
    [ "$sectors" -gt 0 ] || exit 1
    TOTAL=$((TOTAL + sectors / 2))
done
AVAILABLE=0
while read -r key value unit; do if [ "$key" = MemAvailable: ]; then AVAILABLE=$value; fi; done < /proc/meminfo
# Retain at least 1.5 GiB for recovery, an installer and decompression.
[ "$AVAILABLE" -gt $((TOTAL + 1572864)) ] || { log "insufficient available RAM KiB: $AVAILABLE need $TOTAL plus reserve"; exit 1; }
FREE=$(df -Pk /tmp | tail -1 | tr -s ' ' | cut -d ' ' -f4)
[ "$FREE" -gt $((TOTAL + 262144)) ] || { log 'insufficient tmpfs space'; exit 1; }
log "snapshot begin KiB: $TOTAL, available $AVAILABLE"
: > "$ROOT/loops"
for name in vendor odm system system_ext; do
    src=/dev/block/mapper/$name$SLOT
    expected=$(blockdev --getsize64 "$src")
    image=$ROOT/images/$name.img
    timeout 120 dd if="$src" of="$image.part" bs=4194304 2>> /tmp/recovery.log
    [ "$(stat -c %s "$image.part")" = "$expected" ] || exit 1
    mv "$image.part" "$image"
    loop=$(losetup -r -f -s "$image")
    [ -b "$loop" ] || exit 1
    [ "$(blockdev --getro "$loop")" = 1 ] || exit 1
    echo "$name $loop" >> "$ROOT/loops"
    mkdir -p "$ROOT/check-$name"
    mount -t erofs -o ro "$loop" "$ROOT/check-$name"
    log "snapshot ready: $name $expected $loop"
done
# No service may hold the originals here. Normal unmounts only; fail closed.
: > "$ROOT/swapped"
rollback() {
    while read -r name loop; do
        case "$name" in system|system_ext) point=/mnt/$name;; *) point=/$name;; esac
        current=$(mounted_source "$point" || true)
        [ "$current" != "$loop" ] || umount "$point" || return 1
        current=$(mounted_source "$point" || true)
        [ -n "$current" ] || mount -t erofs -o ro "/dev/block/mapper/$name$SLOT" "$point" || return 1
    done < "$ROOT/loops"
}
while read -r name loop; do
    case "$name" in system|system_ext) point=/mnt/$name;; *) point=/$name;; esac
    if ! umount "$point"; then log "busy original: $point"; rollback; exit 1; fi
    # Keep the verification mount until the canonical mount exists: Toybox
    # umount may detach loops, and MS_MOVE is rejected below shared parents.
    if ! mount -t erofs -o ro "$loop" "$point"; then log "RAM mount failed: $point"; rollback; exit 1; fi
    umount "$ROOT/check-$name"
    echo "$name $loop" >> "$ROOT/swapped"
done < "$ROOT/loops"
# A later mount is invisible in the keeper's private namespace. Prepare ICU
# before creating it; the original setup function detects and reuses this.
if ! mounted_source /apex/com.android.i18n >/dev/null; then
    mkdir -p /apex/com.android.i18n /tmp/apex-i18n
    unzip -o -q /mnt/system/system/apex/com.android.i18n.apex apex_payload.img -d /tmp/apex-i18n
    apexloop=$(losetup -r -f -s /tmp/apex-i18n/apex_payload.img)
    mount -t ext4 -o ro "$apexloop" /apex/com.android.i18n
fi
setprop vendor.turner.runtime.staged 1
log 'all four canonical mounts now use RAM-backed read-only loop devices'
