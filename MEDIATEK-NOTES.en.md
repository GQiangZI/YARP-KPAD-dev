# MediaTek (Dimensity) adaptation notes

Problems actually encountered — and verified one by one — while bringing up
TWRP from scratch for the Redmi K Pad (`turner`, Dimensity 9400+ / MT6991).
Stock firmware used: OS3.0.310.0.WAOCNXM.
Last updated: 2026-11-10.

## 1. A clean-built vendor_boot never reaches recovery — repack onto the stock image

Five clean-built images (twrp-14.1 base and YARP base) all black-screened or
logo-looped after flashing. All three MediaTek reference projects
(dash / MT6991Z, warhol / MT6993, chagall / MT6899) do the same thing:
build first, then repack the result into the stock vendor_boot as a template.
None of them flashes the raw build output.

Workable route: keep the stock kernel, DTB, image header and first-stage
ramdisk byte-identical, and replace only the recovery parts.

## 2. Ramdisk compression must be lz4; every zstd image failed

Both stock ramdisk fragments use lz4 legacy format. The kernel config does
have `CONFIG_RD_ZSTD=y`, yet every zstd-compressed image failed to boot.
The zstd compression patch that used to be in this repo has been removed;
lz4 is used throughout.

## 3. AVB is not the gate — do not burn time on signing

No AVB footer, a hash-only footer (Algorithm NONE) and a full RSA4096-signed
footer were all tried; the failure mode was identical, and the stock image
itself ships a hash-only footer. The boot failure has nothing to do with AVB.

## 4. ro.hardware is mt8799, not mt6991

init imports `/init.recovery.${ro.hardware}.rc`, and on this tablet
`ro.hardware` is `mt8799`; mt6991 is only the platform marketing name.
Boot-script changes (e.g. the touch switch) written into
`init.recovery.mt6991.rc` are never executed. Confirmed from the stock
recovery ramoops log, where init actually processes the mt8799 rc.

## 5. The touch driver is built into the kernel — there is no .ko

There is no touch .ko anywhere in the image (the OrangeFox build for rothko,
same platform, also contains zero). Xiaomi's touch stack uses userspace THP
raw-frame processing, and recovery has no matching daemon, so the mt8799 rc
needs this in `on boot`:

```
write /sys/class/touch/touch_dev/enable_touch_raw 0
```

to switch back to kernel input events.

## 6. There is a 31-second watchdog

The stock log confirms `mtk-wdt` with a 31 s timeout (nowayout=0): if nothing
pets the watchdog within 31 s of entering recovery, the SoC hard-resets.
When diagnosing, distinguish a real crash from a watchdog timeout — the log
tails look different.

## 7. An uncleared BCB in misc makes the tablet boot straight into stock recovery

After a failed flash, if the boot-recovery command in the misc partition's
BCB is never cleared, every power-on goes straight into stock recovery, and
any ramoops pulled afterwards is a stock session, not the failed boot.
Clear it (either way):

```sh
adb shell su -c "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1"
fastboot erase misc
```

Always clear the BCB and cold-boot straight into Android before trying to
capture a failing boot's log.

## 8. [Most important] A repack merge needs a symbol-level pairing audit

Merge order: the platform fragment goes in first, the recovery fragment
overlays it, and **for same-named files the later one wins**. The stock init
from the template is kept, but same-named libraries it depends on are silently
replaced by TWRP's API 36 builds. DT_NEEDED closure checks (does the file
exist?) all PASS, while the symbols do not pair up, so PID 1 dies during
dynamic linking — which looks exactly like a black screen / logo loop.

**Case 1: killProcessGroupOnce**
Stock init references the C symbol `killProcessGroupOnce`; TWRP's
`libprocessgroup.so` exports only the C++ mangled `_Z20killProcessGroupOncejii`,
and no library in the merged image provides the C spelling.
Fix: remove TWRP's `libprocessgroup.so` from the recovery fragment so the
stock one wins. The stock build's one extra dependency, `libcgrouprc.so`,
is already in the image as the stock build, and TWRP's recovery binary does
not link this library at all, so removing it is safe.
(Fixed in repack v3; verification 47/47 PASS.)

**Case 2: an android::base::Join template instantiation**
TWRP's `libhidl-gen-utils.so` references
`android::base::Join<std::vector<std::string>&, char const*>(...)`.
The stock `libbase.so` does not export that instantiation; only the API 36
libbase in the twrp16 directory does. But twrp16 is on the search path only
through the recovery service's `setenv LD_LIBRARY_PATH`, while init links
`libhidl-gen-utils.so` directly and resolves through the default path.
The stock `libhidl-gen-utils.so` does not reference that symbol and its
dependency closure is complete, so v4 will likewise drop the recovery
fragment's overlay copy.
(Its consumers are init and hwservicemanager, both stock binaries; the
symbol satisfaction of librecovery_ui_ext is the one point still to confirm.)

**Lesson**: on the repack route, pair every UND reference with a DEF export
using `readelf --dyn-syms`. DT_NEEDED closure alone proves nothing.

Two related notes:
- `ueventd` is byte-identical to `init` (the same file under a second name);
  a symbol audit must count both as reference holders.
- Both stock rc files start with `import /init.recovery.project.rc`, but
  that file does not exist anywhere in the stock image. It is a dangling
  stock leftover and harmless — do not chase it.

## 9. The stock firmware's own DLKM images splice two kernel builds

Auditing the three dlkm images of OS3.0.310.0 (336 .ko in total): the
68 modules in `system_dlkm` carry vermagic exactly matching the running
kernel (`6.6.118-android15-8-gc44b714366cc-abogki519650608-4k`), while all
258 modules in `vendor_dlkm` were built for a different kernel build
(`gf1638d237c11`). When a module refuses to load over vermagic, remember
the firmware itself ships mixed builds.

## 10. Decryption in recovery does not work on this platform yet

warhol (MT6993) documents the same limitation. On the repack route the
keystore / keymint components do not line up with the stock init scripts,
so do not expect to decrypt /data after flashing — get the UI up first.

## Current status (2026-11-10)

repack v3 is assembled and passes the full static verification (stock
template + the three earlier fixes: charger binary removed,
mtk_plpath_utils back to the stock build, touch line moved into the
mt8799 rc; plus the libprocessgroup symbol fix from section 8, case 1).
Flash test pending. v4 is planned to change exactly one more file:
dropping the recovery fragment's `libhidl-gen-utils.so` overlay
(section 8, case 2).
