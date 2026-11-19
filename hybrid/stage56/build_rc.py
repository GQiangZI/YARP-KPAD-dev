#!/usr/bin/env python3
"""Add turner's A/B DTBO to the RC image's existing flash target list."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage48"))
from build import compress, cpio_entries, decompress, digest, layout
from build import pack_cpio, repack_image, require, verify_avb

BASE_SHA = "bbbe5faa0d3ebe4f04ebaabc51001355166e643146e45796ff6783a0b8271d70"
FLAGS = "system/etc/twrp.flags"
FSTAB = "system/etc/recovery.fstab"
DTBO_FSTAB = b"/dev/block/by-name/dtbo /dtbo emmc defaults slotselect"
DTBO_FLAGS = b'/dtbo emmc /dev/block/by-name/dtbo flags=display="DTBO";flashimg=1'
VB_FLAGS = b'/vendor_boot emmc /dev/block/by-name/vendor_boot flags=display="Vendor Boot";flashimg=1'


def build(base: Path, output: Path):
    require(base.resolve() != output.resolve(), "output must not overwrite base")
    data = base.read_bytes()
    require(digest(data) == BASE_SHA, "expected the exact v3.39 base")
    info, avb = layout(data), verify_avb(data)
    f0, f1 = info["fragments"]
    entries = cpio_entries(decompress(f1))
    files = {e["name"]: e["body"] for e in entries}
    require(VB_FLAGS in files[FLAGS].splitlines(), "missing v3.39 Vendor Boot target")
    require(not any(line.split()[:1] == [b"/dtbo"] for line in files[FLAGS].splitlines()),
            "duplicate DTBO flags entry")
    require(not any(line.split()[1:2] == [b"/dtbo"] for line in files[FSTAB].splitlines()),
            "duplicate DTBO fstab entry")
    replacements = {
        FSTAB: files[FSTAB].rstrip(b"\n") + b"\n" + DTBO_FSTAB + b"\n",
        FLAGS: files[FLAGS].rstrip(b"\n") + b"\n" + DTBO_FLAGS + b"\n",
    }
    result = repack_image(data, info, avb, [
        f0, compress(pack_cpio(entries, replacements, [])),
    ])
    new_f0, new_f1 = layout(result)["fragments"]
    require(new_f0 == f0, "first ramdisk changed")
    actual = cpio_entries(decompress(new_f1))
    require([e["name"] for e in actual] == [e["name"] for e in entries], "archive entries changed")
    for old, new in zip(entries, actual):
        name = old["name"]
        if name in replacements:
            require(new["body"] == replacements[name], f"incorrect change to {name}")
        else:
            require(new["raw"] == old["raw"], f"unexpected change to {name}")
    report = dict(version="v3.40-rc1", status="AWAITING_DEVICE_ACCEPTANCE",
                  partition="vendor_boot", base_sha256=BASE_SHA, image_sha256=digest(result),
                  size=len(result), changed=sorted(replacements),
                  targets=["Boot", "Init Boot", "Vendor Boot", "DTBO", "Super"],
                  avb_hash_verified=True)
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
