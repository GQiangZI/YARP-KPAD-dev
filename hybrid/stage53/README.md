# v3.37 Keystore 数据库同步测试

v3.36 实机通过 `vold_prepare_subdirs prepare "" 0 1`，读取出图案类型。
提交图案后，YARP 在 `syncKeystoreDb()` 等待 init 停止 `keystore2` 时失败。
v3.36 的 init 实际管理名为 `vendor.keystore2-sup` 的脚本，该脚本另起进程运行
原厂 keystore2。[YARP 解密源码](https://github.com/TWRP-Test/android_system_vold/blob/twrp-16.0/Decrypt.cpp)

v3.37 由 init 以 `keystore2` 服务名直接管理原厂进程。启动脚本通过 `exec`
交出进程，沿用 v3.36 的库路径、预加载库和补充组。YARP 按原来的顺序
停止服务、通过 SQLite backup API 从已挂载的 `/data` 备份到 `/tmp`、重启服务并
等待 Binder 注册。镜像包含 v3.36 实机通过 DE 的原生目录准备程序。

先用 stage52 的 `build_native.py --elf` 生成对应的目录准备程序，然后构建镜像。

```sh
python3 hybrid/stage53/build_sync.py --base turner-vendor_boot-hybrid-v3.36-CRYPTO-LEGACY-TEST.img \
  --prepare vold_prepare_subdirs --output turner-vendor_boot-hybrid-v3.37-KEYSTORE-SYNC-TEST.img
```

构建器验证 v3.36 镜像、实机测试版目录准备程序的 SHA256，以及 vendor_boot
结构、DTB 和 AVB 哈希。第一 ramdisk 原样复用，第二 ramdisk 仅改动报告列出的条目。
待实机确认服务重启后，使用原图案验证 CE 和内部存储。
