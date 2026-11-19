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

## 公开发布前的验收

RC2 的守卫在 Recovery 启动时重定向部分 `by-name` 入口。它没有在安装前拒绝刷机包的机制，
也没有验证所有写入路径，因此目前无法确认对 LK 和 preloader 的写入一定会被拦截。

- 刷包保护：在实际写入前拒绝以受保护分区为目标的安装包。安装器若无法可靠判断写入目标，
  应拒绝该安装流程。验收覆盖本地 ZIP、ADB sideload、脚本安装、A/B payload 及槽位别名。
  先用模拟分区和测试包检查拒绝结果与零写入，再做实机验证。
- 镜像与日志：正式镜像不打包采集结果、测试日志、调试转储或临时诊断脚本，也不自动把
  Recovery 日志留在设备存储。RC2 两段 ramdisk 未见历史日志文件或日志包，但仍包含
  `turner-crypto-status.sh`，Recovery 二进制也包含运行时日志路径。发布前需验证常规启动、
  重启及安装失败时的日志存放位置，并验证精简后 Data 解密、ADB 与 MTP 仍正常。

## 发布记录

使用标签 `v3.40-rc2` 和 GitHub **Pre-release**。上传镜像、SHA256 文件，
随发布说明记录通过验收的固件和槽位。公开分发前核对 [组件来源与分发范围](../../THIRD_PARTY_NOTICES.md)。
