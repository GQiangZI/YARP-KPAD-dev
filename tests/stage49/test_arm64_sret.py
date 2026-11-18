#!/usr/bin/env python3
"""Execute the actual ARM64 result adapters and check their ABI register mapping.

Usage: test_arm64_sret.py production.so abi-test.so
The second ELF includes a two-instruction echo callee. No Android runtime is emulated.
"""
from pathlib import Path
import struct
import sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                UC_ARM64_REG_X3, UC_ARM64_REG_X30, UC_ARM64_REG_SP)


def symbols(path):
    with path.open("rb") as file:
        elf = ELFFile(file)
        table = {s.name: s for s in elf.get_section_by_name(".dynsym").iter_symbols()}
        result = {}
        for name in ("turner_sret0", "turner_sret2", "turner_abi_echo"):
            if name not in table:
                continue
            s = table[name]
            for seg in elf.iter_segments():
                if (seg["p_type"] == "PT_LOAD" and
                        seg["p_vaddr"] <= s["st_value"] < seg["p_vaddr"] + seg["p_filesz"]):
                    offset = seg["p_offset"] + s["st_value"] - seg["p_vaddr"]
                    file.seek(offset)
                    result[name] = file.read(s["st_size"])
                    break
        return result


def main():
    production, test = map(lambda p: symbols(Path(p)), sys.argv[1:])
    for name in ("turner_sret0", "turner_sret2"):
        assert production[name] == test[name], "test helper differs from production"
    for name in ("turner_sret0", "turner_sret2"):
        u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        u.mem_map(0x10000, 0x10000)
        entry, callee, output, halt = 0x11000, 0x12000, 0x13000, 0x14000
        u.mem_write(entry, production[name])
        u.mem_write(callee, test["turner_abi_echo"])
        u.reg_write(UC_ARM64_REG_X0, callee)
        u.reg_write(UC_ARM64_REG_X1, output)
        u.reg_write(UC_ARM64_REG_X2, 0xABCDEF)
        u.reg_write(UC_ARM64_REG_X3, 0)
        u.reg_write(UC_ARM64_REG_X30, halt)
        u.reg_write(UC_ARM64_REG_SP, 0x1F000)
        u.emu_start(entry, halt, count=30)
        got = struct.unpack("<QQ", bytes(u.mem_read(output, 16)))
        assert got == ((callee, output) if name == "turner_sret0" else (0xABCDEF, 0)), got
        assert u.reg_read(UC_ARM64_REG_SP) == 0x1F000, "stack changed"
        assert u.reg_read(UC_ARM64_REG_X30) == halt, "return address changed"
        print("PASS:", name, "indirect result, arguments, stack and return address")


if __name__ == "__main__":
    main()
