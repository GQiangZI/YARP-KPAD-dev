# 在 v3.36 中补齐 vold_prepare_subdirs

实机跟踪重复出现同一个顺序。内核接受 `FS_IOC_ADD_ENCRYPTION_KEY`，
`/data/user/0` 的绑定挂载成功，四个 DE 目录的 `FS_IOC_SET_ENCRYPTION_POLICY`
均返回 0，随后子进程以状态 1 退出。旧版 `FS_IOC_GET_ENCRYPTION_POLICY`
返回 `EINVAL` 后，后续设置调用仍成功。

YARP 的 `fscrypt_prepare_user_storage` 在目录与策略处理后调用
`/system/bin/vold_prepare_subdirs prepare`。v3.36 的 Recovery ELF 包含这个
路径和错误字符串，两个 ramdisk 均缺少该文件。
[YARP vold 源码](https://github.com/TWRP-Test/android_system_vold/blob/twrp-16.0/FsCrypt.cpp)

原厂程序无参数启动的实机测试以 `SIGSEGV` 结束，退出码 139，发生在安装临时入口前。
后续的 ARM64 原生程序以 v3.36 的 Bionic、`libcutils` 和 `libselinux` 构建，
执行上游的 DE/CE `prepare` 路径并检查目录权限、UID/GID 和 SELinux 标签。
无法修复 checkin 目录的元数据时返回失败并保留其内容。重启 Recovery 后临时入口会消失。

构建时使用 ziglang 0.17.1、lz4 和 pyelftools。脚本从已验证的 v3.36 镜像提取
链接库，校验 ELF 解释器、依赖和导入符号。

```sh
python3 hybrid/stage52/build_native.py --base turner-vendor_boot-hybrid-v3.36-CRYPTO-LEGACY-TEST.img \
  --output turner-vold-prepare-native.sh
```

推送 `turner-vold-prepare-native.sh` 到 `/tmp` 后，用平板的 root Recovery 终端运行。看到
`Helper ready` 后点一次「解密」，再用手机 Termux 执行
`adb shell cat /tmp/turner-vold-prepare.log`。预期用户 0 的 DE 准备记录为
`prepare user=0 flags=1 exit=0`，随后再确认图案验证和内部存储访问。
