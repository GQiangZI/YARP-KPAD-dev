# turner FBE 目录初始化诊断

v3.36 已经取得 keystore2 并挂载 `/data`。上游 `load_all_de_keys()` 安装用户 0 的
DE 密钥后写入 `twrp.user.0.decrypt=0`，`prepare_special_dirs()` 创建 `/data/user/0`
绑定挂载。实机观察到这两项，随后 `fscrypt_init_user0` 仍失败。余下候选包括
`/data/media/obb` 的准备以及 `fscrypt_prepare_user_storage` 检查的 DE 目录。Recovery
内的 logd 崩溃循环使 vold 的具体错误丢失。

本脚本在已有 v3.36 上临时记录正常解密重试的目录与策略调用。仅附加到单个
`/system/bin/recovery` 进程，45 秒后脱离。日志记录路径、权限和 errno。跟踪范围
排除 read、write 和 execve，ioctl 与 xattr 缓冲区以地址显示，避免记录密钥内容。

把生成的 `turner-fbe-trace.sh` 推到 `/tmp`，在平板 root Recovery 终端运行
`sh /tmp/turner-fbe-trace.sh`。出现 `FBE trace attached` 后，在 45 秒内点一次此前失败
的解密按钮。约 45 秒后输出 `/tmp/turner-fbe-trace-logs.tar`，可通过 ADB 拉取。

实机跟踪确认四个 DE 目录的策略设置都返回成功，紧接着子进程以状态 1 退出。
v3.36 ramdisk 缺少其所需的 `vold_prepare_subdirs`。后续用 [已有 v3.36 的临时测试](../stage52/README.md)
记录辅助程序的退出状态，实机跟踪包已足够定位。

## 构建与许可

使用未修改的 strace 6.13 源码。对应源码为 [Debian 原始 tarball](https://deb.debian.org/debian/pool/main/s/strace/strace_6.13+ds.orig.tar.xz)，
SHA256 `3efb31716098b891f833e38432083a9863aa6ef45a5be26438cfd9833fac2e6d`。
源码内 `COPYING` 和 LGPL-2.1 文本注明许可，打包时作为注释一并附带。musl 采用
对应 Zig 工具链的源码和许可证。

使用 ziglang 0.17.1，解压源码后在独立构建目录配置。Debian 重打包源码省略了
`debian/changelog.in`，为生成打包配置可在解压目录补一行 `@PACKAGE_VERSION@`。
这不影响 strace 的编译源码。

```sh
strace_src=/absolute/strace-6.13
strace_uapi="-I$strace_src/bundled/linux/arch/arm64/include/uapi -I$strace_src/bundled/linux/include/uapi"
CC='python3 -m ziglang cc -target aarch64-linux-musl' \
  CFLAGS='-Os' LDFLAGS='-static -s' "$strace_src/configure" \
  --host=aarch64-linux-musl --enable-bundled=yes --enable-mpers=no --without-libdw --without-libunwind \
  --without-libselinux --disable-gcc-Werror --disable-dependency-tracking
make -C src -j8 bundled_CPPFLAGS= CPPFLAGS="$strace_uapi"
python3 hybrid/stage51/package_trace.py --strace /absolute/build/src/strace \
  --license /absolute/strace-and-musl-notices.txt --output turner-fbe-trace.sh
```

`make` 的 include 路径优先使用 strace 随附的 Linux UAPI，让这版源码使用与其匹配的结构体定义。

参考 [YARP vold 的 DE 初始化](https://github.com/TWRP-Test/android_system_vold/blob/twrp-16.0/FsCrypt.cpp)
和 [Recovery 解密入口](https://github.com/TWRP-Test/android_bootable_recovery/blob/twrp-16.0/partition.cpp)。
