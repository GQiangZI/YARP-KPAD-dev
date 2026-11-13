#!/usr/bin/env python3
"""Read-only safety check for Redmi K Pad (turner) vendor_boot v4 images."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

SIZE = 64 * 1024 * 1024
LZ4_LEGACY = b'\x02\x21\x4c\x18'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse(path):
    image = Path(path).read_bytes()
    if len(image) != SIZE:
        raise ValueError(f'{path}: size {len(image)} != turner vendor_boot partition {SIZE}')
    if image[:8] != b'VNDRBOOT':
        raise ValueError(f'{path}: not a vendor_boot image')
    read32 = lambda o: struct.unpack_from('<I', image, o)[0]
    version, page = read32(8), read32(12)
    if version != 4 or page != 4096:
        raise ValueError(f'{path}: expected vendor_boot v4, 4096-byte pages; got v{version}, {page}')
    ramdisk_size, header_size, dtb_size = read32(24), read32(2096), read32(2100)
    table_size, table_count, entry_size, bootconfig_size = (read32(o) for o in (2112, 2116, 2120, 2124))
    if header_size != 2128 or table_count != 2 or entry_size != 108 or table_size != 216:
        raise ValueError(f'{path}: unexpected header/ramdisk-table dimensions')
    align = lambda n: ((n + page - 1) // page) * page
    ramdisk_start = align(header_size)
    dtb_start = ramdisk_start + align(ramdisk_size)
    table_start = dtb_start + align(dtb_size)
    bootconfig_start = table_start + align(table_size)
    if bootconfig_start + bootconfig_size > SIZE:
        raise ValueError(f'{path}: sections extend beyond partition size')
    fragments = []
    for i in range(table_count):
        off = table_start + i * entry_size
        length, offset, kind = struct.unpack_from('<III', image, off)
        name = image[off + 12:off + 44].split(b'\0', 1)[0].decode('ascii', errors='replace')
        if offset + length > ramdisk_size:
            raise ValueError(f'{path}: ramdisk entry {i} exceeds ramdisk area')
        payload = image[ramdisk_start + offset:ramdisk_start + offset + length]
        if not payload.startswith(LZ4_LEGACY):
            raise ValueError(f'{path}: fragment {i} is not LZ4 legacy compressed')
        fragments.append({'name': name, 'type': kind, 'size': length, 'sha256': sha(payload)})
    if [(f['type'], f['name']) for f in fragments] != [(1, ''), (2, 'recovery')]:
        raise ValueError(f'{path}: expected PLATFORM then RECOVERY fragments')
    return {
        'path': str(path), 'size': len(image), 'image_sha256': sha(image),
        'vendor_cmdline': image[28:2076].split(b'\0', 1)[0].decode('utf-8', errors='replace'),
        'fragments': fragments, 'dtb_sha256': sha(image[dtb_start:dtb_start + dtb_size]),
        'dtb_size': dtb_size, 'bootconfig_size': bootconfig_size,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--reference', type=Path, help='working Skyward/stock turner vendor_boot')
    args = parser.parse_args()
    try:
        result = parse(args.image)
        if args.reference:
            ref = parse(args.reference)
            for key in ('dtb_sha256', 'dtb_size', 'vendor_cmdline'):
                if result[key] != ref[key]:
                    raise ValueError(f'{key} differs from known-working reference')
            if result['fragments'][0]['sha256'] != ref['fragments'][0]['sha256']:
                raise ValueError('PLATFORM ramdisk differs from known-working reference')
            result['reference_check'] = 'PASS (DTB, cmdline, PLATFORM ramdisk)'
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, struct.error) as error:
        parser.exit(1, f'FAIL: {error}\n')


if __name__ == '__main__':
    main()
