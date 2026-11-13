#!/usr/bin/env python3
"""Extract turner Skyward vendor_boot v4 parts read-only with pinned-image validation.

Produces DTB and unmodified LZ4-compressed PLATFORM/RECOVERY fragments.
Does NOT build a new vendor_boot.img or approve any image for flashing.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from verify_vendor_boot import parse

KNOWN = {
    "5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855": "fast",
    "9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a": "slow",
}


def align(value, page):
    return (value + page - 1) // page * page


def store_exact(path, data):
    """No silently overwriting files with different bytes."""
    if path.exists():
        if path.is_dir() or path.read_bytes() != data:
            raise ValueError(f"refusing to overwrite mismatched file: {path}")
    else:
        path.write_bytes(data)
    return {"path": path.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def extract(image_path, output_dir):
    summary = parse(image_path)  # v4, size, table and LZ4 format checks
    digest = summary["image_sha256"]
    if digest not in KNOWN:
        raise ValueError("unrecognized image SHA-256; only the two known turner Skyward images are accepted")
    raw = image_path.read_bytes()
    page = struct.unpack_from("<I", raw, 12)[0]
    ramdisk_size = struct.unpack_from("<I", raw, 24)[0]
    header_size = struct.unpack_from("<I", raw, 2096)[0]
    dtb_size = struct.unpack_from("<I", raw, 2100)[0]
    ramdisk_start = align(header_size, page)
    dtb_start = ramdisk_start + align(ramdisk_size, page)
    table_start = dtb_start + align(dtb_size, page)
    entries = []
    for index in range(2):
        length, offset, kind = struct.unpack_from("<III", raw, table_start + index * 108)
        name = "platform_ramdisk.lz4" if kind == 1 else "recovery_ramdisk.lz4"
        payload = raw[ramdisk_start + offset:ramdisk_start + offset + length]
        entry = {"name": name, "bytes": payload}
        if hashlib.sha256(payload).hexdigest() != summary["fragments"][index]["sha256"]:
            raise ValueError(f"ramdisk {index} hash mismatch before export")
        entries.append(entry)
    dtb = raw[dtb_start:dtb_start + dtb_size]
    if hashlib.sha256(dtb).hexdigest() != summary["dtb_sha256"]:
        raise ValueError("DTB hash mismatch before export")
    out = output_dir / KNOWN[digest]
    out.mkdir(parents=True, exist_ok=True)
    items = [store_exact(out / entry["name"], entry["bytes"]) for entry in entries]
    items.append(store_exact(out / "dtb", dtb))
    result = {
        "device": "turner", "source_variant": KNOWN[digest],
        "source_image_sha256": digest, "status": "REFERENCE_ONLY_NOT_FLASHABLE",
        "files": items,
    }
    manifest = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
    store_exact(out / "manifest.json", manifest)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="known turner Skyward 64 MiB vendor_boot image")
    parser.add_argument("--output-dir", type=Path, required=True, help="local export root")
    args = parser.parse_args()
    try:
        result = extract(args.image, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, struct.error) as exc:
        parser.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
