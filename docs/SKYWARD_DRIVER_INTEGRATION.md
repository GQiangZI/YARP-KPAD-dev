# Skyward 3.0.306 驱动完整整合 / Verified driver integration

[简体中文](#简体中文) | [English](#english)

## 简体中文

**当前状态：274 个 Skyward 原版模块已从两个能启动的镜像中提取并校验，整合脚本和 CI 已准备好，但 GitHub 仓库中的旧版 `.ko` 尚未完成替换。**

本项目不会单独替换部分模块，因为当前仓库与 Skyward 3.0.306 的 **274 个 `.ko` 全部存在哈希差异**；混合版本可能导致启动、显示、触控或解密异常。

### 唯一缺少的步骤：将已验证的驱动压缩包传入 GitHub

由于 GitHub 连接不支持直接从当前工作环境上传二进制附件，压缩包需要通过 GitHub 网页放入本开发仓库一次。此步骤不涉及刷机或编译。

- 文件名：`Skyward_turner_OS3.0.306_modules_reference.zip`
- 仓库上传路径：`references/skyward/Skyward_turner_OS3.0.306_modules_reference.zip`
- 文件大小：约 15.6 MiB（GitHub 网页上传文件限制为 25 MiB）
- **压缩包 SHA-256**：`28ca760a4b6cc867c04493b6b29e0104b1ee1fd820a264b6c3169c336d811fad`
- 进入 GitHub 仓库的 `references/skyward/` 目录，选择 **Add file → Upload files**，上传该压缩包并提交到 `main`。
- 上传后 [`Import verified Skyward 306 drivers (SOURCE ONLY)`](../.github/workflows/integrate-skyward-modules.yml) 会自动运行；也可手动触发。

工作流将拒绝来源不符、任何文件 SHA-256 不符、非 274 个模块、模块文件名/元数据不匹配或目标不是 turner 的情况。通过全部验证后，**一次性替换全部 274 个驱动**，再次核对整套哈希，并提交 `analysis/SKYWARD_MODULES_APPLIED.json`。

导入任务会在同一个提交中从主分支移除临时 ZIP；**但 Git 历史会保留原始上传对象**。这是公开仓库，只有确认压缩包适合公开时才上传。

**整合驱动并不等于 YARP 可正常启动。** 后续仍必须编译、检查 init/ABI、Vendor Boot v4 与 AVB 结构，并在可恢复条件下实机测试。Wi-Fi 继续暂缓。

### 本地离线核验

```bash
# 只核对压缩包和仓库，不修改文件
python3 tools/apply_verified_skyward_zip.py Skyward_turner_OS3.0.306_modules_reference.zip --tree .

# 确认后才做完整源代码替换（仍不会生成可刷镜像）
python3 tools/apply_verified_skyward_zip.py Skyward_turner_OS3.0.306_modules_reference.zip --tree . --apply
python3 tools/check_skyward_module_set.py --tree .
```

## English

The 274 Skyward driver binaries and five metadata files have been extracted from both boot-tested turner images and validated. The repository importer and tests are ready, **but the public source tree still contains the original mismatched binaries until the reference ZIP is uploaded.**

Upload the exact `Skyward_turner_OS3.0.306_modules_reference.zip` (SHA-256 `28ca760a4b6cc867c04493b6b29e0104b1ee1fd820a264b6c3169c336d811fad`) to `references/skyward/` on the `main` branch using GitHub's **Add file → Upload files** interface. The dedicated source-only workflow then verifies every hash, atomically imports all 274 modules, generates an audit record, and removes the temporary archive from the latest tree. Note that Git history retains uploaded files.

**Importing the driver set is not a build, boot test or flash-safety approval.** Further YARP GUI2, init, crypto, vendor_boot and device validation remains required.

[仓库首页 / Repository](../README.md) · [安全要求 / Safety](../SAFETY.zh-CN.md)
