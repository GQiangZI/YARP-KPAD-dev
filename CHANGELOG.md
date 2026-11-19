# 更新日志

## v3.40-rc2

- 使用 turner 的 ConfigFS 控制器配置 MTP 和 ADB 组合模式。
- 补齐首个预发布候选版的构建方法、组件来源和实机验收记录。

## v3.40-rc1

- 添加 turner 的 A/B DTBO 镜像刷入目标。
- 增加备份失败、容量刷新和 USB 切换的故障采集工具。

## v3.39

- 在镜像刷入菜单中显示 Vendor Boot。

## v3.38

- 新增 keystore2 授权服务的旧 Binder 查询兼容。
- 实机通过原锁屏图案解锁，Recovery 可浏览内部存储。

## v3.37

- 将 keystore2 的停启交给 init，允许 YARP 同步内存中的工作数据库。
- 内置实机验证过的 DE 目录准备辅助程序。
