# Redmi K Pad（turner）YARP GUI2 功能与 Wi-Fi 验收标准

[**简体中文**](YARP_GUI2_FEATURE_PARITY.zh-CN.md) | [English](YARP_GUI2_FEATURE_PARITY.md)

> **状态：适配规范，不代表已经实现或通过实机验证。**

## 项目必须保持的界面和功能

以 [TWRP-Test 的 `twrp-16.0` 分支](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0) 为基础，保留 **YARP 原生 GUI2 / LVGL** 界面与 Recovery 功能，不使用 Skyward 的 `system/bin/recovery` 替换 YARP，也不回退到传统 TWRP 旧 UI。

菜单导航、状态栏、底部操作栏、确认流程、字体和缩放逻辑、语言、主题、文件管理、安装/刷机、备份恢复、挂载、终端和设置应与上游一致；只对设备相关的初始化、显示、触控、存储和 HAL 进行必要适配。

小米平板 8 Pro（`piano`）的 YARP 设备树可用作横屏大屏参考，但不能直接照搬它的高通驱动、触控旋转参数或独立 `recovery.img` 构建方式。turner 目标是 `vendor_boot.img`，设备树标注屏幕为 1880×3008。

## 实机验收清单

| 项目 | 验收要求 | 当前状态 |
| --- | --- | --- |
| 启动与回退 | Vendor Boot v4，双 LZ4 ramdisk，DTB、分区大小和正常系统启动均匹配 | Skyward 镜像已可用；YARP 未验证 |
| GUI2 显示与触控 | 方向、缩放、文字、滚动、触摸命中、按钮、截图正常 | Skyward 显示与触控已通过用户实测；YARP 待验证 |
| Data 解密 | PIN/图案/密码解锁和挂载，无意外破坏数据 | Skyward 用户实测失败；YARP 待验证 |
| 安装与 Sideload | ZIP 安装、ADB Sideload、故障处理 | 待验证 |
| 备份与恢复 | A/B、动态分区、备份列表、还原及完整性 | 待验证 |
| 擦除与格式化 | 正确识别分区，操作可确认，避免误擦 | 待验证 |
| USB | ADB、MTP、传输和重新连接 | 待验证 |
| Fastbootd / 重启 | 正确进入 fastbootd、系统、Recovery、Bootloader | 待验证 |
| 其他功能 | 文件管理、终端、挂载、日志、语言、时区、亮度、电量 | 待验证 |
| **Wi-Fi（可选）** | 打开、扫描、连接、DHCP、网络状态稳定 | **暂缓；不阻塞第一版** |

## Wi-Fi 技术现状

YARP 上游已具有：
- `gui2/pages/wifi_page.cpp`：Wi-Fi 页面。
- `gui2/backend/twrp_wifi_backend.cpp`：连接、扫描、状态等后端。
- `TW_INCLUDE_WIFI`：构建时启用/关闭开关，未启用时可隐藏入口。

其现有后端使用 `wlan0`、`wpa_supplicant`、`wpa_cli` 和 `/tmp/recovery/sockets`。这些接口、服务、模块、固件、依赖和 DHCP 配置**尚未在 Redmi K Pad 的 Recovery 环境验证**。

**第一阶段保持 Wi-Fi 关闭，不在 `BoardConfig.mk` 启用 `TW_INCLUDE_WIFI := true`。** 先完成启动、触控、解密、ADB/MTP，再核对联发科 Wi-Fi 运行环境。只有实际扫描、连接、获取 IP、重连和网络测试全部稳定时才启用。若不能实现，则继续暂缓，不牺牲其他功能。

## 发布要求

源码能编译、静态审计通过以及 Skyward 的正常启动，均不代表 YARP 镜像能安全启动。必须保存实机测试日志和准确固件版本，满足安全规范后才考虑公开发布。

[返回中文首页](../README.md) · [刷机与发布安全规范](../SAFETY.zh-CN.md)
