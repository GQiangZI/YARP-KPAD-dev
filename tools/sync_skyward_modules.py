#!/usr/bin/env python3
"""Safely compare or replace local turner .ko files from verified Skyward images.

Default: read-only. --apply updates only a LOCAL checkout; no build or flash.
Needs liblz4 shared library (Ubuntu: liblz4-1).
"""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile

FAST = "5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855"
SLOW = "9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a"
PLATFORM_SHA = "2330b412e7d93d81d0f336b5e2141e983a49d2e5483bdd526eebc2d34132c081"
METADATA = {"modules.alias", "modules.dep", "modules.load", "modules.load.recovery", "modules.softdep"}
LZ4_MAGIC = bytes.fromhex("02214c18")


def align(n, a):
    return (n + a - 1) // a * a


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def uncompress_legacy(data):
    if not data.startswith(LZ4_MAGIC):
        raise ValueError("expected LZ4 legacy PLATFORM ramdisk")
    library = ctypes.util.find_library("lz4")
    if not library:
        raise ValueError("liblz4 not installed")
    fn = ctypes.CDLL(library).LZ4_decompress_safe
    fn.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    fn.restype = ctypes.c_int
    output = bytearray()
    offset = 4
    while offset < len(data):
        if offset + 4 > len(data):
            raise ValueError("truncated LZ4 legacy block")
        size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if not (0 < size <= 8 * 1024 * 1024) or offset + size > len(data):
            raise ValueError("invalid LZ4 legacy block size")
        destination = ctypes.create_string_buffer(8 * 1024 * 1024)
        written = fn(data[offset:offset + size], destination, size, len(destination))
        if written < 0:
            raise ValueError("invalid LZ4 compressed block")
        output.extend(destination.raw[:written])
        offset += size
    return bytes(output)


def cpio_files(payload):
    cursor, result = 0, {}
    while cursor < len(payload):
        if cursor + 110 > len(payload):
            raise ValueError("truncated CPIO newc header")
        header = payload[cursor:cursor + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError("invalid CPIO newc magic")
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        if not 0 < namesize < 4096:
            raise ValueError("invalid CPIO name length")
        end_name = cursor + 110 + namesize
        if end_name > len(payload) or payload[end_name - 1] != 0:
            raise ValueError("truncated CPIO name")
        name = payload[cursor + 110:end_name - 1].decode("utf-8")
        start = align(end_name, 4)
        end = start + size
        if end > len(payload):
            raise ValueError("truncated CPIO file")
        cursor = align(end, 4)
        if name == "TRAILER!!!":
            break
        if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
            raise ValueError("unsafe CPIO path")
        if stat.S_IFMT(mode) == stat.S_IFREG:
            if name in result:
                raise ValueError("duplicate CPIO path")
            result[name] = payload[start:end]
    return result


def read_modules(image):
    data = image.read_bytes()
    if len(data) != 67108864 or data[:8] != b"VNDRBOOT":
        raise ValueError("not a turner 64 MiB vendor_boot")
    source = digest(data)
    if source not in (FAST, SLOW):
        raise ValueError("image SHA-256 not a known-good Skyward fast/slow image")
    num = lambda off: struct.unpack_from("<I", data, off)[0]
    if (num(8), num(12), num(2096), num(2116), num(2120)) != (4, 4096, 2128, 2, 108):
        raise ValueError("unexpected vendor_boot v4 header/table")
    start = align(num(2096), num(12))
    table = start + align(num(24), num(12)) + align(num(2100), num(12))
    length, offset, kind = struct.unpack_from("<III", data, table)
    if kind != 1 or offset != 0 or not (0 < length <= num(24)):
        raise ValueError("unexpected PLATFORM ramdisk entry")
    platform = data[start:start + length]
    if digest(platform) != PLATFORM_SHA:
        raise ValueError("known-good PLATFORM payload hash mismatch")
    extracted = cpio_files(uncompress_legacy(platform))
    modules = {key.rsplit("/", 1)[-1]: value for key, value in extracted.items()
               if key.startswith("lib/modules/") and
               (key.endswith(".ko") or key.rsplit("/", 1)[-1] in METADATA)}
    if sum(name.endswith(".ko") for name in modules) != 274 or len(modules) != 279:
        raise ValueError("expected 274 drivers plus five module metadata files")
    return source, modules


def compare(tree, modules):
    folder = tree / "recovery/root/lib/modules"
    if not (tree / "BoardConfig.mk").is_file() or not folder.is_dir():
        raise ValueError("not a turner YARP checkout")
    expected = {name for name in modules if name.endswith(".ko")}
    actual = {path.name for path in folder.glob("*.ko") if path.is_file() and not path.is_symlink()}
    if expected != actual:
        raise ValueError("module names differ between image and local tree")
    changes = []
    for name, content in sorted(modules.items()):
        dest = folder / name
        if not dest.is_file() or dest.is_symlink():
            raise ValueError("missing or symlinked module metadata/file: " + name)
        original = dest.read_bytes()
        if name in METADATA and original != content:
            raise ValueError("module metadata differs; refusing mixed-version overlay: " + name)
        if original != content:
            changes.append({
                "name": name, "original_git_blob": blob(original),
                "skyward_git_blob": blob(content),
                "original_size": len(original), "skyward_size": len(content)
            })
    return changes


def apply_overlay(tree, modules, changes):
    folder = tree / "recovery/root/lib/modules"
    if (tree / ".git").exists():
        status = subprocess.run(
            ["git", "-C", str(tree), "status", "--porcelain", "--", "recovery/root/lib/modules"],
            capture_output=True, text=True, check=True)
        if status.stdout.strip():
            raise ValueError("module directory has uncommitted changes")
    with tempfile.TemporaryDirectory(prefix="skyward-module-stage-") as tmp:
        staging = Path(tmp)
        for item in changes:
            name = item["name"]
            (staging / name).write_bytes(modules[name])
            if blob((staging / name).read_bytes()) != item["skyward_git_blob"]:
                raise ValueError("staged module hash mismatch: " + name)
        for item in changes:
            name = item["name"]
            os.replace(staging / name, folder / name)
    if compare(tree, modules):
        raise ValueError("post-apply module hash verification failed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path)
    p.add_argument("--tree", type=Path, default=Path("."))
    p.add_argument("--apply", action="store_true",
                   help="opt-in replacement in a local checkout (never a flash operation)")
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    try:
        source, modules = read_modules(args.image)
        changes = compare(args.tree, modules)
        if args.apply and changes:
            apply_overlay(args.tree, modules, changes)
        report = {
            "device": "turner/MT6991",
            "image_sha256": source, "platform_sha256": PLATFORM_SHA,
            "module_count": 274, "dependency_metadata_identical": True,
            "mismatched_modules": len(changes), "changes": changes,
            "applied": bool(args.apply and changes),
            "status": "LOCAL_ONLY_NOT_BUILT_NOT_FLASH_TESTED"
        }
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding="utf-8")
        print(text)
    except (OSError, ValueError, RuntimeError, struct.error, subprocess.CalledProcessError) as exc:
        p.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
