# YARP Recovery — Redmi K Pad（turner）

[**简体中文**](README.md) | [English](README.en.md)

> **✅ 项目状态：v1.0 已发布（2026-11-19）**
>
> 本项目已完成：显示、触控、**数据解密（图案 / PIN / 密码）**、OTG、MTP、ADB、振动、备份恢复全部实机打通，解密后退出可正常进系统。
>
> 👉 **成品镜像请去正式仓库下载**：[GQiangZI/twrp_device_xiaomi_turner — Releases](https://github.com/GQiangZI/twrp_device_xiaomi_turner/releases)，镜像 `YARP-turner-K_PAD-vendor_boot-46428cf2.img`，SHA256 `e9ede605818609f9cbb7725feef7bbfc0490b15200f2d88d85ee87051af3714a`。
>
> **本仓库是开发材料库**：拼接脚本、构建材料、逐版记录与解密栈审计都在这里；**不要直接刷本仓库里的任何中间产物**，它们不是发布镜像。

## 项目目标

让 Redmi K Pad 使用上游 **YARP 原生 GUI2/LVGL 界面及核心 Recovery 功能**，并优先参考已能在本机运行的 Skyward turner 镜像，适配联发科平台的启动、驱动、触控、解密与 USB 服务。

- **保留 YARP 原生界面**：菜单、交互、布局策略、文件管理、安装、备份恢复、挂载、终端、设置等保持与上游一致

## 设备信息

| 项目 | 当前适配目标 |
| --- | --- |
| 设备 | Redmi K Pad |
| 代号 | `turner` |
| 平台 | MediaTek MT6991（天玑 9400+，ro.hardware = mt8799） |
| 基础系统 | HyperOS OS4.0.3.0 正式版（验证基线） |
| 屏幕配置 | 1880 × 3008（当前设备树配置） |
| Recovery 上游 | [TWRP-Test / twrp-16.0](https://github.com/TWRP-Test) |
| 输出目标 | **`vendor_boot.img`**（不是独立 `recovery.img`） |
| 启动结构 | Vendor Boot v4、双 ramdisk、LZ4 legacy |

> 小米平板 8 Pro（`piano`）的 YARP 横屏配置仅作 UI 参考 turner。

## 开发进度（v1.0 终态）

| 项目 | 状态 |
| --- | --- |
| YARP GUI2 / 平板显示与触控 | ✅ v1.0 已验证：GUI2 完整显示，触控流畅（Novatek NT36536E + 小米 touchfeature HAL） |
| Data 解密 | ✅ v1.0 已验证：metadata + FBE（DE/CE）全链路打通，图案 / PIN / 密码均可；凭据经系统 mitee Gatekeeper 验证、KeyMint 下发授权令牌，与原厂同一条 TEE 链 |
| ADB、MTP、备份恢复 | ✅ 已验证：ADB / MTP / sideload / OTG U 盘、备份恢复、分区管理、Install Image 可刷 Vendor Boot / DTBO |
| 振动 | ✅ 已验证：AIDL vibratorfeature HAL + AW8693x 执行器驱动 |
| 启动链防护 | ✅ 已验证：卡刷包禁止写 lk / preloader，保护 BL 解锁 |
| Wi-Fi | ⏳ 未做（不影响 Recovery 核心功能） |
| GitHub Actions 构建 | ✅ 设备树编译工作流已配置（`.github/workflows/`）；直出镜像在本机黑屏，发布镜像按「混合拼接」路线组装，材料与脚本在本仓库 |

版本变更明细见正式仓库的 [`CHANGELOG.md`](https://github.com/GQiangZI/twrp_device_xiaomi_turner/blob/main/CHANGELOG.md)；解密栈审计见本仓库 `hybrid/decrypt-stack/FINDINGS.md`。

## 实现方式（简述）

直出编译的镜像在本机全部黑屏，最终采用**混合拼接**路线：以 HyperOS OS4 原厂 `vendor_boot` 为底（F0 与 DTB 保持原厂，DTB 逐字节一致），F1 放入 YARP 用户态并做严格库隔离，解密与触控的 HAL 在运行时从**已安装系统**拉起。完整说明见正式仓库 README。

## 重要安全说明

- **本仓库不提供可刷的成品镜像**。成品只在正式仓库的 Releases 发布，刷机前请核对 SHA256。
- turner 没有独立 recovery 分区，Recovery 在 **vendor_boot** 里，**不能用 `fastboot boot` 测试**，只能刷入：`fastboot flash vendor_boot YARP-turner-K_PAD-vendor_boot-46428cf2.img`，然后 `fastboot reboot recovery`。
- 刷前请先备一份原厂 `vendor_boot.img`，需要恢复时刷回即可；不要刷入原厂完整包里的 lk / preloader（可能导致重新上锁）。
- 首次实机测试前应准备可核验的原厂镜像与恢复方案，并记录设备及固件版本；未经明确验证的产物只允许作为开发测试材料。
- 安全与刷机前检查（中文）· English：见 `SAFETY.md` / `SAFETY.zh-CN.md`。

## 参考与致谢

- [TWRP-Test：YARP / TWRP 16.0 与 GUI2](https://github.com/TWRP-Test)
- 原 Redmi K Pad 设备树
  -skyward-extra 参考项目的思路
- Xiaomi Pad 8 Pro Recovery 设备树
- 致谢（正式仓库 README）：cogan17 / JonesqPacMan（rothko 设备树）、lingqiqi、YuKongA、kirklin、kodeaqua（taiko TWRP，首个公开的 mitee 解密先例）、TeamWin Recovery Project

保留各上游项目适用的许可证与版权信息。**本仓库仅用于开发与验证，原设备树仓库不在此处修改。**
