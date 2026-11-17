#!/system/bin/sh
#
# turner-setup.sh — boot-time preparation for the YARP x Skyward hybrid
# recovery on Redmi K Pad (turner, MT6991). Stage-2 draft, stage-4 patched
# (bounded waits + kmsg breadcrumbs; see the stage-4 note below).
#
# Modelled on piano-setup.sh (Xiaomi Pad 8 Pro YARP tree) and on the service
# orchestration proven by the Skyward-for-turner build (a7 device.toml):
#
# - The TEE chain (tee-supplicant -> KeyMint -> Gatekeeper) and the Xiaomi
#   touch HAL run the *installed system's* binaries from the installed
#   vendor/odm partitions, with per-service library paths (hybrid-services.rc
#   carries the LD_LIBRARY_PATH lists copied from the a7 toml).
# - KeyMint binds key blobs to the OS version and patch levels it is started
#   under, and refuses (or worse, upgrades) blobs when they differ from the
#   installed ROM (piano-setup.sh header comment). So the real values are
#   read from the installed ROM and resetprop'd BEFORE KeyMint starts. If a
#   value cannot be read, the build-time fallback stays; the payload's
#   fallbacks (2026-08-01) are older than the installed OS4 patch level
#   (2026-10-01), so a mismatch then fails decrypt instead of upgrading the
#   ROM's keys — the safe direction, again per piano.
# - vndservicemanager is deliberately never started: on turner it SIGABRTs
#   in a 15 s loop and the vendor services register on /dev/binder's
#   servicemanager anyway (a7 toml). The OS4 recovery init does not start
#   it either; nothing to undo.
#
# This script only prepares and starts services. All service definitions
# (user/group/capabilities/library paths) live in hybrid-services.rc; every
# hybrid service is `disabled` there so class_start can never race this
# script's ordering.
#
# Stage-4 patch (semantics audit, hybrid v2): this script runs ONLY as a
# non-blocking init service (`start` from hybrid-services.rc, never `exec`),
# so nothing here can stall init's trigger queue. Every polling/wait loop
# is bounded (<= 30 s) and logs its timeout to /dev/kmsg under the tag
# TURNER-SETUP instead of spinning forever; step breadcrumbs go to
# /dev/kmsg via log_msg so a hang localizes to a step in console-ramoops.
# All service starts use `setprop ctl.start` (asynchronous by definition).

LOG_TAG=TURNER-SETUP
SLOT=$(getprop ro.boot.slot_suffix)
SCRATCH=/tmp/hybrid
SYS_MNT=/mnt/system
EXT_MNT=/mnt/system_ext

log_msg() {
    echo "I:${LOG_TAG}: $1" >> /tmp/recovery.log
    echo "${LOG_TAG}: $1" > /dev/kmsg
}

# First match only: build.prop may repeat a key and init keeps the first.
# (piano-setup.sh read_prop, verbatim pattern.)
read_prop() {
    grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2-
}

set_prop() {
    if [ -z "$2" ]; then
        log_msg "$1 not found in the installed ROM, keeping $(getprop "$1")"
        return
    fi
    if command -v resetprop >/dev/null 2>&1; then
        resetprop "$1" "$2"
    else
        # ro.* props are write-once for plain setprop; log and move on —
        # the stale fallback then fails decrypt safely instead of lying.
        setprop "$1" "$2" 2>/dev/null ||
            log_msg "no resetprop and setprop refused $1"
    fi
    log_msg "$1=$2"
}

is_mounted() {
    grep -q " $1 " /proc/mounts
}

# Mount an installed logical partition read-only at $2 if not already
# mounted there. Stock firmware is erofs; some custom ROMs use ext4.
# (piano-setup.sh mount_ro, generalised.)
mount_ro() {
    # $1 = partition name (vendor, system, ...), $2 = mount point
    dev=/dev/block/mapper/$1${SLOT}
    is_mounted "$2" && return 0
    mkdir -p "$2"
    i=0
    while [ ! -e "${dev}" ] && [ "${i}" -lt 10 ]; do
        sleep 1
        i=$((i + 1))
    done
    # Bounded wait (<= 10 s): on timeout, say so on kmsg and fall through
    # to the mount attempts, which log their own failure. Never spin.
    if [ ! -e "${dev}" ]; then
        log_msg "TIMEOUT after 10s waiting for ${dev}; mount attempt will likely fail"
    fi
    mount -t erofs -o ro "${dev}" "$2" 2>/dev/null ||
        mount -t ext4 -o ro "${dev}" "$2" 2>/dev/null ||
        log_msg "cannot mount ${dev} at $2"
}

