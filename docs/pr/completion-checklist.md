# PR #78 完工清单

这份清单用于把兼容性汇总从 Draft 推到可审查、可合并状态。历史设备记录不等于当前候选版本的完整验收。

## 当前门槛

| 门槛 | 状态 | 完成条件 |
|---|---|---|
| 分支同步 | 进行中 | 最新 `master` 为 `a001e6d`；原基线后新增 1038 个提交，已建立独立集成工作树处理冲突 |
| 变更分层 | 待办 | Wine/native/构建修复进入 `master`；应用库和产品界面进入 `main-ui` |
| 主机回归 | 旧基线候选通过 | Linux 27 个编译/运行阶段（含 ASan/UBSan），Windows 8 个 JS 组及包完整性回归通过；最新主线集成版须重跑 |
| 完整构建 | 待办 | 干净目录完成 arm64 HAP、Native/Wine/Mesa/VirGL、core、wine-vulkan、DXVK、D3D12 |
| 设备验收 | 单设备套件通过 | core 4/4、wine-vulkan 4/4、dxvk 3/3、d3d12 3/3；多设备、完整 IME 和真实游戏长跑仍待补齐 |
| PR 状态 | 待办 | 补齐 review/CI 后再把 Draft 改为 Ready for review |

## 本地验证

- TypeScript/ArkTS：桌面输出、指针、游戏库、触控、鼠标模式和虚拟按键回归通过。
- C++ host：20 个纯逻辑用例通过；事件总线测试已对齐当前 21 个事件，z-order 测试改为字符串内容比较。
- 字体策略：`wine.inf` 以 UTF-8（含 BOM 兼容）读取，中文字体别名回归通过。
- HAP 构建：干净 `hvigor clean` 后 `assembleHap` 成功；候选包 CRC、runtime manifest/hash 和 native markers 校验通过。
- 设备启动：首次候选包因 native 依赖未被 HAP 收集而触发 `libentry.so` 加载失败；改用实体 `entry/libs/arm64-v8a` 并干净重打包后，28 个 native 库进入 HAP，设备启动保持运行。

## 设备 smoke 状态

候选 HAP 已安装到设备并保持常亮。最初 core 无 summary 是手工生成的测试 JSON 含字面量换行转义导致，后续已由合法的 suites/manifest 替换。修复 SmokeRunner 错误日志后定位到此问题。

OpenGL 随后失败于 `no compositor display sequence observed`，原因是 smoke Want 将管理页拉回前台，而手机普通会话有意不自动打开桌面。最终修复将前台准备放入 SmokeRunner 的共同执行路径：冷启动、二次 Want、开发面板均传入当前调用方的 UIAbilityContext，等待 root、请求 DesktopAbility，并确认 surface 就绪后再启动测试。普通无 smoke 请求的启动不触发前台切换。`prefix=reuse` 在 runtime 升级待处理时会失败并保留环境，只有显式 clean 请求可走测试重置。

### 当前权威归档

| 套件 | 主机判定 | 本地目录（相对候选工作树） |
|---|---|---|
| core | PASS 4/4（含两架构四象限截图） | `build/automation-logs/core-core-foreground-fixed/` |
| core（Linux 新编 DNS） | PASS 4/4 | `build/automation-logs/core-core-linux-dns-rebuilt/` |
| wine-vulkan | PASS 4/4 | `build/automation-logs/wine-vulkan-wine-vulkan-pr78-followup/` |
| dxvk | PASS 3/3（含 cube 截图） | `build/automation-logs/dxvk-dxvk-pr78-6bf3abe/` |
| d3d12 | PASS 3/3；1000 帧 + gears/triangle 各 600 帧 | `build/automation-logs/d3d12-d3d12-pr78-6bf3abe/` |
| DXVK 专用 D3D9 档位 | FAIL 0/4；载荷缺少 x64/x86 DXVK `d3d9.dll` | `build/automation-logs/dxvk-d3d9-dxvk-d3d9-explicit/` |
| DXVK 专用 D3D9 档位（重建 DLL 后） | FAIL 1/4；x64 D3D11 通过，x64 D3D9 建设备失败，x86 DLL 加载失败 | `build/automation-logs/dxvk-d3d9-dxvk-d3d9-rebuilt-138733/` |

后三套件对应 `6bf3abe` 候选；第一次完整 core 通过时已包含同样的共同前台逻辑，但尚未加入 reuse 升级保护。HAP 的 Native/ArkTS 是本轮构建；Wine/Mesa/VirGL 和最初 smoke EXE 复用已有产物。这些不是完整运行时从零重建证据。Linux 另已重新编译两架构 DNS probe，图形探针仍来自已有 Wine PE 构建，构建来源记录在单独 core payload 的 `build-provenance.json`。

`6bf3abe` HAP SHA-256：`98227b4b76a080594604576ef701fba09f9e06c082c3609585129cea7d741746`。Wine payload SHA-256：`d6eef4ffaecf84e45fc431d878aeaf108471b9fddb2df061b9e6fa0e4c1cf58a`。

当前候选仍需要与最新主线完成集成并完整重建。已有旧基线通过记录不能代替集成后的验收，也不能据此标记整个 PR 完工。

本轮公开证据边界与哈希见 [November 1 validation follow-up](../debugging/pr78-validation-20261101.md)。

D3D9 后端契约复核发现，自动化曾漏接 native 已支持的 `dxvk_legacy_d3d9`。现已恢复专用档位并放行该精确值；保留对模糊 `dxvk` 的拒绝。两架构 DXVK Legacy 已在独立 Linux 目录重建，新包完整性检查通过；设备上的 13 个 DXVK 运行库/清单文件已备份、替换并回读核验，未重置 prefix。新载荷 SHA-256 为 `138733418e6deb7b525606805a1fe0e9526a53567ec377e92b0904eebd899b3e`。专用套件仍失败，不能把 DLL 打包修复等同于 D3D9 可用，也不能用普通 `dxvk_legacy` 替代专用档位来规避。
