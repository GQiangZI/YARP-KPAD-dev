"""Synthetic tests for Skyward ZIP integration; never builds or flashes images."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parent))
from apply_verified_skyward_zip import (
    FAST_SHA, META, PLATFORM_SHA, PREFIX, SLOW_SHA, apply, fingerprint,
)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'BoardConfig.mk').write_text('DEVICE_PATH := device/xiaomi/turner\n')
        (self.root / 'board-info.txt').write_text('require board=turner|25079RPDCC\n')
        self.folder = self.root / PREFIX
        self.folder.mkdir(parents=True)
        self.data = {f'module_{i:03d}.ko': f'driver{i}'.encode() for i in range(274)}
        for name in META:
            self.data[name] = b'foo' + name.encode()
        for name, payload in self.data.items():
            (self.folder / name).write_bytes(payload)
        self.zip_path = self.root / 'reference.zip'
        manifest = dict(
            image_sha256_fast=FAST_SHA, image_sha256_slow=SLOW_SHA,
            source_ramdisk_sha256=PLATFORM_SHA, file_count=279,
            files=[{'path': PREFIX + name, 'size': len(payload),
                    'sha256': hashlib.sha256(payload).hexdigest()}
                   for name, payload in self.data.items()],
        )
        with zipfile.ZipFile(self.zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('README.md', 'Synthetic fixture')
            archive.writestr('manifest.json', json.dumps(manifest))
            for name, payload in self.data.items():
                archive.writestr(PREFIX + name, payload)
        self.patches = (
            patch('apply_verified_skyward_zip.ZIP_SHA256', hashlib.sha256(self.zip_path.read_bytes()).hexdigest()),
            patch('apply_verified_skyward_zip.MODULE_FP', fingerprint(self.data, False)),
            patch('apply_verified_skyward_zip.ALL_FP', fingerprint(self.data, True)),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_dry_run_does_not_write(self):
        (self.folder / 'module_000.ko').write_bytes(b'old driver')
        result = apply(self.zip_path, self.root, False)
        self.assertEqual(result['mismatches_before_import'], 1)
        self.assertEqual((self.folder / 'module_000.ko').read_bytes(), b'old driver')

    def test_full_import_is_idempotent(self):
        (self.folder / 'module_000.ko').write_bytes(b'old driver')
        result = apply(self.zip_path, self.root, True)
        self.assertTrue(result['applied'])
        self.assertEqual(apply(self.zip_path, self.root, False)['mismatches_before_import'], 0)
        self.assertEqual(len(list(self.folder.glob('*.ko'))), 274)

    def test_metadata_conflict_refuses_write(self):
        (self.folder / 'modules.dep').write_bytes(b'wrong deps')
        with self.assertRaisesRegex(ValueError, 'dependency metadata'):
            apply(self.zip_path, self.root, True)

    def test_symlink_refuses_write(self):
        (self.folder / 'module_000.ko').unlink()
        (self.folder / 'module_000.ko').symlink_to('module_001.ko')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            apply(self.zip_path, self.root, True)

    def test_changed_archive_refuses_write(self):
        self.zip_path.write_bytes(self.zip_path.read_bytes() + b'corruption')
        with self.assertRaisesRegex(ValueError, 'ZIP hash mismatch'):
            apply(self.zip_path, self.root, True)


if __name__ == '__main__':
    unittest.main()
