#!/usr/bin/env python3
"""Build and package the native helper using the exact v3.36 Recovery libraries."""
import argparse
import base64
from io import BytesIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "stage48"))
from build import cpio_entries, decompress, digest, elf_exports, layout, verify_avb

BASE_SHA = "e215ee037e63c9d7ce6ff44694dcbad6ac39f93b75f695d0e8db12e857e3d125"
LIBRARIES = (
    "system/lib64/libc.so",
    "system/lib64/twrp16/libcutils.so",
    "system/lib64/twrp16/libselinux.so",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--elf", type=Path, help="Keep the executable for local validation")
    args = parser.parse_args()
    image = args.base.read_bytes()
    if digest(image) != BASE_SHA:
        parser.error("expected the hardware-tested v3.36 image")
    verify_avb(image)
    entries = {
        entry["name"]: entry["body"]
        for fragment in layout(image)["fragments"]
        for entry in cpio_entries(decompress(fragment))
    }
    with TemporaryDirectory(prefix="turner-prepare-") as scratch:
        dest = Path(scratch)
        libraries = []
        exports = set()
        for name in LIBRARIES:
            library = dest / Path(name).name
            body = entries[name]
            library.write_bytes(body)
            libraries.append(library)
            exports.update(elf_exports(body))
        executable = dest / "vold_prepare_subdirs"
        subprocess.run([
            sys.executable, "-m", "ziglang", "cc", "-target", "aarch64-linux-android",
            "-std=gnu11", "-Os", "-Wall", "-Wextra", "-Werror", "-ffreestanding",
            "-fno-stack-protector", "-nostdlib", "-fPIE", "-pie",
            "-Wl,--dynamic-linker=/system/bin/linker64", "-Wl,--allow-shlib-undefined",
            "-Wl,-z,relro,-z,now", "-Wl,-s",
            HERE / "bionic_start.c", HERE / "vold_prepare_subdirs.c",
            *libraries, "-o", executable,
        ], check=True)
        binary = executable.read_bytes()

    elf = ELFFile(BytesIO(binary))
    interpreter = next(s.get_interp_name() for s in elf.iter_segments() if s["p_type"] == "PT_INTERP")
    needed = {tag.needed for tag in elf.get_section_by_name(".dynamic").iter_tags("DT_NEEDED")}
    imports = {
        sym.name for sym in elf.get_section_by_name(".dynsym").iter_symbols()
        if sym.name and sym["st_shndx"] == "SHN_UNDEF"
    }
    if (elf["e_machine"], elf["e_type"], interpreter) != (
        "EM_AARCH64", "ET_DYN", "/system/bin/linker64"
    ) or needed != {Path(name).name for name in LIBRARIES} or imports - exports:
        raise ValueError("unexpected executable ABI, dependencies or unresolved imports")
    encoded = base64.b64encode(binary).decode("ascii")
    chunks = (encoded[i:i + 4096] for i in range(0, len(encoded), 4096))
    payload = "\n".join(f"    printf '%s\\n' '{chunk}'" for chunk in chunks)
    template = (HERE / "native-install.sh.in").read_text()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace("@SHA256@", digest(binary)).replace("@PAYLOAD@", payload))
    if args.elf:
        args.elf.write_bytes(binary)
        args.elf.chmod(0o755)
    print(f"{args.output} embeds {len(binary)} bytes, SHA256 {digest(binary)}")


if __name__ == "__main__":
    main()
