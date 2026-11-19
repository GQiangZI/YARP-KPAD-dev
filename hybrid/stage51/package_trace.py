#!/usr/bin/env python3
"""Embed a static AArch64 strace as short base64 chunks for mksh."""

import argparse
import base64
from hashlib import sha256
from pathlib import Path

from elftools.elf.elffile import ELFFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strace", type=Path, required=True)
    parser.add_argument("--license", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.strace.open("rb") as stream:
        elf = ELFFile(stream)
        if elf["e_machine"] != "EM_AARCH64" or any(
            segment["p_type"] in ("PT_INTERP", "PT_DYNAMIC") for segment in elf.iter_segments()
        ):
            raise ValueError("strace must be statically linked ARM64")

    binary = args.strace.read_bytes()
    encoded = base64.b64encode(binary).decode("ascii")
    chunks = (encoded[offset:offset + 8192] for offset in range(0, len(encoded), 8192))
    payload = "\n".join(f"    printf '%s\\n' '{chunk}'" for chunk in chunks)
    template = Path(__file__).with_name("fbe-trace.sh.in").read_text()
    body = template.replace("@PAYLOAD@", payload).replace("@SHA256@", sha256(binary).hexdigest())
    notice = "\n".join("# " + line for line in args.license.read_text().splitlines())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body + "\n# strace license\n" + notice + "\n")
    print(f"{args.output}: static ARM64 strace SHA256 {sha256(binary).hexdigest()}")


if __name__ == "__main__":
    main()
