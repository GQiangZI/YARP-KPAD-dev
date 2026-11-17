# v3.9 independent verification — 2026-11-16 11:32 CST (proactivity research run)

Checked the staged image in `~/workspace/yarp-hybrid/stage25/` against what was
delivered to the user at 11:12 CST. All claims hold; no defect found.

- Image sha256 (full): `95f4fe8f22de253290e1f034bebb3835819e729217e85326998016402f1dcfba`
  — matches the delivered prefix `95f4fe8f…`. Size 67,108,864 B (64 MiB).
- v3.8 image sha256: `8e38b16d25cec6592a556bc2b955d1a509f03a64677b56d7a179974433b7a6d5`
  — matches its delivered prefix `8e38b16d…`.
- F0 identical: `stage24/.work/f0.lz4` and `stage25/.work/f0.lz4` share sha256
  `ac41ecd25dea9cf5e79622ea6c74b04a9ba1fd32b28284db543ac8333a66a3ca`
  (includes the servicemanager VINTF patch from v3.6/v3.7).
- F1 cpio (244 entries each): the ONLY differing file is
  `system/etc/hybrid/liblogcapture.so` — v38 68,184 B sha16 `51aed99415afa22e`,
  v39 68,840 B sha16 `b41fd8ddd702bce4`, matching the standalone .so files in
  each stage dir. Symlinks (`init`, `twrpbinder/libbinder.so`,
  `twrpbinder/libbinder_ndk.so`) have identical targets in both.
- liblogcapture v4 exports all 5 Accessor symbols
  (`addAccessorProvider`, `removeAccessorProvider`, `createAccessor`,
  `delegateAccessor`, `validateAccessor`) plus
  `android::binder::os::get_trace_enabled_tags`; the stub zeroes the sret
  buffer (x8) when present and returns 0. Source: `stage25/liblogcapture.c`
  lines 117–143.

Note: raw byte diff of the two .img files spans almost the whole file — expected,
the LZ4-compressed ramdisk re-compresses after one changed file; the cpio-level
comparison above is the meaningful check.

Status: v3.9 is exactly v3.8 + liblogcapture v4 as delivered. Awaiting the user's
flash + v39 logs. Link expires 2026-11-18 11:12 CST.
