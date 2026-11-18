# turner v3.36 data 解密测试

v3.35 实机 fstab 修正生效，主进程的 `checkService` 和 `waitForService` 均得不到
keystore2，`/data` 未挂载。后续探针在 split 环境中用旧事务 2 查到了 keystore2、
KeyMint 和 Gatekeeper。split 环境使用原厂 `libbinder.so` 与 twrp16
`libbinder_ndk.so`。recovery 和 stock 两组只有退出码，无法判断它们的查询结果。

v3.36 把同一段旧查询代码接进 recovery 的预加载库。真实的现代查询返回空时，
只对五个加密服务的明确实例名发送一次旧 `CHECK_SERVICE`。ServiceManager 仍执行
原有权限检查。使用 `RTLD_NOLOAD` 取得 recovery 已加载的 Binder 库，用这些库
创建和解析 Parcel。每次返回一个由调用方负责释放的服务句柄。vold 继续按原期限
轮询。日志记录库路径、查询阶段、状态码及首次查到句柄的结果。

## 构建

```sh
python3 -m pip install ziglang==0.17.1 lz4 pyelftools
mkdir -p build/stage50
python3 -m ziglang cc -target aarch64-linux-android -mcpu=generic+lse \
  -Os -ffreestanding -fno-stack-protector -nostdlib -shared -fPIC -s \
  -Wall -Wextra -Werror -Wl,-z,max-page-size=4096 \
  -Wl,-soname,libturner_crypto.so -DTURNER_BINDER_BRIDGE \
  hybrid/stage48/libturner_crypto.c hybrid/stage49/binder_probe.c \
  -o build/stage50/libturner_crypto.so
python3 tests/stage50/test_legacy_lookup.py
python3 hybrid/stage48/build.py \
  --base /absolute/path/turner-vendor_boot-hybrid-v3.30.img \
  --bridge build/stage50/libturner_crypto.so \
  --release v3.36-CRYPTO-LEGACY-TEST \
  --output turner-vendor_boot-hybrid-v3.36-CRYPTO-LEGACY-TEST.img
```

构建器核对 v3.30 输入的完整 SHA256、新增库的直接依赖和已加载库所需导出，
校验 ramdisk 文件差异、DTB、vendor_boot 分区大小和 AVB 哈希。相较 v3.35，
归档条目只有解密桥接库和诊断脚本不同。主机测试覆盖迟注册、服务消失、权限与
传输失败、句柄引用与 Parcel 清理。仍需使用 Redmi K Pad 实机确认数据挂载。

## 实机验证

对 turner 的 `vendor_boot` 刷入测试镜像，保留已实测启动的版本作为回退。
进入 Recovery，观察内置存储能否显示原有文件。有凭据页面时正常输入一次。
在平板本机 Recovery 终端运行以下命令，生成 `/tmp/turner-v336-logs.tar`。

```sh
sh /system/bin/turner-crypto-status.sh
```

首批 v3.36 镜像把日志包设为仅 root 可读。用该镜像时，生成后在平板终端执行
`chmod 644 /tmp/turner-v336-logs.tar`。

在手机 Termux 拉取日志。

```sh
adb pull /tmp/turner-v336-logs.tar "$HOME/storage/downloads/"
```
