# 贡献与实机联测

问题报告请带上镜像版本、HyperOS 完整版本、设备代号、当前槽位和复现步骤。
刷入问题请附目标分区和操作入口。备份问题请写明所选分区、输出位置，
以及 `createTarFork()` 退出前的首条错误。发送日志前请遮掉设备序列号、
个人文件名、账号和凭据。

卡住时优先保留 Recovery 会话，按 [故障采集说明](hybrid/stage56/RELEASE.md#实机故障采集)
从手机 Termux 获取日志。USB 问题请注明 MTP 开关、使用的 USB 端口、
数据线与 ADB 主机。保留该槽位可启动的 turner `vendor_boot` 用于回退。

提交代码时，说明改动涉及的 ramdisk 文件及验证方式。保留镜像 SHA256
和设备测试记录，并区分模拟验证与实机结果。

```sh
python3 tests/stage48/test_crypto_bridge.py
python3 tests/stage50/test_legacy_lookup.py
git diff --check
```

首个候选版的重打包入口和验收范围见 [v3.40-rc2 发布说明](hybrid/stage57/RELEASE.md)。
