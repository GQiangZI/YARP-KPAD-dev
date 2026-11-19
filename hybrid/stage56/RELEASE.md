# Redmi K Pad (turner) YARP Recovery v3.40-rc1

适用设备为 Redmi K Pad（turner，MT6991）。镜像类型为 `vendor_boot.img`。
当前状态为候选版，实机证据来自此前的 v3.38 和调试镜像。

发布资产为 `turner-vendor_boot-v3.40-rc1.img`（64 MiB），SHA256 为
`d467e1b3b0a4057b9b3817d964bdec476c0f9564f8fe20e858b6fc304b07e0df`。

## 此版变更

- 镜像刷入菜单的目标为 **Boot、Init Boot、Vendor Boot、DTBO、Super**。
  DTBO 使用 turner 设备树中的 A/B 声明，对应原厂 fstab 的 `dtbo`。
  菜单按 Recovery 识别到的分区生成。
- 沿用图案解锁、内部存储访问和现有 USB 模式。WLAN 维持关闭。
- 基于 v3.39 重打包，只更新 Recovery 的 fstab 和 `twrp.flags`。

刷入目标范围覆盖本版计划支持的 Android 启动和系统镜像。Turner 的
Recovery 位于 `vendor_boot` 中。`misc`、`persist`、modem、vbmeta、
LK、preloader 和加密相关分区不开放新的单镜像刷入入口。

## 实机验收与发布审查

| 功能 | 已有证据 | 待验收 |
| --- | --- | --- |
| 启动、显示、触控 | v3.38 进入 GUI 并正常操作 | RC 同固件连续冷启动和重进 Recovery，记录可操作时间 |
| Data 解密 | v3.38 原图案通过，可浏览内部存储原有文件名 | RC 解锁、打开已有文件，复测重启和错误图案 |
| 镜像刷入 | fastboot 刷入当前槽位的 Recovery 镜像已实测 | RC 核对菜单和当前槽位，再分别验证 GUI 写入及重启。待实机测试前将 DTBO 和 Super 视为待验证入口 |
| 备份与恢复 | Boot 单分区完成，64 MB 有摘要；组合备份在 Cache 打包退出 255 | 取得 Cache 失败点的完整日志，验证 Data 和可恢复性 |
| 容量刷新 | 有正常退出记录，也有偶发卡在刷新页的反馈 | 采集卡住时的 /tmp/recovery.log，并测重复刷新和备份取消后的界面状态 |
| USB | 关闭 MTP 时手机 Termux 能识别 ADB | 验证 MTP 切换、回到 ADB、重新插拔和 USB OTG 热插拔 |
| 刷机包和恢复出厂 | 当前仅有零散测试 | 分别验证兼容 OTA、sideload、清理操作与同槽位回退 |
| 构建和分发 | 固定 v3.39 输入，候选镜像通过本地结构检查 | 对齐完整源码构建与混合镜像，锁定各组件来源和版本，核对随镜像分发的原厂及第三方组件许可 |
| 安全状态 | 基线运行日志存在 SELinux permissive 记录，镜像内 AVB 哈希描述符使用 NONE | 核对 RC 实机安全状态及驱动所需策略，公开构建前明确适用边界 |

公开发布时，优先用 **Pre-release** 标记，并附上 SHA256、已验证的固件版本、槽位和回退镜像。
稳定版验收尤其关注 Cache 备份失败、刷新偶发卡住和 MTP 切换后 ADB 识别问题。

## 实机故障采集

[RC1 采集脚本](../../tools/turner-rc1-diagnostics.sh) 从 ADB 推到 `/tmp` 后运行。
Cache 失败或刷新卡住时采集当前日志，脚本同时记录存储挂载和 USB 状态。

```sh
adb push turner-rc1-diagnostics.sh /tmp/turner-rc1-diagnostics.sh
adb shell sh /tmp/turner-rc1-diagnostics.sh snapshot > turner-rc1-incident.txt
```

检查 MTP 时，先用 ADB 启动采样，再切换 MTP。采样在平板本机持续约 40 秒，
关闭 MTP 并重新连接 ADB 后拉取记录。RC1 的 ramdisk 缺少
`sys.usb.config=mtp,adb` 的 init 触发项，采样确认实际 USB 控制器和端点状态。

```sh
adb shell sh /tmp/turner-rc1-diagnostics.sh watch-usb
adb pull /tmp/turner-rc1-usb.txt
```

## 本地构建

```sh
python3 -m pip install lz4==4.4.5 pyelftools==0.33
python3 hybrid/stage56/build_rc.py \
  --base turner-vendor_boot-hybrid-v3.39-VENDOR-BOOT-TEST.img \
  --output turner-vendor_boot-v3.40-rc1.img
```

构建器核对输入 SHA256、镜像结构、DTB、AVB 哈希和逐条 ramdisk 差异，并输出
`.verification.json`。将镜像作为 GitHub Release 资产上传，保留可回退的实机通过版。

## 来源

- [TWRP-Test / YARP](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0)
- [Redmi K Pad 原设备树](https://github.com/GQiangZI/twrp_device_xiaomi_turner)
- [Skyward Recovery](https://github.com/kirklin/skyward)
