#!/system/bin/sh
# Read-only diagnostic collection; does not touch credentials or key blobs.
OUT=/tmp/turner-crypto-status.txt
ARCHIVE=/tmp/turner-v335-logs.tar
{
    echo 'turner crypto diagnostic v3.35'
    date
    cat /proc/uptime
    id
    for prop in ro.build.version.release ro.build.version.sdk \
        ro.build.version.security_patch ro.vendor.build.security_patch \
        ro.bootimage.build.version.security_patch ro.crypto.state ro.crypto.type \
        ro.crypto.metadata.enabled sys.boot_completed vendor.turner.setup.done \
        vendor.turner.setup.failed; do
        echo "$prop=$(getprop "$prop")"
    done
    echo '--- recovery processes and libraries'
    for pid in $(pidof recovery); do
        echo "pid=$pid"
        tr '\000' ' ' < "/proc/$pid/cmdline"
        echo
        grep -E 'libturner_crypto|libbinder(_ndk)?\.so' "/proc/$pid/maps"
    done
    echo '--- services'
    service list 2>&1
    echo '--- mounts'
    cat /proc/mounts
    echo '--- source fstab (the bridge supplies an in-memory corrected view)'
    cat /etc/additional.fstab 2>/dev/null
    echo '--- metadata directory presence (no key contents)'
    ls -ld /metadata /metadata/vold /metadata/vold/metadata_encryption \
        /metadata/vold/metadata_encryption/key /mnt/vendor/persist 2>&1
    echo '--- bridge log'
    cat /tmp/turner-crypto.log 2>/dev/null
} > "$OUT" 2>&1
dmesg > /tmp/dmesg-v335.txt 2>&1
cat /proc/mounts > /tmp/mounts-v335.txt
FILES=''
for item in /tmp/turner-crypto-status.txt /tmp/turner-crypto.log \
    /tmp/recovery.log /tmp/dmesg-v335.txt /tmp/mounts-v335.txt \
    /tmp/spawn-keymint-sup.log /tmp/spawn-gatekeeper-sup.log \
    /tmp/spawn-keystore2-sup.log /tmp/spawn-touch-sup.log \
    /tmp/spawn-vibrator-sup.log /etc/additional.fstab \
    /system/etc/recovery.fstab; do
    [ -f "$item" ] && FILES="$FILES ${item#/}"
done
# Recovery runs this script as root. The ADB sync service may run as shell.
if tar -cf "$ARCHIVE" -C / $FILES && chmod 0644 "$ARCHIVE"; then
    printf 'Saved %s\n' "$ARCHIVE"
else
    printf 'Failed to export %s\n' "$ARCHIVE" >&2
    exit 1
fi
