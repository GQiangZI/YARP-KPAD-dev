#!/usr/bin/env python3
"""Add the tested prepare helper and fix init's keystore2 lifecycle."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "stage48"))
from build import compress, cpio_entries, decompress, digest, layout, new_entry
from build import pack_cpio, repack_image, require, verify_avb

BASE_SHA = "e215ee037e63c9d7ce6ff44694dcbad6ac39f93b75f695d0e8db12e857e3d125"
PREPARE_SHA = "b6f620a7dc2b013ea6f8f517c6d00b21e8ac8bcb7a4441195c5f0fbf40861cac"
ORIGINAL_SERVICE = b"vendor.keystore2-sup"
RC = "system/etc/init/hybrid-services.rc"
SETUP = "system/bin/turner-setup.sh"
LAUNCHER = "system/bin/turner-ks2-sup.sh"
STATUS = "system/bin/turner-crypto-status.sh"
PREPARE = "system/bin/vold_prepare_subdirs"


def build(base: Path, prepare: Path, output: Path):
    require(base.resolve() != output.resolve(), "output must not overwrite base")
    data, helper = base.read_bytes(), prepare.read_bytes()
    require(digest(data) == BASE_SHA, "unexpected v3.36 base")
    require(digest(helper) == PREPARE_SHA, "expected the exact helper tested on-device")
    info, avb = layout(data), verify_avb(data)
    f0, f1 = info["fragments"]
    entries = cpio_entries(decompress(f1))
    files = {entry["name"]: entry for entry in entries}
    require(PREPARE not in files, "prepare helper already present")
    service = (b"service " + ORIGINAL_SERVICE + b" /system/bin/turner-ks2-sup.sh\n"
               b"    class hal\n    user root\n    group root system\n"
               b"    seclabel u:r:recovery:s0\n    disabled\n")
    rc = files[RC]["body"]
    require(rc.count(service) == 1, "unexpected keystore service stanza")
    setup = files[SETUP]["body"]
    require(setup.count(ORIGINAL_SERVICE) == 2, "unexpected keystore start or state checks")
    replacements = {
        RC: rc.replace(service, service.replace(ORIGINAL_SERVICE, b"keystore2")
                       .replace(b"group root system", b"group root root 1017 1007")),
        SETUP: setup.replace(ORIGINAL_SERVICE, b"keystore2"),
        LAUNCHER: (HERE / "keystore2-launch.sh").read_bytes(),
        STATUS: files[STATUS]["body"].replace(b"v3.36", b"v3.37").replace(b"v336", b"v337"),
    }
    addition = new_entry(PREPARE, helper, 0o100755, 900003)
    packed = compress(pack_cpio(entries, replacements, [addition]))
    result = repack_image(data, info, avb, [f0, packed])
    new_f0, new_f1 = layout(result)["fragments"]
    require(new_f0 == f0, "first fragment changed")
    actual = {entry["name"]: entry for entry in cpio_entries(decompress(new_f1))}
    require(set(actual) == set(files) | {PREPARE}, "unexpected archive entries")
    require(actual[PREPARE]["body"] == helper and actual[PREPARE]["fields"][1] == 0o100755,
            "prepare helper differs")
    for name, entry in files.items():
        if name in replacements:
            require(actual[name]["body"] == replacements[name], f"incorrect change to {name}")
        else:
            require(actual[name]["raw"] == entry["raw"], f"unexpected change to {name}")
    report = {
        "version": "v3.37-KEYSTORE-SYNC-TEST", "status": "NOT_DEVICE_TESTED",
        "partition": "vendor_boot", "image_sha256": digest(result), "size": len(result),
        "base_sha256": BASE_SHA, "prepare_sha256": PREPARE_SHA,
        "changed": sorted(replacements), "added": [PREPARE],
        "avb_hash_verified": True, "first_fragment_unchanged": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    output.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--prepare", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.prepare, args.output)
