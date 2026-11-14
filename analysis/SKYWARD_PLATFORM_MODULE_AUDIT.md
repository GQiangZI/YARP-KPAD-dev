# Skyward 3.0.306 PLATFORM module audit / 驱动版本核查

> **Confirmed version conflict, not a runtime diagnosis.** No new YARP image has been built or boot-tested.
>
> **已确认整套驱动存在版本差异，但尚未证明这是之前的启动崩溃原因。请勿将当前仓库版本当作稳定可刷镜像。**

## Sources / 核查来源

- Known-booting Skyward fast image SHA-256: `5946756010e8be6b0dd149868cad60770a7c62080d6e0b55d8d9d3a2b8f59855`
- Known-booting Skyward slow image SHA-256: `9eb4b9a7c8a0173aa3e396406dd6af1e01fef9f6bb10ce734db38fec60863d2a`
- Both images share PLATFORM ramdisk SHA-256: `2330b412e7d93d81d0f336b5e2141e983a49d2e5483bdd526eebc2d34132c081`
- Public development tree: [YARP-KPAD-dev](https://github.com/GQiangZI/YARP-KPAD-dev), imported from original tree commit `1bb97be36ea89362664a87dfb7a77acca4e3eb9b`.

## Verified results / 已证实结果

| Check | Result |
|---|---|
| Extracted PLATFORM entries | 676 total (414 regular files, 224 symlinks, 38 directories) |
| Kernel modules `*.ko` | **274** in Skyward, **274** in current repository |
| Matching module filenames | **274 / 274** |
| Matching module binary blobs | **0 / 274** |
| Different module binary blobs | **274 / 274** |
| Module dependency metadata | `modules.alias`, `modules.dep`, `modules.load`, `modules.load.recovery`, `modules.softdep` are byte-identical |
| Fast vs slow PLATFORM | Byte-identical |

Comparison method: for each `lib/modules/<name>.ko` extracted from the known-working legacy LZ4 CPIO, compute a Git blob SHA-1 and compare the corresponding `recovery/root/lib/modules/<name>.ko` GitHub blob. All 274 files have different *first eight hex digits* of the blob hash; therefore **every full blob SHA-1 differs**, without relying on an assumed kernel version. Checked name ordering against individual known samples.

### Representative exact SHA-1 mismatches / 抽样完整哈希

| Module | Skyward known-good blob | Current repository blob |
|---|---|---|
| `mitee.ko` | `4699679146a282c5a812209b4928abb4f3155aae` | `f959aedaf045586eb0099f4466633db8ce773a51` |
| `mediatek-drm.ko` | `bf27a6889ad90beb5cd2b6d711ad86c5fcebfdbb` | `ded499da061911c9a2b9ea563c01ffdcf75b6543` |
| `mtu3.ko` | `e13fb66b6d9a16aff65949717ba0b36473397856` | `f004a8804f7da4e2e25ef459a46c49e0afd74c54` |
| `mtk-mmc.ko` | `626c012528b3f21a46f7b87a201f6fcfdfeb426c` | `b3fa0536ec9b2df60fc3fd90f36f625c36342502` |
| `mt6379-chg.ko` | `1c924334d31b1a7fda7a916ee17b2032f0445d52` | `a4f48693b5d85e58c522a30b847c15839e8b35dc` |
| `panel-nt37801-cmd-fhd.ko` | `aa098cb2eeec4c2d27c636a72552dc59ee6ba209` | `4f8e0e1c067672333e4e690f76a4988a2b5c419c` |

ELF `.modinfo` in Skyward `mitee.ko`, `mtu3.ko`, `mediatek-drm.ko`, and sampled panel driver reports:
`6.6.77-android15-8-g00f161d7c6ac-4k SMP preempt mod_unload modversions aarch64`.
That is the **reference module's own vermagic**, not proof of the installed K Pad's running kernel version or of YARP compatibility.

## Safe integration route / 安全整合方法

A new [read-only-by-default module sync tool](../tools/sync_skyward_modules.py) can inspect the exact supplied Skyward image and compare every module with the local device tree:

```bash
python3 tools/sync_skyward_modules.py /path/to/skyward-turner-306-fast.img --tree . --report skyward-module-diff.json

# Only inside a disposable / throwaway local git checkout, deliberately:
python3 tools/sync_skyward_modules.py /path/to/skyward-turner-306-fast.img --tree . --apply
git diff --stat
```

The tool accepts **only two pinned, previously verified image SHA-256 hashes**. It verifies PLATFORM ramdisk hash, parses legacy LZ4 and CPIO, requires exactly 274 matching filenames, and rejects unequal `modules.*` metadata. It never makes a flashable image; `--apply` alters local driver files only.

**Remote integration update (2026-11-14):** The extracted 274-module + five-metadata ZIP was verified locally (SHA-256 `28ca760a4b6cc867c04493b6b29e0104b1ee1fd820a264b6c3169c336d811fad`, 15.60 MiB). The [whole-set ZIP importer](../tools/apply_verified_skyward_zip.py) and [one-shot automatic source-only workflow](../.github/workflows/integrate-skyward-modules.yml) are committed and covered by five passing CI tests. The GitHub connector still cannot directly upload local binary attachments. Thus **the actual remote `.ko` files have not been replaced** until that verified ZIP is uploaded once at `references/skyward/Skyward_turner_OS3.0.306_modules_reference.zip`. See [integration instructions / 整合说明](../docs/SKYWARD_DRIVER_INTEGRATION.md). The workflow will verify hashes and commit all 274 files as a unit; no image build or release is triggered.

## Recommended order / 下一步

1. Stage **all 274** Skyward modules together, not selected `.ko` files from mixed firmware builds.
2. Compare exact kernel vermagic, `modules.dep`, and the working firmware's `boot`/vendor partitions with the target device before use.
3. Keep Skyward PLATFORM ramdisk, DTB, module ordering and first-stage semantics intact in a candidate test image.
4. Compile YARP/GUI2 independently, then inspect ELF dependency closure, Vendor Boot v4 structure, and image size.
5. Do not release or recommend flashing until actual boot, rollback, touch, USB, encryption and normal system operation are tested.

**Status: VERSION MISMATCH CONFIRMED — TEST IMAGE NOT APPROVED / 版本差异已确认，尚无通过验证的可刷镜像。**