# Start a service and wait for init to report it running. A start can be
# refused while TWRP briefly mounts over /vendor, so retry it.
# (piano-setup.sh start_service, verbatim pattern.)
# The start itself is `setprop ctl.start` — asynchronous; this loop only
# polls the result and is bounded at 30 iterations x 1 s, after which it
# logs a TURNER-SETUP timeout to /dev/kmsg and gives up on this service
# (the remaining services are still attempted).
start_service() {
    i=0
    while [ "${i}" -lt 30 ]; do
        [ "$(getprop "init.svc.$1")" = running ] && return 0
        setprop ctl.start "$1"
        sleep 1
        i=$((i + 1))
    done
    log_msg "TIMEOUT: $1 did not reach running within 30s"
    FAILURES="${FAILURES} $1"
    return 1
}

# v2.4: fire a start without waiting, and a poll-only waiter, so the
# three HALs start back-to-back and race in parallel instead of each
# waiting behind the previous service's full timeout (the touch HAL
# previously started ~60 s late, after both TEE waits timed out).
fire_service() {
    setprop ctl.start "$1"
}

wait_service() {
    i=0
    while [ "${i}" -lt 30 ]; do
        [ "$(getprop "init.svc.$1")" = running ] && return 0
        sleep 1
        i=$((i + 1))
    done
    log_msg "TIMEOUT: $1 did not reach running within 30s"
    FAILURES="${FAILURES} $1"
    return 1
}

# Best-effort owner/mode staging from the a7 toml [[owners]] blocks.
# Missing nodes are expected on this device (the toml says so itself) and
# are skipped silently; the pass is repeated after the touch HAL is up.
stage_tee_owners() {
    for n in /dev/tee0 /dev/teepriv0 /dev/rpmb0 /dev/mmcblk0rpmb; do
        [ -e "${n}" ] || continue
        chown system:system "${n}" 2>/dev/null
        chmod 0660 "${n}" 2>/dev/null
    done
}

stage_touch_owners() {
    if [ -e /dev/xiaomi-touch ]; then
        chown system:system /dev/xiaomi-touch 2>/dev/null
        chmod 0666 /dev/xiaomi-touch 2>/dev/null
    fi
    for n in /dev/xiaomi-touch-knock /dev/xiaomi-thp \
        /sys/class/touch/touch_dev/enable_touch_raw \
        /sys/class/touch/touch_dev/resolution_factor \
        /sys/class/touch/touch_dev/update_rawdata \
        /sys/class/touch/touch_dev/gesture_single_tap_state \
        /sys/class/touch/touch_dev/fod_press_status \
        /sys/class/touch/touch_dev/suspend_state \
        /sys/class/touch/touch_dev/touch_sensor \
        /sys/class/touch/touch_dev/touch_sensor_ctrl \
        /sys/class/touch/touch_dev/touch_active_status \
        /sys/class/touch/touch_dev/touch_finger_status \
        /sys/class/touch/touch_dev/touch_thp_cmd \
        /sys/class/touch/touch_dev/touch_thp_cmd_data \
        /sys/class/touch/touch_dev/touch_thp_cmd_ready \
        /proc/tp_selftest /proc/tp_hal_version /proc/tp_fw_version \
        /proc/tp_lockdown_info; do
        [ -e "${n}" ] || continue
        chown system:system "${n}" 2>/dev/null
        chmod 0664 "${n}" 2>/dev/null
    done
}

