#!/usr/bin/env python3
"""Expose the existing A/B vendor_boot partition in Install Image."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage48"))
from build import compress, cpio_entries, decompress, digest, layout
from build import pack_cpio, repack_image, require, verify_avb

BASE_SHA = "dd084d385827af9c62a87a735ce0788d5bfbd0a8db23ed82db2c7deee8648b0f"
FLAGS = "system/etc/twrp.flags"
FSTAB = "system/etc/recovery.fstab"
FLAG_LINE = (
    b'/vendor_boot emmc /dev/block/by-name/vendor_boot '
    b'flags=display="Vendor Boot";flashimg=1\n'
)


def build(base: Path, output: Path):
    require(base.resolve() != output.resolve(), "output must not overwrite base")
    data = base.read_bytes()
    require(digest(data) == BASE_SHA, "expected the hardware-tested v3.38 image")
    info, avb = layout(data), verify_avb(data)
    f0, f1 = info["fragments"]
    entries = cpio_entries(decompress(f1))
    files = {e["name"]: e["body"] for e in entries}
    matches = [line.split(maxsplit=4) for line in files[FSTAB].splitlines()
               if line.split()[:2] == [b"/dev/block/by-name/vendor_boot", b"/vendor_boot"]]
    require(len(matches) == 1 and matches[0][2] == b"emmc" and
            b"slotselect" in matches[0][4].split(b" ", 1)[0].split(b","),
            "vendor_boot must resolve using the existing A/B fstab entry")
    old_flags = files[FLAGS]
    require(not any(line.split()[:1] == [b"/vendor_boot"] for line in old_flags.splitlines()),
            "vendor_boot flags already present")
    new_flags = old_flags.rstrip(b"\n") + b"\n\n" + FLAG_LINE
    result = repack_image(data, info, avb, [
        f0, compress(pack_cpio(entries, {FLAGS: new_flags}, [])),
    ])
    new_f0, new_f1 = layout(result)["fragments"]
    require(new_f0 == f0, "first ramdisk changed")
    actual = cpio_entries(decompress(new_f1))
    require([e["name"] for e in actual] == [e["name"] for e in entries], "archive entries changed")
    for old, new in zip(entries, actual):
        if old["name"] == FLAGS:
            require(new["body"] == new_flags, "flags differ")
        else:
            require(new["raw"] == old["raw"], f"unexpected change: {old['name']}")
    report = dict(version="v3.39-VENDOR-BOOT-TEST", status="NOT_DEVICE_TESTED",
                  partition="vendor_boot", image_sha256=digest(result), base_sha256=BASE_SHA,
                  size=len(result), changed=[FLAGS], avb_hash_verified=True)
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
