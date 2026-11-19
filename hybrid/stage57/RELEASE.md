# Redmi K Pad YARP Recovery v3.40-rc2

首个预发布候选版，适用于 Redmi K Pad（turner，MT6991）。

- 发布资产：`turner-vendor_boot-v3.40-rc2.img`，64 MiB。
- SHA256：`e9ede605818609f9cbb7725feef7bbfc0490b15200f2d88d85ee87051af3714a`。
- 目标分区：`vendor_boot`。通过设备代号和当前槽位选择设备。

## 变更

- 支持 Boot、Init Boot、Vendor Boot、DTBO 和 Super 刷入目标配置。
- 在 turner 的 ConfigFS 初始化中配置 MTP FunctionFS，等待 MTP 和 ADB
  端点就绪后绑定同一控制器，切回其他模式时清理组合配置。
- WLAN 关闭。

## 实机状态

| 功能 | 实测记录 |
| --- | --- |
| Data 解密 | 2026-11-19 用户确认 RC2 实机解密正常 |
| Boot 单分区备份 | v3.38 已生成校验摘要，恢复待验证 |
| Vendor Boot、DTBO 菜单 | 配置已通过镜像校验，显示和 GUI 写入待实机验收 |
| ADB 和 MTP | 2026-11-19 用户确认 RC2 实机 ADB 和 MTP 均正常 |
| Cache 和 Data | Cache 组合备份曾返回 255，Data 文件型备份与还原待验收 |
| 容量刷新 | 曾偶发卡住，需要抓取发生时的记录 |

冷启动耗时、ADB 与 MTP 并行及反复切换的表现，留待记录专项测试结果。
故障采集和回退准备见 [RC1 指南](../stage56/RELEASE.md) 与 [贡献指南](../../CONTRIBUTING.md)。

## 重现构建

```sh
python3 -m pip install lz4==4.4.5 pyelftools==0.33
python3 hybrid/stage57/build_rc2.py \
  --base turner-vendor_boot-v3.40-rc1.img \
  --output turner-vendor_boot-v3.40-rc2.img
python3 tools/verify_vendor_boot.py turner-vendor_boot-v3.40-rc2.img
sha256sum turner-vendor_boot-v3.40-rc2.img
```

构建器核对输入哈希、AVB 哈希、DTB、vendor_boot 结构及逐条归档差异。
RC2 只改第一 ramdisk 中的 init 配置，第二 ramdisk 逐字节保持。
嵌入式 AVB 只包含哈希描述符，认证算法仍为 NONE。

## 发布记录

使用标签 `v3.40-rc2` 和 GitHub **Pre-release**。上传镜像、SHA256 文件，
随发布说明记录通过验收的固件和槽位。公开分发前核对 [组件来源与分发范围](../../THIRD_PARTY_NOTICES.md)。
