# Redmi K Pad USB / MTP init audit (English / 简体中文)

> **Status: static evidence only — do not merge both init rule sets into an active recovery.**
>
> **状态：仅完成静态对照，尚未通过 YARP 实机验证；不能把两套 USB init 规则直接叠加。**

## Source evidence / 来源

| File / 文件 | Source / 来源 | Git blob SHA-1 | Active in development tree? |
|---|---|---|---|
| `recovery/root/init.recovery.usb.rc` | Original turner YARP device tree | `049816d3f2008db369861f8053cd6e69cc7cc4ca` | Present; still original content |
| `references/skyward/fast/init.recovery.mt6991.rc` | Extracted from both boot-tested Skyward fast/slow images | `48f504573da1381179ffb99c6c72303129f36527` | **Reference only** |
| `references/skyward/fast/skyward-mtp.rc` | Extracted Skyward `system/etc/init/skyward-mtp.rc` | `302cfedc5fefb7c4aa2180bd0eca311ebe3efd11` | **Reference only** |

The Skyward reference files were matched to locally extracted files using Git blob hashes. Both fast and slow Skyward images contain the same MT6991 init and MTP rules.

## Confirmed mismatches / 已确认差异

### USB controller

- Original YARP `init.recovery.usb.rc`: `setprop sys.usb.controller "11201000.usb0"` in `on fs`.
- Working Skyward `init.recovery.mt6991.rc`: `setprop sys.usb.controller "16701000.usb0"` in `on init`.

**Implication / 风险：** controller name and initialization phase both differ. This is a test hypothesis for a future USB/ADB issue, **not proof** that merely changing the string will fix MTP or that all USB ports must use the same controller. Verify the actual /sys/class/udc/ devices and the physical port in recovery.

### ConfigFS and FunctionFS

- Original YARP rules set `sys.usb.configfs=0` in `early-init`, create the USB gadget, mount `ffs.mtp`, `ffs.adb` and `ffs.fastboot`, then set `sys.usb.configfs=1` in `on fs`.
- Skyward init sets `sys.usb.configfs=1` in `on init`; its dedicated MTP rc mounts `ffs.mtp` on `on fs && property:sys.usb.configfs=1`.

**Do not copy the Skyward MTP service trigger into the original file unchanged.** It could duplicate `mkdir` / `mount functionfs` operations, race with USB ConfigFS initialization, or change gadget ownership.

### MTP + ADB binding

- Original YARP uses `sys.usb.ffs.ready=1 && sys.usb.config=mtp,adb`, USB product ID `0xFF48`.
- Skyward uses **both** `sys.usb.ffs.ready=1` **and** `sys.usb.ffs.mtp.ready=1` with `sys.usb.config_disable=0` for starting adbd, product ID `0x4EE2`.

This may explain timing-related differences, but cannot be attributed to any proven YARP runtime failure without logs.

## Safe integration sequence / 安全整合顺序

1. Preserve original `init.recovery.usb.rc` and independent Skyward reference; do not make both active.
2. After successful YARP boot, collect `ls -l /sys/class/udc`, `getprop sys.usb.*`, `ls -l /config/usb_gadget/g1/configs/b.1`, `logcat -b all`, and `dmesg` before changes.
3. Confirm whether `16701000.usb0` exists and is the controller for the tested connection; do not assume both USB port paths are equivalent.
4. Make one narrowly scoped change on a development branch at a time, build as **untested**, and test ADB-only, MTP-only, MTP+ADB, disconnect/reconnect and Fastbootd separately.
5. Retain a verified rollback image and rescue procedure throughout.

## Related documents / 相关文档

- [Safety / 安全说明](../SAFETY.zh-CN.md)
- [YARP GUI2 / Wi-Fi requirements / 功能验收要求](../docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md)
- [Skyward init comparison / 初始化对照](SKYWARD_INIT_AUDIT.md)

**No runtime USB fix has been claimed or applied. / 当前尚未修改启用中的 USB 配置，也不宣称已修复实机问题。**
