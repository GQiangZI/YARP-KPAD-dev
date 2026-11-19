# YARP Recovery — Redmi K Pad (turner)

[简体中文](README.md) | [**English**](README.en.md)

> **✅ Project status: v1.0 released (2026-11-19)**
>
> This project is complete: display, touch, **data decryption (pattern / PIN / password)**, OTG, MTP, ADB, haptics, backup & restore are all verified on-device, and the system boots normally after a decrypt session.
>
> 👉 **Get the prebuilt image from the official repo**: [GQiangZI/twrp_device_xiaomi_turner — Releases](https://github.com/GQiangZI/twrp_device_xiaomi_turner/releases), image `YARP-turner-K_PAD-vendor_boot-46428cf2.img`, SHA256 `e9ede605818609f9cbb7725feef7bbfc0490b15200f2d88d85ee87051af3714a`.
>
> **This repo is the development-materials archive**: build scripts, assembly materials, per-version records and the crypto-stack audit live here. **Do not flash any intermediate artifact from this repo** — none of them is the release image.

## Project goal

Bring the upstream **YARP native GUI2/LVGL interface and core recovery features** to the Redmi K Pad, following the Skyward turner image that already runs on this device, and port the MediaTek boot, driver, touch, decryption and USB stack.

- **Keep the native YARP interface**: menus, interaction, layout, file manager, install, backup & restore, mounts, terminal and settings stay as upstream.

## Device

| Item | Detail |
| --- | --- |
| Device | Redmi K Pad |
| Codename | `turner` |
| Platform | MediaTek MT6991 (Dimensity 9400+, ro.hardware = mt8799) |
| Base system | HyperOS OS4.0.3.0 stable (verification baseline) |
| Display | 1880 × 3008 (current device-tree config) |
| Recovery upstream | [TWRP-Test / twrp-16.0](https://github.com/TWRP-Test) |
| Output target | **`vendor_boot.img`** (not a standalone `recovery.img`) |
| Boot structure | Vendor Boot v4, dual ramdisk, LZ4 legacy |

> The Xiaomi Pad 8 Pro (`piano`) YARP landscape config is only a UI reference for turner.

## Development progress (v1.0 final state)

| Item | Status |
| --- | --- |
| YARP GUI2 / display & touch | ✅ Verified in v1.0: full GUI2 display, responsive touch (Novatek NT36536E + Xiaomi touchfeature HAL) |
| Data decryption | ✅ Verified in v1.0: metadata + FBE (DE/CE) fully working, pattern / PIN / password; credentials verified by the system's mitee Gatekeeper, KeyMint issues the authorization token — the same TEE chain as stock |
| ADB, MTP, backup & restore | ✅ Verified: ADB / MTP / sideload / USB OTG storage, backup & restore, partition management, Install Image can flash Vendor Boot / DTBO |
| Haptics | ✅ Verified: AIDL vibratorfeature HAL + AW8693x actuator driver |
| Boot-chain guard | ✅ Verified: flashable zips cannot write lk / preloader, protecting the bootloader unlock |
| Wi-Fi | ⏳ Not implemented (does not affect core recovery work) |
| GitHub Actions builds | ✅ Device-tree build workflows configured (`.github/workflows/`); tree-built images black-screen on this device, so the release image is assembled with the "hybrid" method, whose materials and scripts are in this repo |

Per-version history is in the official repo's [`CHANGELOG.md`](https://github.com/GQiangZI/twrp_device_xiaomi_turner/blob/main/CHANGELOG.md); the crypto-stack audit is in this repo at `hybrid/decrypt-stack/FINDINGS.md`.

## How it works (brief)

Directly compiled images all black-screened on this device, so the release uses a **hybrid** build: stock HyperOS OS4 `vendor_boot` as the base (F0 and DTB stay stock; the DTB is byte-identical), the YARP userspace in F1 with strict library isolation, and the crypto and touch HALs started at runtime from the **installed system**. See the official repo README for the full story.

## Important safety notes

- **This repo ships no flashable release image.** Releases live only in the official repo; verify the SHA256 before flashing.
- turner has no separate recovery partition — recovery lives in **vendor_boot**, so **`fastboot boot` cannot be used**; flash it: `fastboot flash vendor_boot YARP-turner-K_PAD-vendor_boot-46428cf2.img`, then `fastboot reboot recovery`.
- Keep a stock `vendor_boot.img` handy; flash it back the same way to revert. Do not flash lk / preloader from a full stock package (it can re-lock the bootloader).
- Before any first device test, prepare a verifiable stock image and a recovery plan, and record the device and firmware version; unverified artifacts are test material only.
- Safety & pre-flash checks: see `SAFETY.md` / `SAFETY.zh-CN.md`.

## References & credits

- [TWRP-Test: YARP / TWRP 16.0 & GUI2](https://github.com/TWRP-Test)
- Original Redmi K Pad device tree
- [Skyward Recovery](https://github.com/kirklin/skyward) · skyward-extra
- Xiaomi Pad 8 Pro Recovery device tree
- Credits (official repo README): cogan17 / JonesqPacMan (rothko device tree), lingqiqi, YuKongA, kirklin, 酷安 小智乃敲可爱 (Skyward turner port), kodeaqua (taiko TWRP, the first public mitee decryption precedent), TeamWin Recovery Project

Keep each upstream project's license and copyright notices. **This repo is for development and verification only; the original device-tree repo is not modified here.**
