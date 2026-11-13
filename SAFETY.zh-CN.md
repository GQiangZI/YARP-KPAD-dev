# Redmi K Pad（turner）Recovery 开发安全规范

[**简体中文**](SAFETY.zh-CN.md) | [English](SAFETY.md)

> **开发中 · 尚未经过 YARP 实机验证 · 不可作为正式刷机教程或稳定版镜像。**
>
> 当前设备树尚未完整迁移，基于它生成的 YARP 镜像尚未确认能在 Redmi K Pad 安全启动。禁止将未经测试的产物当作稳定版分发。

## 发布可刷写镜像之前必须完成

1. **确认设备与固件**：Redmi K Pad，代号 `turner`，MT6991；记录精确的系统版本与固件版本。
2. **核对 Vendor Boot**：对照原厂和能够启动的 Skyward 镜像，检查 v4 头部、4096 字节页大小、双 ramdisk 表项的数量/类型/名称、LZ4 压缩、DTB、启动参数及 64 MiB 容量限制。
3. **保留必要组件**：核对 PLATFORM ramdisk、驱动、固件、init 服务、HAL 及动态链接依赖。**编译通过不代表能够启动。**
4. **审查系统安全链路**：检查 first-stage fstab、A/B 槽位、动态分区、metadata encryption、FBE、KeyMint、Gatekeeper 与 AVB。
5. **完成实机测试**：启动、显示、触控、ADB、MTP、解密、备份、恢复、重启以及正常进入系统。
6. **具备回退能力**：首次试刷前必须准备已验证的原厂镜像备份和可执行的恢复步骤。
7. **限制发布**：只允许手动触发构建，不自动公开发布稳定版；未经实机验证的产物必须标记为 `UNTESTED-DO-NOT-FLASH`。

## 硬件文件来源

优先以用户提供、已在 K Pad 实机运行的 Skyward turner 快/慢版 `vendor_boot.img` 作为硬件参考。仅在核对身份、完整性、依赖关系和再分发条件后，提交确有必要的驱动、固件及 HAL 文件。

无法确认再分发权限时，使用带哈希校验的可复现提取脚本，而非未经核验就直接上传至公开仓库。

**不得在没有差异分析的情况下混用快、慢两个镜像的不同 Recovery 组件。** Skyward 已能正常启动，并不等于移植后的 YARP 也已验证安全。

## 当前状态

设备树只迁移了部分文本配置，完整的预编译文件、启动资源和构建脚本尚待补齐；YARP 尚未通过编译、启动和功能验证。**目前没有获准公开刷写的镜像。**

[返回中文首页](README.md) · [YARP 功能验收要求](docs/YARP_GUI2_FEATURE_PARITY.zh-CN.md)
