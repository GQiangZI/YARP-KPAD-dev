#!/usr/bin/env python3
"""Verify that a turner device tree uses the complete Skyward 3.0.306 module set.

This checks content, not just the count/module.load references.
Expected SHA-256 is built from sorted (filename + NUL + raw SHA-256 bytes).
"""
import argparse
import hashlib
from pathlib import Path

REFERENCE_MODULES_SHA256 = "fc7683ba891f1b7bd833c3d75fd0064c76e31cf0b22f4f16be120e32d530cccb"
REFERENCE_ALL_SHA256 = "66812e332147fee97474c5b9538f54cb07ce9c3bd84af3b5788a67fc1c6d9c31"
METADATA = ("modules.alias", "modules.dep", "modules.load", "modules.load.recovery", "modules.softdep")
MODULE_COUNT = 274


def fingerprint(files):
    output = hashlib.sha256()
    for file in sorted(files, key=lambda p: p.name):
        output.update(file.name.encode("utf-8") + b"\0")
        file_sha = hashlib.sha256()
        with file.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                file_sha.update(chunk)
        output.update(file_sha.digest())
    return output.hexdigest()


def check(tree):
    root = Path(tree) / "recovery/root/lib/modules"
    modules = sorted(root.glob("*.ko"))
    metadata = [root / name for name in METADATA]
    if len(modules) != MODULE_COUNT or not all(path.is_file() for path in metadata):
        raise ValueError("incomplete module directory / dependency metadata")
    module_set = fingerprint(modules)
    all_set = fingerprint(modules + metadata)
    return module_set, all_set


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", default=".", help="turner device-tree root")
    parser.add_argument("--warn-only", action="store_true",
                        help="allow diagnostic builds but never claim module parity")
    args = parser.parse_args()
    try:
        modules, full = check(args.tree)
    except (OSError, ValueError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    if modules == REFERENCE_MODULES_SHA256 and full == REFERENCE_ALL_SHA256:
        print("PASS: complete 274-module set and five metadata files match boot-tested Skyward 3.0.306")
        return
    text = ("MODULE VERSION MISMATCH: current binaries do not match the 274-module "
            "Skyward OS3.0.306 set. Module-set SHA256=" + modules +
            " / full-set SHA256=" + full +
            ". Do not publish a flashable image from mixed/unknown driver versions.")
    if args.warn_only:
        print("WARNING: " + text)
    else:
        parser.exit(1, "FAIL: " + text + "\n")


if __name__ == "__main__":
    main()
