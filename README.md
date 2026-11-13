# YARP Recovery — Redmi K Pad（turner）

[**简体中文**](README.md) | [English](README.en.md)

> **项目状态：开发中 · 尚未完成编译及实机验证 · 请勿刷写**
>
> 本仓库是 Redmi K Pad（MT6991）的 **YARP / TWRP 16.0 GUI2** Recovery 适配项目。目前内容尚不完整；任何源码、脚本或后续测试产物均**不代表可安全刷机**。

## 项目目标

让 Redmi K Pad 使用上游 **YARP 原生 GUI2/LVGL 界面及核心 Recovery 功能**，并优先参考已能在本机运行的 Skyward turner 镜像，适配联发科平台的启动、驱动、触控、解密与 USB 服务。

- **保留 YARP 原生界面**：菜单、交互、布局策略、文件管理、安装、备份恢复、挂载、终端、设置等保持与上游一致，不使用 Skyward 界面替代。
- **优先保证基础功能**：启动、显示、触控、ADB/MTP、数据解密、备份恢复、Fastbootd 等。
- **Wi-Fi 是可选功能**：上游已有 Wi-Fi 界面及后端；但 turner 的驱动与服务尚未验证。第一阶段不启用，不影响其他功能推进。
- **安全优先**：编译通过、静态检查通过或 Skyward 成功启动，都不等于本项目生成的 YARP 镜像已经通过实机验证。

## 设备信息

| 项目 | 当前适配目标 |
| --- | --- |
| 设备 | Redmi K Pad |
| 代号 | `turner` |
| 平台 | MediaTek MT6991 |
| 基础系统 | Android 16 / HyperOS（具体固件版本须实机核验） |
| 屏幕配置 | 1880 × 3008（当前设备树配置） |
| Recovery 上游 | [TWRP-Test / twrp-16.0](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0) |
| 输出目标 | **`vendor_boot.img`**（不是独立 `recovery.img`） |
| 启动结构 | Vendor Boot v4、双 ramdisk、LZ4 legacy |

> 小米平板 8 Pro（`piano`）的 YARP 横屏配置仅作 UI 参考；它的高通驱动、触控旋转参数和 `recovery.img` 分区方式**不能直接照搬**到 turner。

## 开发进度

| 项目 | 当前状态 |
| --- | --- |
| 核心设备树配置 | 部分已迁移 |
| MT6991 初始化配置、fstab 与 vold 补丁 | 已迁移部分文件，仍需依赖审查 |
| Skyward 快/慢启动镜像 | 已建立结构与 init 差异分析文档；文件依赖尚未全部核对 |
| 预编译驱动、固件与 HAL | **尚未完整迁移** |
| YARP GUI2 / 平板显示与触控 | 待编译、待实机验证 |
| Data 解密、ADB、MTP、备份恢复 | 待实机验证 |
| Wi-Fi | 可选，暂缓 |
| 完整构建、产物检查与刷机测试 | **尚未完成** |

## 重要安全说明

**当前仓库尚不是完整可编译、可刷写的设备树。** 尤其需要确保 Vendor Boot v4 的 header、DTB、PLATFORM/RECOVERY ramdisk、原厂模块、fstab、init 与 HAL 依赖正确，且镜像不超过 64 MiB 分区容量。不能只凭“构建成功”发布给其他用户刷机。

首次实机测试前应准备可核验的原厂镜像与恢复方案，并记录设备及固件版本；未经明确验证的产物只允许作为开发测试材料，不可标记为稳定版。

- [安全与刷机前检查（中文）](SAFETY.zh-CN.md) · [English](SAFETY.md)
- [YARP GUI2 功能与 Wi-Fi 验收要求（中文）](docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md) · [English](docs/YARP_GUI2_FEATURE_PARITY.md)
- [Skyward Vendor Boot 结构分析](analysis/SKYWARD_VENDOR_BOOT_COMPARISON.md)
- [Skyward 初始化对照](analysis/SKYWARD_INIT_AUDIT.md)
- [只读 Vendor Boot 结构检查脚本](tools/verify_vendor_boot.py)

## 参考与致谢

- [TWRP-Test：YARP / TWRP 16.0 与 GUI2](https://github.com/TWRP-Test/android_bootable_recovery)
- [原 Redmi K Pad 设备树](https://github.com/GQiangZI/twrp_device_xiaomi_turner)
- [Skyward Recovery](https://github.com/kirklin/skyward) · [skyward-extra](https://github.com/echoskies-works/skyward-extra)
- [Xiaomi Pad 8 Pro Recovery 设备树](https://github.com/xiaomi-pad-8-pro-development/android_device_xiaomi_piano-recovery)

保留各上游项目适用的许可证与版权信息。**本仓库仅用于开发与验证，原设备树仓库不在此处修改。**