# Load the Novatek touch driver from the *installed* vendor_dlkm, so the
# module always matches the installed kernel (the hybrid boots the stock
# kernel of whatever ROM is installed; a bundled .ko would silently rot
# on the next OTA). This is the piano TW_LOAD_VENDOR_MODULES philosophy
# and what Skyward's [modules] does on this very device. The bundled copy
# at /system/etc/hybrid/ (extracted from the OS4 vendor_dlkm, pinned by
# sha256 in DESIGN.md) is only a fallback if vendor_dlkm cannot be mounted
# at all. (The v2 F1 did not ship the bundled copy; v2.3 ships it again.)
#
# v2.4 loader rewrite — the v2.2/v2.3 loader never loaded anything:
# vendor_dlkm's modules.dep lists every dep by ABSOLUTE path
# (/vendor_dlkm/lib/modules/<name>.ko), and the old loop insmod'ed
# "${moddir}/${dep}", producing a doubled path and ENOENT. So the dep
# xiaomi_touch_turner.ko — which exports register_touch_panel,
# xiaomi_register_panel_notifier, get_raw_data_base, driver_get_touch_mode
# and friends — never landed, and nt36536e died on Unknown symbol
# (kernel err -2, which insmod then reports as "No such file or
# directory"). Fixes: (1) mount vendor_dlkm at its CANONICAL point when
# free, so the absolute paths in modules.dep resolve as written;
# (2) resolve every dep token to a file under ${moddir} by basename
# (vendor_dlkm modules live flat in lib/modules); (3) walk the dep
# closure from modules.dep and load deps-first, with retry passes —
# the kernel enforces the true order via symbols anyway. modprobe is
# dropped: toybox modprobe -d failed on this tree with the same
# absolute-path quirk. Every error is logged verbatim (v2.3 change).
load_touch_module() {
    [ -d /sys/module/nt36536e_touch_turner ] && return 0
    vdl=/vendor_dlkm
    if ! is_mounted /vendor_dlkm; then
        mount_ro vendor_dlkm /vendor_dlkm
        if ! is_mounted /vendor_dlkm; then
            log_msg "canonical /vendor_dlkm mount failed, trying scratch mount"
            mount_ro vendor_dlkm "${SCRATCH}/vendor_dlkm"
            [ -d "${SCRATCH}/vendor_dlkm/lib/modules" ] && vdl="${SCRATCH}/vendor_dlkm"
        fi
    fi
    moddir="${vdl}/lib/modules"
    if [ -d "${moddir}" ]; then
        dep_names_of() {
            line=$(grep -m1 "$1\\.ko:" "${moddir}/modules.dep" 2>/dev/null)
            [ -n "${line}" ] || return 0
            for tok in ${line#*:}; do
                basename "${tok}" .ko | tr '-' '_'
            done
        }
        # Dep closure of the touch module, deps-first order.
        want=""
        frontier="nt36536e_touch_turner"
        while [ -n "${frontier}" ]; do
            newf=""
            for m in ${frontier}; do
                case " ${want} " in *" ${m} "*) ;; *) want="${m} ${want}" ;; esac
                for d in $(dep_names_of "${m}"); do
                    case " ${want} " in *" ${d} "*) ;; *) newf="${newf} ${d}" ;; esac
                done
            done
            frontier="${newf}"
        done
        log_msg "touch module closure (deps first): ${want}"
        pass=0
        while [ ${pass} -lt 4 ]; do
            pass=$((pass + 1))
            remaining=""
            for m in ${want}; do
                [ -d "/sys/module/${m}" ] && continue
                err=$(insmod "${moddir}/${m}.ko" 2>&1) || {
                    log_msg "insmod ${m}.ko failed (pass ${pass}): ${err}"
                    remaining="${remaining} ${m}"
                }
                [ -d "/sys/module/${m}" ] && log_msg "insmod ${m}.ko ok"
            done
            [ -d /sys/module/nt36536e_touch_turner ] && return 0
            [ -z "${remaining}" ] && break
            want="${remaining}"
        done
        [ -d /sys/module/nt36536e_touch_turner ] && return 0
        log_msg "touch module did not load from ${moddir}"
    fi
    if [ -f /system/etc/hybrid/nt36536e_touch_turner.ko ]; then
        log_msg "falling back to the bundled touch module copy"
        fb_err=$(insmod /system/etc/hybrid/nt36536e_touch_turner.ko 2>&1)
        [ -d /sys/module/nt36536e_touch_turner ] && return 0
        log_msg "bundled touch module insmod failed: ${fb_err}"
    fi
    log_msg "touch module NOT loaded — panel will probe but produce no events until the HAL/module issue is fixed"
    return 1
}

