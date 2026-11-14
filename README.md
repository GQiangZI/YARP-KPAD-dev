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
| 原始设备树、libinit、BootControl | **已完整迁入原仓库基线（锁定提交 `1bb97be`）** |
| MT6991 初始化配置、fstab 与 vold 补丁 | **文件已迁移，实机依赖仍需验证** |
| Skyward 快/慢启动镜像 | 已建立结构与 init 差异分析文档；文件依赖尚未全部核对 |
| 基线 DTB、内核模块、固件与 HAL | **已完成 274 个 Skyward 驱动提取与校验，整套入库工作流就绪；等待参考 ZIP 上传以完成远端替换** |
| YARP GUI2 / 平板显示与触控 | 待编译、待实机验证 |
| Data 解密、ADB、MTP、备份恢复 | 待实机验证 |
| Wi-Fi | 可选，暂缓 |
| 静态检查 | **文件完整性与同步工具测试通过**；驱动版本一致性检查明确提示不匹配 |
| GitHub Actions 构建 | **已配置手动工作流**；尚未执行完整 Android/YARP 构建 |
| 实机启动、解密和刷机测试 | **尚未完成，禁止宣称可刷** |

## 重要安全说明

**当前仓库已经迁入原设备树的主要源码和二进制，但尚未完成 YARP 整体编译与实机启动验证，不能认定可刷写。** 尤其需要确保 Vendor Boot v4 的 header、DTB、PLATFORM/RECOVERY ramdisk、原厂模块、fstab、init 与 HAL 依赖正确，且镜像不超过 64 MiB 分区容量。不能只凭“构建成功”发布给其他用户刷机。

首次实机测试前应准备可核验的原厂镜像与恢复方案，并记录设备及固件版本；未经明确验证的产物只允许作为开发测试材料，不可标记为稳定版。

- [安全与刷机前检查（中文）](SAFETY.zh-CN.md) · [English](SAFETY.md)
- [YARP GUI2 功能与 Wi-Fi 验收要求（中文）](docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md) · [English](docs/YARP_GUI2_FEATURE_PARITY.md)
- [Skyward Vendor Boot 结构分析](analysis/SKYWARD_VENDOR_BOOT_COMPARISON.md)
- [Skyward 初始化对照](analysis/SKYWARD_INIT_AUDIT.md)
- [只读 Vendor Boot 结构检查脚本](tools/verify_vendor_boot.py)
- [已验证镜像分段提取工具](tools/extract_vendor_boot_reference.py)
- [Skyward RECOVERY 文件清单与差异](analysis/SKYWARD_PAYLOAD_INVENTORY.md)
- [USB 控制器与 MTP 初始化差异](analysis/USB_CONTROLLER_MTP_AUDIT.md)
- [KeyMint 解密版本与 AVB 安全风险](analysis/CRYPTO_PATCH_LEVEL_AVB_RISKS.md)
- [274 个 Skyward 驱动版本差异（重要）](analysis/SKYWARD_PLATFORM_MODULE_AUDIT.md)
- [驱动整体同步工具（默认只读）](tools/sync_skyward_modules.py) · [驱动版本校验](tools/check_skyward_module_set.py)
- [Skyward 完整驱动整合说明（中英双语）](docs/SKYWARD_DRIVER_INTEGRATION.md) · [自动导入工作流](.github/workflows/integrate-skyward-modules.yml)
- [原始设备树完整导入记录](analysis/BASELINE_IMPORT_REPORT.json) · [导入任务](https://github.com/GQiangZI/YARP-KPAD-dev/actions/runs/43518739112)
- [最新静态与驱动同步测试结果](https://github.com/GQiangZI/YARP-KPAD-dev/actions/runs/43528757341)
- [YARP 手动构建配置](.github/workflows/build-twrp.yml)（测试镜像默认不公开导出）

## 参考与致谢

- [TWRP-Test：YARP / TWRP 16.0 与 GUI2](https://github.com/TWRP-Test/android_bootable_recovery)
- [原 Redmi K Pad 设备树](https://github.com/GQiangZI/twrp_device_xiaomi_turner)
- [Skyward Recovery](https://github.com/kirklin/skyward) · [skyward-extra](https://github.com/echoskies-works/skyward-extra)
- [Xiaomi Pad 8 Pro Recovery 设备树](https://github.com/xiaomi-pad-8-pro-development/android_device_xiaomi_piano-recovery)

保留各上游项目适用的许可证与版权信息。**本仓库仅用于开发与验证，原设备树仓库不在此处修改。**
