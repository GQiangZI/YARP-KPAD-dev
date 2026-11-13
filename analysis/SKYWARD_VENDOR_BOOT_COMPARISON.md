# Skyward turner OS 3.0.306 vendor_boot comparison (local input images)

## Source integrity

| Variant | Image SHA-256 | Image size |
|---|---|---|
| fast | `5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855` | 67,108,864 bytes |
| slow | `9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a` | 67,108,864 bytes |

The following values were extracted directly from the two user-supplied images, without modifying them.

## Vendor Boot v4 layout

- Magic: `VNDRBOOT`; version: **4**; page size: **4096**.
- Vendor ramdisk table: **2 entries**, 108 bytes each (216 bytes total).
- DTB: **533,115 bytes**.
- Table offset: **59,203,584** bytes.
- Both images contain a PLATFORM ramdisk (type 1, blank name) followed by a RECOVERY ramdisk (type 2, name `recovery`).
- Both ramdisks start with the legacy LZ4 magic `02 21 4c 18`.

| Component | Fast size | Slow size | Fast SHA-256 | Slow SHA-256 |
|---|---:|---:|---|---|
| PLATFORM ramdisk | 34,368,249 | 34,368,249 | `2330b412e7d93d81d0f336b5e2141e983a49d2e5483bdd526eebc2d34132c081` | same |
| RECOVERY ramdisk | 24,292,818 | 24,292,629 | `6c04eccd81950e19d843f9534fad0090b68fcc194c7c1f4724259e43de0e0efd` | `69dd030e6a5ca6488bd22eecd9aab263b0bec3be0ac4f23c9889a2ca09af83f0` |

## Implications for YARP

1. **Preserve the PLATFORM ramdisk byte-for-byte** in the initial test image; it is identical in both Skyward variants.
2. The **RECOVERY** payload is the primary candidate for inspecting init services, HAL binaries, firmware dependencies and UI startup differences.
3. Do not assume the 189-byte difference in compressed RECOVERY payload explains the startup speed difference. Decompress and diff individual files, then obtain boot logs.
4. The output image must preserve the **two-entry vendor ramdisk table**, header v4, DTB, LZ4 format and 64 MiB partition bound.
5. This comparison establishes **structure**, not bootability or permission to distribute all embedded vendor binaries.

**Safety status: NOT FLASH READY.** No YARP output image has been built or tested.
