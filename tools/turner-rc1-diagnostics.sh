#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Read-only recovery diagnostics. The USB sampler records into /tmp.

usb_log=/tmp/turner-rc1-usb.txt

usb_state() {
    printf '\n--- USB state (%s) ---\n' "$(cat /proc/uptime)"
    getprop | grep -E '^\[(sys\.usb\.|init\.svc\.(adbd|mtp|fastbootd)\])' || :
    for node in /sys/class/android_usb/android0/state \
        /sys/class/android_usb/android0/functions /sys/class/android_usb/android0/enable \
        /config/usb_gadget/g1/UDC; do
        if [ -r "$node" ]; then
            printf '%s=' "$node"
            cat "$node"
        fi
    done
    ls -ld /sys/class/udc/* /dev/usb-ffs/mtp /dev/usb-ffs/adb 2>/dev/null || :
    ls -l /config/usb_gadget/g1/configs/b.1/f* 2>/dev/null || :
}

snapshot() {
    printf '%s\n' '--- device and storage ---'
    for prop in ro.product.device ro.boot.slot_suffix twrp.user.0.decrypt; do
        printf '%s=%s\n' "$prop" "$(getprop "$prop")"
    done
    grep -E ' /(data|cache|metadata|tmp) ' /proc/mounts || :
    grep -E '^/(vendor_boot|dtbo)[[:space:]]' /etc/twrp.flags 2>/dev/null || :
    usb_state
    printf '\n%s\n' '--- latest recovery log ---'
    tail -n 200 /tmp/recovery.log
}

watch_usb() {
    for step in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        usb_state
        sleep 2
    done
    echo 'USB capture finished'
}

case "${1:-snapshot}" in
    snapshot) snapshot ;;
    watch-usb)
        umask 077
        set -C
        if [ -e "$usb_log" ]; then
            echo "Capture already exists at $usb_log. Pull it before starting another."
            exit 1
        fi
        if ! command -v setsid >/dev/null 2>&1; then
            echo 'Missing setsid.'
            exit 1
        fi
        # A separate session keeps recording while MTP re-enumerates USB.
        if ! : > "$usb_log"; then
            exit 1
        fi
        setsid sh "$0" usb-sample </dev/null >> "$usb_log" 2>&1 &
        echo "Recording USB for about 40 seconds to $usb_log."
        ;;
    usb-sample) watch_usb ;;
    *)
        echo 'Usage: turner-rc1-diagnostics.sh [snapshot|watch-usb]' >&2
        exit 2
        ;;
esac
