#!/usr/bin/env python3
"""Strictly compare vendor_boot structure against the boot-tested Skyward PLATFORM.

This is only a structural test; it does not certify boot, crypto, or UI.
"""
import argparse
import sys

from verify_vendor_boot import parse

REFERENCE_PLATFORM_SHA256 = "2330b412e7d93d81d0f336b5e2141e983a49d2e5483bdd526eebc2d34132c081"
REFERENCE_DTB_SHA256 = "4f985cad82176ea746ffef6aa960269ef0aec410f294bc157bd766ad74f49bc0"
REQUIRED_CMDLINE = ("bootopt=64S3,32N2,64N2", "erofs.reserved_pages=64")


def check(path):
    result = parse(path)  # v4, 64MiB, two fragments, types and LZ4
    if result["fragments"][0]["sha256"] != REFERENCE_PLATFORM_SHA256:
        raise ValueError("PLATFORM ramdisk is not byte-identical to both working Skyward images")
    if result["dtb_sha256"] != REFERENCE_DTB_SHA256:
        raise ValueError("DTB differs from both working Skyward images")
    for token in REQUIRED_CMDLINE:
        if token not in result["vendor_cmdline"]:
            raise ValueError("required boot command-line token missing: " + token)
    print("PASS: structurally matches known-good Skyward PLATFORM, DTB and required cmdline")
    print("WARNING: this is not a hardware boot or decryption test")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    try:
        check(args.image)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