# Post-load touch state, logged unconditionally (v2.3): what input
# devices exist, and what the kernel said about the touch driver.
touch_diag() {
    log_msg "touch diag: /dev/input = $(ls /dev/input 2>/dev/null | tr '\n' ' ')"
    log_msg "touch diag: /sys/class/input = $(ls /sys/class/input 2>/dev/null | tr '\n' ' ')"
    dmesg 2>/dev/null | grep -i -E "nt36536|novatek|xiaomi_touch|touch" | tail -n 12 |
        while IFS= read -r l; do log_msg "touch diag dmesg: ${l}"; done
}

# v2.6: ALL THREE HALs are spawned directly (a7-style) via spawn_hal —
# no init services. Rationale, from the v2.2-v2.5 evidence chain:
# - Under init, keymint/gatekeeper died with status 1 in ~15 ms in every
#   ramdisk-first build and init swallowed their stderr, so five builds
#   produced no death message at all. The one configuration where they
#   ever linked (v2.3, installed-system-first library order) is restored
#   here verbatim, preload libkmsglog only.
# - spawn_hal points stdout/stderr at /dev/kmsg (opened before the
#   privilege drop — v2.5's helper opened it after setuid and the touch
#   HAL's last words were lost), so whatever any HAL says now lands in
#   dmesg.
# - Registration is unaffected by the parent: servicemanager takes
#   registrations from any process (a7 spawns the same way).
# Liveness is judged by /proc/<pid> after a grace period.
SYSFIRST=/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex/com.android.i18n/lib64:/apex/com.android.runtime/lib64:/apex/com.android.runtime/lib64/bionic:/vendor/lib64:/mnt/system_ext/lib64
RAMFIRST=/system/lib64:/system/lib64/bootstrap:/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex/com.android.i18n/lib64:/apex/com.android.runtime/lib64:/apex/com.android.runtime/lib64/bionic:/odm/lib64:/vendor/lib64:/mnt/system_ext/lib64
KMSLOG=/system/etc/hybrid/libkmsglog.so

spawn_and_check() {
    # $1 = label/failure token, rest = spawn_hal args after the logfile
    label=$1; shift
    logf="/tmp/spawn-${label}.log"
    rm -f "${logf}"
    /system/etc/hybrid/spawn_hal "${logf}" "$@"
    sleep 3
    pid=$(sed -n 's/.* pid \([0-9]*\).*/\1/p' "${logf}" 2>/dev/null | tail -n 1)
    if [ -n "${pid}" ] && [ -d "/proc/${pid}" ]; then
        log_msg "${label} spawned pid=${pid} alive after 3s"
        return 0
    fi
    log_msg "${label} spawn failed or died within 3s (pid=${pid})"
    FAILURES="${FAILURES} ${label}"
    return 1
}

spawn_touch_hal() {
    [ -e /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service ] || {
        log_msg "touch HAL binary missing (odm not mounted?)"
        FAILURES="${FAILURES} touch-hal"
        return 1
    }
    spawn_and_check touch-hal 1000 1000 1000,1004 "${RAMFIRST}" "${KMSLOG}" \
        /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service
}

spawn_tee_chain() {
    spawn_and_check keymint 0 0 0,1000,1009 "${SYSFIRST}" "${KMSLOG}" \
        /vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee
    log_msg "step:keymint handled"
    spawn_and_check gatekeeper 0 0 0,1000 "${SYSFIRST}" "${KMSLOG}" \
        /vendor/bin/hw/android.hardware.gatekeeper-service.mitee
    log_msg "step:gatekeeper handled"
}

# ---------------------------------------------------------------------------

[ "$(getprop vendor.turner.setup.done)" = 1 ] && exit 0
FAILURES=""
log_msg "step:begin slot=${SLOT}"

# 1. Installed partitions. vendor/odm go to their canonical points (the
#    services execute /vendor/bin/... and /odm/bin/hw/...); system and
#    system_ext go to the extra points the a7 toml's library lists name
#    (/mnt/system/system/lib64, /mnt/system_ext/lib64). The scratch mounts
#    are NOT torn down afterwards: a service restarted by init re-execs and
#    must still find its libraries (piano could umount because its
#    services run from private copies; ours run in place).
mount_ro vendor /vendor
mount_ro odm /odm
mount_ro system "${SYS_MNT}"
mount_ro system_ext "${EXT_MNT}"
log_msg "step:mounts done"

