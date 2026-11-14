#!/usr/bin/env python3
"""Audit a turner YARP image against hardware reference bytes, not its UI.
No claim of runtime ABI, boot, data decryption or flash safety.
"""
import argparse
import hashlib
from pathlib import Path
import struct

from verify_vendor_boot import parse
from sync_skyward_modules import cpio_files, uncompress_legacy
from check_skyward_module_set import (
    REFERENCE_MODULES_SHA256, REFERENCE_ALL_SHA256, METADATA, MODULE_COUNT,
)

REFERENCE_DTB_SHA256 = "4f985cad82176ea746ffef6aa960269ef0aec410f294bc157bd766ad74f49bc0"
REQUIRED_CMDLINE = ("bootopt=64S3,32N2,64N2", "erofs.reserved_pages=64")


def fingerprint(files):
    h = hashlib.sha256()
    for name, data in sorted(files.items()):
        h.update(name.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    return h.hexdigest()


def check(path, recovery_binary=None):
    result = parse(path)
    if result["dtb_sha256"] != REFERENCE_DTB_SHA256:
        raise ValueError("DTB differs from the turner hardware reference")
    for token in REQUIRED_CMDLINE:
        if token not in result["vendor_cmdline"].split():
            raise ValueError("required boot command-line token missing: " + token)

    image = Path(path).read_bytes()
    num = lambda off: struct.unpack_from("<I", image, off)[0]
    page = num(12)
    align = lambda n: (n + page - 1) // page * page
    start = align(num(2096))
    table = start + align(num(24)) + align(num(2100))
    module_files, merged = {}, {}
    ranges = []
    for i in range(num(2116)):
        length, offset, kind = struct.unpack_from("<III", image, table + i * num(2120))
        if not length or offset + length > num(24):
            raise ValueError("invalid ramdisk fragment")
        ranges.append((offset, offset + length))
        files = cpio_files(uncompress_legacy(image[start + offset:start + offset + length]))
        for name, data in files.items():
            merged[name] = data
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["lib", "modules"]:
                base = parts[-1]
                if base.endswith(".ko") or base in METADATA:
                    if base in module_files and module_files[base] != data:
                        raise ValueError("conflicting module copies across fragments: " + base)
                    module_files[base] = data
    if ranges[0][0] != 0 or ranges[0][1] != ranges[1][0] or ranges[1][1] != num(24):
        raise ValueError("fragment coverage is overlapping or incomplete")
    modules = {name: data for name, data in module_files.items() if name.endswith(".ko")}
    if (len(modules) != MODULE_COUNT or set(module_files) - set(modules) != set(METADATA)
            or fingerprint(modules) != REFERENCE_MODULES_SHA256
            or fingerprint(module_files) != REFERENCE_ALL_SHA256):
        raise ValueError("packaged module set does not match all 279 reference files")
    if recovery_binary:
        expected = Path(recovery_binary).read_bytes()
        executable = merged.get("system/bin/recovery")
        if not expected.startswith(b"\x7fELF") or executable != expected:
            raise ValueError("packaged recovery is not the supplied newly compiled YARP ELF")

    if image[-64:-60] != b"AVBf":
        raise ValueError("missing AVB footer")
    _, major, minor, original_size, vbmeta_offset, vbmeta_size, _ = struct.unpack(
        ">4sIIQQQ28s", image[-64:]
    )
    required_size = table + align(num(2112)) + align(num(2124))
    if major != 1 or vbmeta_size < 256 or not (
        required_size <= original_size <= vbmeta_offset
        and vbmeta_offset + vbmeta_size <= len(image) - 64
    ):
        raise ValueError("invalid AVB footer bounds")
    vbmeta = image[vbmeta_offset:vbmeta_offset + vbmeta_size]
    if vbmeta[:4] != b"AVB0":
        raise ValueError("AVB footer does not point to vbmeta")
    algorithm = struct.unpack_from(">I", vbmeta, 28)[0]
    print("PASS: 274 packaged modules + five metadata files, reference DTB and required cmdline")
    if recovery_binary:
        print("PASS: packaged recovery matches newly compiled ELF")
    print("AVB metadata algorithm:", algorithm, "(verify cryptography separately with avbtool)")
    print("NOT HARDWARE TESTED: native YARP PLATFORM is allowed to differ; no boot/decrypt claim")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path)
    p.add_argument("--recovery-binary", type=Path)
    a = p.parse_args()
    try:
        check(a.image, a.recovery_binary)
    except (OSError, ValueError, struct.error) as exc:
        p.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
