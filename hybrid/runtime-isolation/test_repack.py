# SPDX-License-Identifier: Apache-2.0
import hashlib, struct, unittest
import repack

class ArchiveTests(unittest.TestCase):
    def test_cpio_roundtrip_retains_ownership_and_link_metadata(self):
        rows=[]
        for i,(name,mode,body) in enumerate([('system',0o40755,b''),('system/tool',0o100755,b'hello'),('system/link',0o120777,b'tool')]):
            fields=[i+1,mode,1000,2000,1,1700000000,len(body),0,0,0,0,len(name)+1,0]
            rows.append((name,fields,body))
        self.assertEqual(repack.read_cpio(repack.write_cpio(rows)),rows)

    def test_legacy_lz4_multiblock_preserves_final_short_block(self):
        raw=(bytes(range(256))*32768)+b'final-short-block'
        self.assertEqual(repack.decompress(repack.compress(raw)),raw)

    def test_truncated_legacy_block_is_rejected(self):
        with self.assertRaises(AssertionError):repack.decompress(bytes.fromhex('02214c18')+struct.pack('<I',100)+b'x')

    def test_wrong_display_library_is_rejected(self):
        from patch_display import patch
        with self.assertRaises(AssertionError):patch(b'unrelated-build')

if __name__=='__main__':unittest.main()
