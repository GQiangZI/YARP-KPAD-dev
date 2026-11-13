# Safety gate for turner vendor_boot development

**Development only — NOT FLASH-READY.** This repository is incomplete and no image built from it has been verified to boot on Redmi K Pad. Do not flash CI artifacts or redistribute them as stable releases.

## Non-negotiable checks before sharing a flashable image

1. Confirm target is Redmi K Pad **turner** (MT6991) and the stock firmware baseline matches the tested build.
2. Compare output against stock and working Skyward vendor_boot v4: header, page size, ramdisk table entry count/type/name, compression, DTB, command line, and total partition size (64 MiB).
3. Verify that PLATFORM ramdisk and required firmware, kernel modules, init services, and HAL dependencies are preserved. Never infer correctness from a successful compilation.
4. Verify first-stage fstab, A/B slot handling, dynamic partitions, metadata encryption, and AVB behavior.
5. Test boot, display, touch, adb, MTP, decryption, backup/restore, reboot, and normal OS boot on the exact device/firmware.
6. Provide recovery/rollback instructions and verified stock image backup **before** any flash testing.
7. Keep builds manually triggered; no automatic public release. Label untested artifacts `UNTESTED-DO-NOT-FLASH`.

## Source of binary dependencies

Use the user-supplied Skyward turner fast/slow vendor_boot images as analysis references. Import only required files after validating file identity, integrity, dependency closure and redistribution rights. Where redistribution rights are unclear, supply a deterministic extraction script and hashes rather than uploading binaries.

**Do not mix the fast and slow recovery payloads without a documented dependency analysis.** A bootable Skyward image does not establish that a transplanted YARP image will boot.

## Current state

Initial text files have been copied; full ramdisk/prebuilt/script migration and functional testing remain incomplete. No production image is approved.
