#!/usr/bin/env python3
"""Fail closed on absent turner device-tree inputs. STATIC ONLY; no boot claims."""
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = ROOT / "recovery/root/lib/modules"
DTB_SHA256 = "4f985cad82176ea746ffef6aa960269ef0aec410f294bc157bd766ad74f49bc0"
DTB_SIZE = 533115

REQUIRED = [
    "BoardConfig.mk", "AndroidProducts.mk", "device.mk",
    "init/Android.bp", "init/init_turner.cpp",
    "mtk_plpath_utils/Android.bp", "mtk_plpath_utils/mtk_plpath_utils.cpp",
    "bootctrl/Android.bp", "bootctrl/ufs-mtk-ioctl.h",
    "recovery.fstab",
    "recovery/root/first_stage_ramdisk/fstab.mt6991",
    "recovery/root/first_stage_ramdisk/fstab.emmc",
    "recovery/root/lib/modules/modules.load",
    "recovery/root/lib/modules/modules.load.recovery",
    "recovery/root/init.recovery.mt6991.rc",
    "recovery/root/init.recovery.usb.rc",
    "recovery/root/vendor/bin/hw/android.hardware.gatekeeper-service.mitee",
    "recovery/root/vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee",
    "recovery/root/vendor/bin/tee-supplicant",
    "prebuilt/dtb",
]

def fail(message):
    raise SystemExit("FAIL: " + message)

def main():
    for name in REQUIRED:
        path = ROOT / name
        if not path.is_file():
            fail("missing required file: " + name)
    dtb = (ROOT / "prebuilt/dtb").read_bytes()
    if len(dtb) != DTB_SIZE or hashlib.sha256(dtb).hexdigest() != DTB_SHA256:
        fail("DTB does not match boot-tested Skyward reference")
    modules = sorted(MODULE_DIR.glob("*.ko"))
    if len(modules) != 274:
        fail(f"expected 274 MT6991 .ko files; got {len(modules)}")
    for config in ("modules.load", "modules.load.recovery"):
        lines = (MODULE_DIR / config).read_text().splitlines()
        names = [
            Path(line.split("#", 1)[0].strip().split()[0]).name
            for line in lines if line.strip() and not line.lstrip().startswith("#")
        ]
        modules_to_check = [name for name in names if name.endswith(".ko")]
        missing = [name for name in modules_to_check if not (MODULE_DIR / name).is_file()]
        if missing:
            fail(f"{config}: {len(missing)} missing modules: {missing[:8]}")
        print(f"PASS {config}: {len(modules_to_check)} module references resolve")
    board = (ROOT / "BoardConfig.mk").read_text()
    for token in (
        "BOARD_BOOT_HEADER_VERSION := 4",
        "BOARD_RAMDISK_USE_LZ4 := true",
        "BOARD_INCLUDE_RECOVERY_RAMDISK_IN_VENDOR_BOOT := true",
        "DEVICE_PATH := device/xiaomi/turner",
    ):
        if token not in board:
            fail("required vendor_boot setting missing: " + token)
    if re.search(r"^\s*TW_INCLUDE_WIFI\s*:?=\s*true", board, re.M):
        fail("optional Wi-Fi must not be enabled before MT6991 service validation")
    print("PASS: DTB size and SHA-256 match the working Skyward image")
    print("PASS: all 274 MT6991 modules and mandatory build inputs are present")
    print("PASS: vendor_boot v4 + LZ4 settings; optional Wi-Fi disabled")
    print("STATIC_OK_ONLY: no YARP build, boot or functionality has been validated")

if __name__ == "__main__":
    main()
