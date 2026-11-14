#!/system/bin/sh
# Called by upstream YARP while the installed partitions are mounted.
# Copy only the turner touch service and device-specific libraries into /tmp.
# Never execute installed firmware or write its partitions at this stage.
set -eu
ROOT=/tmp/turner-touch
log() { printf 'turner-touch cache: %s\n' "$*" >> /tmp/recovery.log; }
mounted_ro() { awk -v p="$1" '$2 == p && $4 ~ /(^|,)ro(,|$)/ {ok=1} END {exit !ok}' /proc/mounts; }
setprop twrp.turner.touch.cached 0
mounted_ro /odm || { log 'ODM is not mounted read-only'; exit 1; }
mkdir -p "$ROOT"
chmod 0755 "$ROOT"
STAGE="$ROOT/stage"
[ ! -e "$STAGE" ] || { log 'stale staging directory'; exit 1; }
mkdir -p "$STAGE/bin" "$STAGE/lib64" "$STAGE/manifest"
trap 'rm -rf "$STAGE"' EXIT
SOURCE=/odm/bin/hw/vendor.xiaomi.hw.touchfeature-service
[ -f "$SOURCE" ] || { log 'stock touchfeature service missing'; exit 1; }
cp -L "$SOURCE" "$STAGE/bin/touchfeature"
chmod 0755 "$STAGE/bin/touchfeature"
[ -f /odm/lib64/libtouchreport.so ] || { log 'stock libtouchreport.so missing'; exit 1; }
for src in /odm/lib64/libtouchreport*.so /odm/lib64/vendor.xiaomi.hw.touchfeature*.so; do
    [ -f "$src" ] || continue
    cp -L "$src" "$STAGE/lib64/"
done
# Match the Binder interface's real manifest; do not invent an AIDL version.
for src in /odm/etc/vintf/manifest/*.xml; do
    [ -f "$src" ] || continue
    if grep -q 'vendor.xiaomi.hw.touchfeature' "$src" && grep -q 'ITouchFeature' "$src"; then
        cp -L "$src" "$STAGE/manifest/"
    fi
done
if mounted_ro /vendor; then
    for src in /vendor/lib64/vendor.xiaomi.hw.touchfeature*.so; do
        [ -f "$src" ] || continue
        dst="$STAGE/lib64/$(basename "$src")"
        if [ -e "$dst" ]; then
            cmp -s "$dst" "$src" || { log 'conflicting ODM/vendor AIDL library'; exit 1; }
        else
            cp -L "$src" "$dst"
        fi
    done
    for src in /vendor/etc/vintf/manifest/*.xml; do
        [ -f "$src" ] || continue
        if grep -q 'vendor.xiaomi.hw.touchfeature' "$src" && grep -q 'ITouchFeature' "$src"; then
            dst="$STAGE/manifest/$(basename "$src")"
            if [ -e "$dst" ]; then
                cmp -s "$dst" "$src" || { log 'conflicting ODM/vendor manifest'; exit 1; }
            else
                cp -L "$src" "$dst"
            fi
        fi
    done
fi
set -- "$STAGE"/manifest/*.xml
[ "$#" -eq 1 ] && [ -f "$1" ] || { log 'missing or ambiguous dedicated stock touch VINTF fragment'; exit 1; }
# Do not copy libc, libbinder, linker, libutils, libcrypto or other base libraries.
# Use the YARP build's own libraries for the Android runtime.
[ ! -e "$ROOT/live" ] || { log 'runtime cache already exists'; exit 1; }
chmod 0644 "$STAGE"/lib64/*.so "$STAGE"/manifest/*.xml
mv "$STAGE" "$ROOT/live"
trap - EXIT
setprop twrp.turner.touch.cached 1
log 'staged installed touch service, narrow HAL libraries and actual VINTF source'
