#!/usr/bin/env python3
"""Import the exact Skyward turner OS3.0.306 driver ZIP (source-only, no flashing)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

ZIP_SHA256 = '28ca760a4b6cc867c04493b6b29e0104b1ee1fd820a264b6c3169c336d811fad'
MODULE_FP = 'fc7683ba891f1b7bd833c3d75fd0064c76e31cf0b22f4f16be120e32d530cccb'
ALL_FP = '66812e332147fee97474c5b9538f54cb07ce9c3bd84af3b5788a67fc1c6d9c31'
FAST_SHA = '5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855'
SLOW_SHA = '9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a'
PLATFORM_SHA = '2330b412e7d93d81d0f336b5e2141e983a49d2e5483bdd526eebc2d34132c081'
PREFIX = 'recovery/root/lib/modules/'
META = {'modules.alias', 'modules.dep', 'modules.load', 'modules.load.recovery', 'modules.softdep'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(files, include_meta=True):
    h = hashlib.sha256()
    for name in sorted(files):
        if name in META and not include_meta:
            continue
        h.update(name.encode() + b'\0' + hashlib.sha256(files[name]).digest())
    return h.hexdigest()


def read_reference(zip_path):
    if sha(zip_path.read_bytes()) != ZIP_SHA256:
        raise ValueError('ZIP hash mismatch; only the pinned Skyward reference archive is accepted')
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        module_paths = [n for n in names if n.startswith(PREFIX)]
        if len(names) != len(set(names)) or set(names) != set(module_paths) | {'manifest.json', 'README.md'}:
            raise ValueError('archive has unexpected/duplicated files')
        if len(module_paths) != 279 or any(n != PREFIX + Path(n).name for n in module_paths):
            raise ValueError('expected exactly 279 safely named flat module/metadata files')
        files = {Path(n).name: z.read(n) for n in module_paths}
        if len(files) != 279 or len([n for n in files if n.endswith('.ko')]) != 274:
            raise ValueError('expected exactly 274 kernel modules')
        if set(files) != {n for n in files if n.endswith('.ko')} | META:
            raise ValueError('missing or unexpected module metadata')
        manifest = json.loads(z.read('manifest.json'))
        if (manifest.get('source_ramdisk_sha256'), manifest.get('image_sha256_fast'),
                manifest.get('image_sha256_slow'), manifest.get('file_count')) != (
                PLATFORM_SHA, FAST_SHA, SLOW_SHA, 279):
            raise ValueError('manifest provenance mismatch')
        listed = {x['path']: (x['size'], x['sha256']) for x in manifest['files']}
        if listed != {PREFIX + n: (len(v), sha(v)) for n, v in files.items()}:
            raise ValueError('individual file integrity mismatch')
    if fingerprint(files, False) != MODULE_FP or fingerprint(files) != ALL_FP:
        raise ValueError('complete Skyward kernel set fingerprint mismatch')
    return files


def apply(zip_path, tree, write=False):
    files = read_reference(zip_path)
    target = tree / PREFIX
    if not (tree / 'BoardConfig.mk').is_file() or 'turner' not in (tree / 'board-info.txt').read_text():
        raise ValueError('target is not the turner device tree')
    if not target.is_dir():
        raise ValueError('missing module directory')
    if any(p.is_symlink() or not p.is_file() for p in target.iterdir()):
        raise ValueError('unexpected symlink or directory in target module set')
    current = {p.name: p.read_bytes() for p in target.iterdir()}
    if set(current) != set(files):
        raise ValueError('module filenames differ: incomplete or mixed baseline')
    if any(current[name] != files[name] for name in META):
        raise ValueError('module dependency metadata differs: unsafe to replace binaries')
    mismatches = sum(current[n] != files[n] for n in files if n.endswith('.ko'))
    if write and mismatches:
        # Verify every byte in staging BEFORE touching original modules.
        with tempfile.TemporaryDirectory(prefix='skyward-stage-', dir=target.parent) as tmp:
            stage, backup = Path(tmp) / 'stage', Path(tmp) / 'backup'
            stage.mkdir()
            for name, data in files.items():
                (stage / name).write_bytes(data)
                (stage / name).chmod((target / name).stat().st_mode & 0o777)
            staged = {p.name: p.read_bytes() for p in stage.iterdir()}
            if fingerprint(staged) != ALL_FP:
                raise ValueError('staging checksum mismatch')
            os.rename(target, backup)
            try:
                os.rename(stage, target)
                actual = {p.name: p.read_bytes() for p in target.iterdir()}
                if fingerprint(actual) != ALL_FP:
                    raise ValueError('installed module fingerprint mismatch')
            except BaseException:
                if target.exists():
                    os.rename(target, stage)
                os.rename(backup, target)
                raise
    return {
        'device': 'Redmi K Pad (turner/MT6991)', 'source': 'Skyward OS3.0.306',
        'source_archive_sha256': ZIP_SHA256, 'source_platform_sha256': PLATFORM_SHA,
        'kernel_modules': 274, 'dependency_files': 5,
        'mismatches_before_import': mismatches, 'applied': bool(write and mismatches),
        'verified_complete_module_sha256': MODULE_FP,
        'status': 'SOURCE_ONLY_NOT_BUILT_OR_FLASH_TESTED'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--tree', type=Path, default=Path('.'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = apply(args.archive, args.tree.resolve(), args.apply)
        output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output, encoding='utf-8')
        print(output)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'FAIL: {error}\n')


if __name__ == '__main__':
    main()
