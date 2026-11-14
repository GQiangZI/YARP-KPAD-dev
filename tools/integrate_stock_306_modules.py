#!/usr/bin/env python3
"""Recover the exact Skyward 306 module bytes from a stock vendor_boot.
No source changes unless an exact 279-file reference fingerprint matches.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from check_skyward_module_set import (
    REFERENCE_MODULES_SHA256, REFERENCE_ALL_SHA256, METADATA, MODULE_COUNT,
    fingerprint,
)
from sync_skyward_modules import cpio_files

PREFIX = Path("recovery/root/lib/modules")
ROM = "OS3.0.306.0.WAOCNXM"
DTB_SHA = "4f985cad82176ea746ffef6aa960269ef0aec410f294bc157bd766ad74f49bc0"


def module_files(image):
    raw = image.read_bytes()
    if len(raw) < 4096 or raw[:8] != b"VNDRBOOT":
        raise ValueError("not a vendor_boot image")
    num = lambda off: struct.unpack_from("<I", raw, off)[0]
    v, page, total, header, dtb_size = (num(n) for n in (8, 12, 24, 2096, 2100))
    if v != 4 or page != 4096 or header != 2128:
        raise ValueError("unexpected turner vendor_boot header")
    align = lambda n: (n + page - 1) // page * page
    start = align(header)
    dtb_start = start + align(total)
    table = dtb_start + align(dtb_size)
    size, count, entry = (num(n) for n in (2112, 2116, 2120))
    if not 0 < count <= 16 or entry != 108 or size != count * entry or table + size > len(raw):
        raise ValueError("invalid vendor ramdisk table")
    if hashlib.sha256(raw[dtb_start:dtb_start + dtb_size]).hexdigest() != DTB_SHA:
        raise ValueError("stock DTB differs from Skyward reference")
    files = {}
    for i in range(count):
        length, offset, kind = struct.unpack_from("<III", raw, table + i * entry)
        if not length or offset + length > total:
            raise ValueError("invalid ramdisk bounds")
        # Only stock NONE/PLATFORM/RECOVERY fragments. Never execute their contents.
        if kind not in (0, 1, 2):
            continue
        part = raw[start + offset:start + offset + length]
        if part.startswith((b"\x02\x21\x4c\x18", b"\x04\x22\x4d\x18")):
            part = subprocess.run(["lz4", "-dc"], input=part, capture_output=True, check=True).stdout
        elif part.startswith(b"\x1f\x8b"):
            part = gzip.decompress(part)
        for path, data in cpio_files(part).items():
            p = Path(path)
            if len(p.parts) != 3 or p.parts[:2] != ("lib", "modules"):
                continue
            name = p.name
            if not (name.endswith(".ko") or name in METADATA):
                continue
            if name in files and files[name] != data:
                raise ValueError("conflicting module in vendor ramdisk fragments: " + name)
            files[name] = data
    return files


def verify(folder):
    entries = list(folder.iterdir())
    if any(not p.is_file() or p.is_symlink() for p in entries):
        raise ValueError("non-regular module entry")
    mods = [p for p in entries if p.name.endswith(".ko")]
    if len(mods) != MODULE_COUNT or {p.name for p in entries if p not in mods} != set(METADATA):
        raise ValueError("expected exactly 274 modules and five metadata files")
    module_fp, all_fp = fingerprint(mods), fingerprint(entries)
    if (module_fp, all_fp) != (REFERENCE_MODULES_SHA256, REFERENCE_ALL_SHA256):
        raise ValueError("stock firmware bytes do not match Skyward: " + module_fp + " / " + all_fp)
    return {"kernel_modules": len(mods), "metadata_files": 5,
            "module_set_sha256": module_fp, "full_set_sha256": all_fp}


def extract(image, output):
    if output.exists():
        raise ValueError("output directory already exists")
    files = module_files(image)
    output.mkdir(parents=True)
    for name, data in files.items():
        (output / name).write_bytes(data)
    result = verify(output)
    result["source_vendor_boot_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    return result


def install(source, tree):
    result = verify(source)
    target = tree / PREFIX
    if not (tree / "BoardConfig.mk").is_file() or "turner" not in (tree / "board-info.txt").read_text():
        raise ValueError("not the turner tree")
    existing = list(target.iterdir())
    if any(not p.is_file() or p.is_symlink() for p in existing):
        raise ValueError("invalid checkout module entry")
    if {p.name for p in existing} != {p.name for p in source.iterdir()}:
        raise ValueError("module filenames differ")
    for name in METADATA:
        if (target / name).read_bytes() != (source / name).read_bytes():
            raise ValueError("dependency metadata differs: " + name)
    changed = sum(p.read_bytes() != (source / p.name).read_bytes() for p in existing)
    # No modifications before the entire incoming set has been verified.
    with tempfile.TemporaryDirectory(dir=target.parent, prefix="skyward-stock-stage-") as td:
        stage = Path(td) / "stage"
        old = Path(td) / "old"
        shutil.copytree(source, stage)
        verify(stage)
        target.rename(old)
        try:
            stage.rename(target)
            verify(target)
        except BaseException:
            if target.exists():
                target.rename(stage)
            old.rename(target)
            raise
    result.update({"status": "MODULE_BYTES_MATCH_ONLY_NOT_BUILT_OR_BOOT_TESTED",
                   "source_firmware": ROM, "changed_files": changed})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    e = sub.add_parser("extract")
    e.add_argument("image", type=Path)
    e.add_argument("output", type=Path)
    i = sub.add_parser("install")
    i.add_argument("source", type=Path)
    i.add_argument("--tree", type=Path, default=Path("."))
    i.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.mode == "extract":
            result = extract(a.image, a.output)
        else:
            result = install(a.source, a.tree)
            a.report.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, struct.error, subprocess.CalledProcessError) as exc:
        p.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
