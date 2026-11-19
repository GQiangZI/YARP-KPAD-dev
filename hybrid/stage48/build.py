#!/usr/bin/env python3
"""Apply a small, reproducible delta to the exact, hardware-tested v3.30.

pip install lz4 pyelftools
python build.py --base BASE.img --bridge libturner_crypto.so --output OUTPUT.img
No OTA extraction, old workspace paths or historic stage binaries are needed.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct

import lz4.block
from elftools.elf.elffile import ELFFile

BASE_SHA = "aa0606d8d09d40f9988c8cd92b5c561e47360e6369bbca0f620b8730b219ae2d"
SIZE = 67108864
MAGIC = bytes.fromhex("02214c18")
HERE = Path(__file__).resolve().parent
V335 = "v3.35-CRYPTO-BRIDGE-TEST"
V336 = "v3.36-CRYPTO-LEGACY-TEST"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return sha256(data).hexdigest()


def align(n, a=4096):
    return (n + a - 1) // a * a


def decompress(data):
    require(data[:4] == MAGIC, "ramdisk is not legacy LZ4")
    out, pos = bytearray(), 4
    while pos < len(data):
        require(pos + 4 <= len(data), "truncated LZ4 block header")
        count, = struct.unpack_from("<I", data, pos)
        pos += 4
        require(0 < count <= len(data) - pos, "invalid LZ4 block length")
        out += lz4.block.decompress(data[pos:pos + count], uncompressed_size=8 * 1024 * 1024)
        pos += count
    return bytes(out)


def compress(data):
    out = bytearray(MAGIC)
    for pos in range(0, len(data), 8 * 1024 * 1024):
        block = lz4.block.compress(data[pos:pos + 8 * 1024 * 1024],
                                   mode="high_compression", compression=9, store_size=False)
        out += struct.pack("<I", len(block)) + block
    result = bytes(out)
    require(decompress(result) == data, "LZ4 round trip failed")
    return result


def cpio_entries(data):
    entries, pos = [], 0
    while True:
        require(data[pos:pos + 6] == b"070701", "not a newc archive")
        header = data[pos:pos + 110]
        f = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        start = align(pos + 110 + f[11], 4)
        end = align(start + f[6], 4)
        require(end <= len(data), "CPIO entry out of bounds")
        name = data[pos + 110:pos + 110 + f[11] - 1].decode()
        entries.append(dict(name=name, fields=f, body=data[start:start + f[6]],
                            header=header, raw=data[pos:end]))
        pos = end
        if name == "TRAILER!!!":
            require(not any(data[pos:]), "unexpected data after CPIO trailer")
            return entries


def new_entry(name, body, mode, ino):
    fields = [ino, mode, 0, 0, 1, 0, len(body), 0, 0, 0, 0, len(name.encode()) + 1, 0]
    return dict(name=name, body=body, fields=fields)


def pack_cpio(entries, replacements, additions):
    out = bytearray()
    for entry in entries[:-1] + additions + entries[-1:]:
        name = entry["name"]
        if name not in replacements and "raw" in entry:
            out += entry["raw"]
            continue
        body = replacements.get(name, entry["body"])
        fields = list(entry["fields"])
        fields[6] = len(body)
        out += b"070701" + b"".join(f"{v:08x}".encode() for v in fields)
        out += name.encode() + b"\0"
        out += b"\0" * (align(len(out), 4) - len(out))
        out += body
        out += b"\0" * (align(len(out), 4) - len(out))
    out += b"\0" * (align(len(out), 512) - len(out))
    result = bytes(out)
    parsed = cpio_entries(result)
    require(len(parsed) == len(entries) + len(additions), "CPIO count changed")
    return result


def layout(img):
    require(len(img) == SIZE and img[:8] == b"VNDRBOOT", "wrong image size/type")
    ver, page = struct.unpack_from("<II", img, 8)
    require((ver, page) == (4, 4096), "expected vendor_boot v4 / 4096")
    require(img[-64:-60] == b"AVBf", "missing AVB footer")
    original, vb_off, vb_size = struct.unpack_from(">QQQ", img, len(img) - 52)
    hs, ds = struct.unpack_from("<II", img, 2096)
    rs, = struct.unpack_from("<I", img, 24)
    table_size, count, es, bs = struct.unpack_from("<4I", img, 2112)
    require(hs == 2128 and count == 2 and es == 108 and bs == 0,
            "unexpected fragment table/bootconfig")
    require(table_size == count * es, "bad fragment table size")
    ramdisk = align(hs)
    dtb = align(ramdisk + rs)
    table = dtb + align(ds)
    require(table + table_size == original, "unexpected unsigned image tail")
    require(vb_off == align(original) and vb_size == 512, "unexpected AVB layout")
    fragments, cursor = [], 0
    for i in range(count):
        size, off, kind = struct.unpack_from("<3I", img, table + i * es)
        require(off == cursor and kind == i + 1, "unexpected fragment ordering")
        require(off + size <= rs, "fragment out of bounds")
        fragments.append(img[ramdisk + off:ramdisk + off + size])
        cursor += size
    require(cursor == rs, "fragment size mismatch")
    return dict(original=original, vb_off=vb_off, vb_size=vb_size, dtb=dtb,
                dtb_size=ds, table=table, table_size=table_size, fragments=fragments)


def verify_avb(img):
    info = layout(img)
    vb = img[info["vb_off"]:info["vb_off"] + info["vb_size"]]
    require(vb[:4] == b"AVB0", "missing VBMeta header")
    auth_size, aux_size, algorithm = struct.unpack_from(">QQI", vb, 12)
    require((auth_size, aux_size, algorithm) == (0, 256, 0),
            "base must use the verified unsigned AVB hash descriptor")
    offset, desc_size = struct.unpack_from(">QQ", vb, 96)
    require((offset, desc_size) == (0, 208), "unexpected AVB descriptors")
    at = 256 + auth_size + offset
    tag, following, image_size = struct.unpack_from(">QQQ", vb, at)
    require((tag, following) == (2, 192), "not an AVB hash descriptor")
    require(vb[at + 24:at + 56].rstrip(b"\0") == b"sha256", "unexpected AVB hash")
    pn, salt_len, hash_len, flags = struct.unpack_from(">4I", vb, at + 56)
    require((pn, salt_len, hash_len) == (11, 32, 32), "unexpected AVB hash fields")
    require(vb[at + 132:at + 132 + pn] == b"vendor_boot", "wrong AVB partition")
    salt_at = at + 132 + pn
    salt = vb[salt_at:salt_at + salt_len]
    stored = vb[salt_at + salt_len:salt_at + salt_len + hash_len]
    require(image_size == info["original"], "AVB image size mismatch")
    require(sha256(salt + img[:image_size]).digest() == stored, "AVB digest mismatch")
    return dict(vbmeta=vb, descriptor=at, salt_at=salt_at, salt=salt, flags=flags,
                hash=stored.hex())


def audit_elf(data):
    elf = ELFFile(BytesIO(data))
    require(elf["e_machine"] == "EM_AARCH64" and elf["e_type"] == "ET_DYN",
            "bridge is not an ARM64 shared object")
    symbols = {s.name: s for s in elf.get_section_by_name(".dynsym").iter_symbols()}
    for name in ("AServiceManager_checkService", "open", "open64", "fopen", "fopen64",
                 "__open_2", "openat", "__openat_2"):
        require(name in symbols and symbols[name]["st_shndx"] != "SHN_UNDEF",
                "missing bridge export " + name)
    require("turner_test_normalize" not in symbols, "test build supplied as production bridge")
    needed = [t.needed for t in elf.get_section_by_name(".dynamic").iter_tags("DT_NEEDED")]
    require(not needed, "bridge must not pull in another libc/Binder stack")
    return sorted(s.name for s in symbols.values()
                  if s["st_shndx"] == "SHN_UNDEF" and s.name)


def elf_exports(data):
    elf = ELFFile(BytesIO(data))
    return {s.name for s in elf.get_section_by_name(".dynsym").iter_symbols()
            if s["st_shndx"] != "SHN_UNDEF"}


def build(base, bridge, output, release=V335):
    require(base.resolve() != output.resolve(), "output must not overwrite base")
    data = base.read_bytes()
    require(digest(data) == BASE_SHA, "base is not the exact tested v3.30")
    info, avb = layout(data), verify_avb(data)
    shim = bridge.read_bytes()
    imports = audit_elf(shim)
    tag = release.split("-", 1)[0]
    require(f"TURNER-CRYPTO {tag}:".encode() in shim, "bridge version differs from image release")
    archives = [decompress(f) for f in info["fragments"]]
    entries = [cpio_entries(a) for a in archives]
    maps = [{e["name"]: e for e in es} for es in entries]
    merged = maps[0] | maps[1]
    # Validate every loader import against libraries already present in v3.30.
    exported = set()
    for name in ("system/lib64/libc.so", "system/lib64/libdl.so"):
        body = merged[name]["body"]
        if merged[name]["fields"][1] & 0o170000 == 0o120000:
            target = body.decode().lstrip("/")
            body = merged[target]["body"]
        exported.update(elf_exports(body))
    require(set(imports) <= exported, "unresolved bridge imports: " + str(set(imports) - exported))
    binder_exports = {}
    if release == V336:
        checks = {
            "libbinder.so": {
                "_ZN7android12ProcessState4selfEv",
                "_ZN7android12ProcessState23getStrongProxyForHandleEi",
            },
            "libbinder_ndk.so": {
                "_Z27AIBinder_fromPlatformBinderRKN7android2spINS_7IBinderEEE",
                "AIBinder_Class_define", "AIBinder_associateClass", "AIBinder_decStrong",
                "AIBinder_prepareTransaction", "AIBinder_transact", "AParcel_writeString",
                "AParcel_readStatusHeader", "AParcel_readStrongBinder", "AParcel_delete",
                "AStatus_isOk", "AStatus_delete", "AStatus_getStatus", "AStatus_getExceptionCode",
                "AServiceManager_checkService",
            },
        }
        for lib, required in checks.items():
            path = "system/lib64/twrp16/" + lib
            missing = required - elf_exports(merged[path]["body"])
            require(not missing, f"missing Binder exports in {path}: {sorted(missing)}")
            binder_exports[path] = sorted(required)

    rc_name = "system/etc/init/hw/init.rc"
    old_rc = maps[0][rc_name]["body"]
    marker = (b"service recovery /system/bin/recovery\n"
              b"    socket recovery stream 422 system system\n"
              b"    seclabel u:r:recovery:s0\n"
              b"    user root\n"
              b"    setenv LD_LIBRARY_PATH /system/lib64/twrp16:/system/lib64\n")
    require(old_rc.count(marker) == 1, "recovery service differs from v3.30")
    new_rc = old_rc.replace(marker, marker +
               b"    setenv LD_PRELOAD /system/etc/hybrid/libturner_crypto.so\n")
    status_script = (HERE / "turner-crypto-status.sh").read_bytes()
    if release == V336:
        status_script = status_script.replace(b"v3.35", b"v3.36").replace(b"v335", b"v336")
    additions = [
        new_entry("system/etc/hybrid/libturner_crypto.so", shim, 0o100644, 900001),
        new_entry("system/bin/turner-crypto-status.sh", status_script, 0o100755, 900002),
    ]
    require(not any(e["name"] in merged for e in additions), "bridge already exists")
    packed = [pack_cpio(entries[0], {rc_name: new_rc}, []),
              pack_cpio(entries[1], {}, additions)]
    result = repack_image(data, info, avb, [compress(a) for a in packed])
    fresh, checked = layout(result), verify_avb(result)
    changes = []
    for i in range(2):
        new_map = {e["name"]: e for e in cpio_entries(decompress(fresh["fragments"][i]))}
        require(set(maps[i]) <= set(new_map), "entry was removed")
        for name, original_entry in maps[i].items():
            updated = new_map[name]
            if updated["raw"] != original_entry["raw"]:
                require(i == 0 and name == rc_name and updated["body"] == new_rc,
                        "unexpected changed entry " + name)
                changes.append(dict(fragment=i, path=name, action="changed"))
        for name in sorted(set(new_map) - set(maps[i])):
            require(i == 1 and name in {e["name"] for e in additions}, "unexpected added entry")
            changes.append(dict(fragment=i, path=name, action="added"))
    require(len(changes) == 3, "unexpected delta count")
    report = dict(version=release, status="NOT_DEVICE_TESTED",
                  base_sha256=BASE_SHA, image_sha256=digest(result), size=len(result),
                  bridge_sha256=digest(shim), bridge_imports=imports,
                  avb_hash_verified=True, avb_authentication="NONE (same as input)",
                  avb_flags=checked["flags"], dtb_region_unchanged=True,
                  recovery_binary_unchanged=True, binder_libraries_unchanged=True,
                  existing_f1_entries_byte_identical=True, changes=changes,
                  partition_headroom=SIZE - fresh["vb_off"] - 512 - 64)
    if binder_exports:
        report["recovery_binder_exports_verified"] = binder_exports
        report["lookup_protocol"] = "Legacy CHECK_SERVICE (2) fallback after a null modern lookup"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    output.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def repack_image(data, info, avb, fragments):
    header = bytearray(data[:4096])
    struct.pack_into("<I", header, 24, sum(map(len, fragments)))
    table = bytearray(data[info["table"]:info["table"] + info["table_size"]])
    for i, fragment in enumerate(fragments):
        struct.pack_into("<II", table, 108 * i, len(fragment), sum(map(len, fragments[:i])))
    raw = bytearray(header + b"".join(fragments))
    raw += b"\0" * (align(len(raw)) - len(raw))
    raw += data[info["dtb"]:info["table"]]
    raw += table
    vb_offset = align(len(raw))
    require(vb_offset + 512 + 64 <= SIZE, "image does not fit; no output written")
    vb = bytearray(avb["vbmeta"])
    struct.pack_into(">Q", vb, avb["descriptor"] + 16, len(raw))
    h = avb["salt_at"] + len(avb["salt"])
    vb[h:h + 32] = sha256(avb["salt"] + raw).digest()
    result = bytearray(SIZE)
    result[:len(raw)] = raw
    result[vb_offset:vb_offset + 512] = vb
    result[-64:] = b"AVBf" + struct.pack(">IIQQQ", 1, 0, len(raw), vb_offset, 512) + b"\0" * 28
    result = bytes(result)
    fresh = layout(result)
    verify_avb(result)
    require(result[fresh["dtb"]:fresh["table"]] == data[info["dtb"]:info["table"]],
            "DTB region changed")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--bridge", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--release", choices=(V335, V336), default=V335)
    args = p.parse_args()
    build(args.base, args.bridge, args.output, args.release)
