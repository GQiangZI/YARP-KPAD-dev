# v3.38 Authorization 服务查询测试

v3.37 实机已经重启 keystore2，并返回 `GateKeeper status ok`。紧接着
YARP 对 `android.security.authorization` 的查询超时，未执行
`addAuthToken`。这个 init 环境仍使用原厂 ServiceManager 的旧查询协议。

仅把该服务加入现有的兼容查询名单，YARP 仍使用原厂服务递交和验证真实的
GateKeeper 令牌。沿用 stage50 的编译命令，使用 `build_auth.py --base`
指定实机验证的 v3.37 镜像，`--bridge` 指定新编译的共享库。
