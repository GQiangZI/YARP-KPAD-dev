#!/usr/bin/env python3
"""Replace only the ServiceManager compatibility bridge in v3.37."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage48"))
from build import audit_elf, compress, cpio_entries, decompress, digest, elf_exports
from build import layout, pack_cpio, repack_image, require, verify_avb

BASE_SHA = "66bb031fe750e506ec753d65a320ad0bdd010b94d1717ecf62dc2d932a8aad46"
BRIDGE = "system/etc/hybrid/libturner_crypto.so"
STATUS = "system/bin/turner-crypto-status.sh"


def build(base, bridge, output):
    require(base.resolve() != output.resolve(), "output must not overwrite base")
    data, new_bridge = base.read_bytes(), bridge.read_bytes()
    require(digest(data) == BASE_SHA, "expected the hardware-tested v3.37 image")
    imports = audit_elf(new_bridge)
    require(b"android.security.authorization\0" in new_bridge, "missing authorization lookup")
    info, avb = layout(data), verify_avb(data)
    f0, f1 = info["fragments"]
    entries = cpio_entries(decompress(f1))
    merged = {e["name"]: e["body"] for e in cpio_entries(decompress(f0)) + entries}
    exports = elf_exports(merged["system/lib64/libc.so"]) | elf_exports(merged["system/lib64/libdl.so"])
    require(set(imports) <= exports, "unresolved bridge imports")
    updated = {
        BRIDGE: new_bridge,
        STATUS: merged[STATUS].replace(b"v3.37", b"v3.38").replace(b"v337", b"v338"),
    }
    result = repack_image(data, info, avb, [f0, compress(pack_cpio(entries, updated, []))])
    new_f0, new_f1 = layout(result)["fragments"]
    require(new_f0 == f0, "first ramdisk changed")
    actual = {e["name"]: e for e in cpio_entries(decompress(new_f1))}
    require(set(actual) == {e["name"] for e in entries}, "unexpected ramdisk entries")
    for e in entries:
        name = e["name"]
        if name in updated:
            require(actual[name]["body"] == updated[name], f"replacement mismatch: {name}")
        else:
            require(actual[name]["raw"] == e["raw"], f"unexpected change: {name}")
    report = dict(version="v3.38-AUTH-LOOKUP-TEST", status="NOT_DEVICE_TESTED",
                  partition="vendor_boot", image_sha256=digest(result), base_sha256=BASE_SHA,
                  size=len(result), changed=sorted(updated), avb_hash_verified=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    output.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "bridge", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.bridge, args.output)
