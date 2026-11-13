#!/usr/bin/env python3
"""Offline regression tests for Skyward module synchronization; no image/flash."""
import ctypes
import ctypes.util
import os
from pathlib import Path
import tempfile
import unittest

from tools.sync_skyward_modules import align, apply_overlay, blob, compare, cpio_files, uncompress_legacy


class SkywardModuleSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tree = Path(self.tmp.name)
        (self.tree / "BoardConfig.mk").write_text("DEVICE_PATH := device/xiaomi/turner\n")
        self.folder = self.tree / "recovery/root/lib/modules"
        self.folder.mkdir(parents=True)
        self.modules = {
            "a.ko": b"new driver A",
            "b.ko": b"new driver B",
            "modules.alias": b"alias foo bar\n",
            "modules.dep": b"a.ko:\nb.ko: a.ko\n",
            "modules.load": b"a.ko\nb.ko\n",
            "modules.load.recovery": b"a.ko\n",
            "modules.softdep": b"",
        }
        for name, content in self.modules.items():
            (self.folder / name).write_bytes(content)

    def test_initially_same(self):
        self.assertEqual([], compare(self.tree, self.modules))

    def test_detect_then_apply_then_verify(self):
        (self.folder / "a.ko").write_bytes(b"old driver A")
        differences = compare(self.tree, self.modules)
        self.assertEqual(["a.ko"], [item["name"] for item in differences])
        self.assertEqual(blob(b"old driver A"), differences[0]["original_git_blob"])
        apply_overlay(self.tree, self.modules, differences)
        self.assertEqual([], compare(self.tree, self.modules))

    def test_fails_closed_on_metadata_mismatch(self):
        (self.folder / "modules.dep").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "metadata"):
            compare(self.tree, self.modules)

    def test_fails_closed_on_missing_module(self):
        (self.folder / "b.ko").unlink()
        with self.assertRaisesRegex(ValueError, "module names differ"):
            compare(self.tree, self.modules)

    def test_fails_closed_on_symlink_module(self):
        (self.folder / "a.ko").unlink()
        (self.folder / "a.ko").symlink_to("b.ko")
        with self.assertRaises(ValueError):
            compare(self.tree, self.modules)

    def test_newc_rejects_path_traversal(self):
        def newc(name, content):
            nums = [1, 0o100644, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name) + 1, 0]
            header = b"070701" + b"".join(f"{n:08x}".encode() for n in nums)
            blob = header + name.encode() + b"\0"
            blob += b"\0" * (align(len(blob), 4) - len(blob))
            blob += content
            return blob + b"\0" * (align(len(blob), 4) - len(blob))
        with self.assertRaisesRegex(ValueError, "unsafe"):
            cpio_files(newc("../escape.ko", b"bad"))

    def test_legacy_lz4_decompression(self):
        library = ctypes.util.find_library("lz4")
        if library is None:
            self.skipTest("liblz4 missing")
        lib = ctypes.CDLL(library)
        fn = lib.LZ4_compress_default
        fn.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        fn.restype = ctypes.c_int
        source = b"070701" * 100
        result = ctypes.create_string_buffer(len(source) * 2)
        size = fn(source, result, len(source), len(result))
        self.assertGreater(size, 0)
        frame = bytes.fromhex("02214c18") + size.to_bytes(4, "little") + result.raw[:size]
        self.assertEqual(source, uncompress_legacy(frame))


if __name__ == "__main__":
    unittest.main()