# 2. Real OS version / patch levels from the installed ROM, before any
#    KeyMint start (piano-setup.sh set_prop block, same three props):
#    the release and the system patch level come from the installed
#    system build.prop, the vendor patch level from the installed vendor.
set_prop ro.build.version.release \
    "$(read_prop "${SYS_MNT}/system/build.prop" ro.build.version.release)"
set_prop ro.build.version.security_patch \
    "$(read_prop "${SYS_MNT}/system/build.prop" ro.build.version.security_patch)"
set_prop ro.vendor.build.security_patch \
    "$(read_prop /vendor/build.prop ro.vendor.build.security_patch)"
log_msg "step:props aligned"

# 3. persist + metadata for the TEE chain. tee-supplicant/KeyMint keep the
#    key store (MTK fdsd) under /mnt/vendor/persist; the stock tee rc's
#    `on fs` mkdir never runs in recovery, so both the mount and the dirs
#    are made here (a7 toml [[owners]] create=true block).
if ! is_mounted /mnt/vendor/persist; then
    mkdir -p /mnt/vendor/persist
    # v2.3: v2.2's single attempt failed and its error was lost. Try both
    # by-name roots and both plausible fstypes; log every error verbatim.
    for pdev in /dev/block/bootdevice/by-name/persist /dev/block/by-name/persist; do
        [ -e "${pdev}" ] || continue
        for pfst in ext4 f2fs; do
            perr=$(mount -t ${pfst} -o noatime,nosuid,nodev "${pdev}" /mnt/vendor/persist 2>&1) &&
                break 2
            log_msg "persist mount ${pdev} (${pfst}) failed: ${perr}"
        done
    done
    is_mounted /mnt/vendor/persist || {
        log_msg "cannot mount persist (all candidates failed)"
        FAILURES="${FAILURES} persist"
    }
fi
mkdir -p /mnt/vendor/persist/data /mnt/vendor/persist/fdsd
chown system:system /mnt/vendor/persist/data /mnt/vendor/persist/fdsd 2>/dev/null
chmod 0755 /mnt/vendor/persist/data /mnt/vendor/persist/fdsd 2>/dev/null
# metadata carries /metadata/vold/metadata_encryption/key; without it
# mounted, metadata decryption cannot even start (a7 toml [partitions]).
if ! is_mounted /metadata; then
    mkdir -p /metadata
    mount -t f2fs -o ro,noatime,nosuid,nodev \
        /dev/block/bootdevice/by-name/metadata /metadata ||
        log_msg "cannot mount metadata"
fi
log_msg "step:persist+metadata ready"

# 4. Device-node staging (first pass; repeated for touch after the HAL).
stage_tee_owners

# 5. Touch driver module from the installed vendor_dlkm, then its nodes.
load_touch_module || FAILURES="${FAILURES} touch-module"
touch_diag
stage_touch_owners
log_msg "step:touch module handled"

# 6. TEE chain, in the a7 toml's order, with the toml's waits between
#    starts (wait_ms is the delay the supplicant/HAL needs before the next
#    service asks it anything — "started together, the key service asks
#    first and waits forever").
start_service vendor.tee-supplicant
setprop vendor.teefs_state ready
log_msg "step:tee-supplicant started"
sleep 4
spawn_tee_chain

# 7. Xiaomi touch HAL (HTCP: without it the probed driver emits no input
#    events). v2.5: spawned directly (a7-style), NOT via init — see
#    spawn_touch_hal. Nodes are re-staged once it is up.
spawn_touch_hal
stage_touch_owners
log_msg "step:touch HAL handled"

# v2.4: setup.done means the whole chain actually came up. The old
# script set it unconditionally, so a failed boot was permanently
# marked initialized and the entry guard skipped every retry.
if [ -n "${FAILURES}" ]; then
    log_msg "step:done WITH FAILURES:${FAILURES} — setup.done NOT set"
    setprop vendor.turner.setup.failed "${FAILURES}"
else
    setprop vendor.turner.setup.done 1
    log_msg "step:done"
fi
