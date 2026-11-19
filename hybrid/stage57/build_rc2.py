#!/usr/bin/env python3
"""Backport the turner USB composite init rules to the exact RC1 image."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "stage48"))
from build import compress, cpio_entries, decompress, digest, layout
from build import pack_cpio, repack_image, require, verify_avb

BASE_SHA = "d467e1b3b0a4057b9b3817d964bdec476c0f9564f8fe20e858b6fc304b07e0df"
INIT = "system/etc/init/hw/init.rc"
MTP = "system/lib64/twrp16/libtwrpmtp-ffs.so"
CLEANUP = (
    b"on property:sys.usb.config=none && property:sys.usb.configfs=1\n"
    b'    write /config/usb_gadget/g1/UDC "none"\n'
    b"    stop adbd\n"
    b"    stop fastbootd\n"
    b"    setprop sys.usb.ffs.ready 0\n"
    b"    rm /config/usb_gadget/g1/configs/b.1/f1\n"
)
CLEANUP_MTP = (
    b"    setprop sys.usb.ffs.mtp.ready 0\n"
    b"    rm /config/usb_gadget/g1/configs/b.1/f2\n"
)


def build(base: Path, output: Path):
    require(base.resolve() != output.resolve(), "output must not overwrite base")
    data = base.read_bytes()
    require(digest(data) == BASE_SHA, "expected the exact v3.40-rc1 image")
    info, avb = layout(data), verify_avb(data)
    f0, f1 = info["fragments"]
    entries = cpio_entries(decompress(f0))
    files = {e["name"]: e["body"] for e in entries + cpio_entries(decompress(f1))}
    for hardware in ("mt6991", "mt8799"):
        rc = files[f"init.recovery.{hardware}.rc"]
        require(b"setprop sys.usb.configfs 1" in rc and
                b'setprop sys.usb.controller "16701000.usb0"' in rc,
                f"unexpected USB configuration for {hardware}")
    require(b"/dev/usb-ffs/mtp/ep0\0" in files[MTP] and
            b"sys.usb.ffs.mtp.ready\0" in files[MTP], "missing MTP FunctionFS backend")
    require(not any(b"sys.usb.config=mtp,adb" in body for name, body in files.items()
                    if name.endswith(".rc")), "duplicate composite trigger")
    old_init = files[INIT]
    require(old_init.count(CLEANUP) == 1, "unexpected ConfigFS cleanup")
    new_init = old_init.replace(CLEANUP, CLEANUP + CLEANUP_MTP).rstrip(b"\n")
    new_init += b"\n\n" + (HERE / "mtp-adb.rc").read_bytes()
    packed = compress(pack_cpio(entries, {INIT: new_init}, []))
    result = repack_image(data, info, avb, [packed, f1])
    fresh = layout(result)
    require(data[:24] == result[:24] and data[28:4096] == result[28:4096],
            "unexpected vendor boot header change")
    new_f0, new_f1 = fresh["fragments"]
    require(new_f1 == f1, "second ramdisk changed")
    actual = cpio_entries(decompress(new_f0))
    require([e["name"] for e in actual] == [e["name"] for e in entries], "archive entries changed")
    for old, new in zip(entries, actual):
        name = old["name"]
        if name == INIT:
            require(new["body"] == new_init, "incorrect init replacement")
        else:
            require(new["raw"] == old["raw"], f"unexpected change: {name}")
    report = dict(version="v3.40-rc2", status="AWAITING_DEVICE_ACCEPTANCE",
                  partition="vendor_boot", base_sha256=BASE_SHA, image_sha256=digest(result),
                  size=len(result), changed=[INIT], avb_hash_verified=True,
                  recovery_ramdisk_unchanged=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    output.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.output)
