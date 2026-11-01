# PR #78 完工清单

这份清单用于把兼容性汇总从 Draft 推到可审查、可合并状态。历史设备记录不等于当前候选版本的完整验收。

## 当前门槛

| 门槛 | 状态 | 完成条件 |
|---|---|---|
| 分支同步 | 待办 | 同步最新 `master`，解决冲突，并确认可快进合并 |
| 变更分层 | 待办 | Wine/native/构建修复进入 `master`；应用库和产品界面进入 `main-ui` |
| 主机回归 | 部分 | Node/TypeScript 和可移植 C++ host 用例已通过；Linux/ASan/UBSan 仍待执行 |
| 完整构建 | 待办 | 干净目录完成 arm64 HAP、Native/Wine/Mesa/VirGL、core、wine-vulkan、DXVK、D3D12 |
| 设备验收 | 待办 | 多设备冷启动、前后台恢复、IME 组合输入、真实游戏长跑和错误弹窗回归 |
| PR 状态 | 待办 | 补齐 review/CI 后再把 Draft 改为 Ready for review |

## 本地验证

- TypeScript/ArkTS：桌面输出、指针、游戏库、触控、鼠标模式和虚拟按键回归通过。
- C++ host：20 个纯逻辑用例通过；事件总线测试已对齐当前 21 个事件，z-order 测试改为字符串内容比较。
- 字体策略：`wine.inf` 以 UTF-8（含 BOM 兼容）读取，中文字体别名回归通过。
- HAP 构建：干净 `hvigor clean` 后 `assembleHap` 成功；候选包 CRC、runtime manifest/hash 和 native markers 校验通过。
- 设备启动：首次候选包因 native 依赖未被 HAP 收集而触发 `libentry.so` 加载失败；改用实体 `entry/libs/arm64-v8a` 并干净重打包后，28 个 native 库进入 HAP，设备启动保持运行。

## 设备 smoke 状态

候选 HAP 已安装到设备并保持常亮。`core` smoke 已推送 payload，但本机 MinGW GCC 16.2 在重新编译 `winehua_dns_probe.c` 时触发编译器内部错误，因此本轮没有把旧 payload 冒充为本候选的完整新编译结果；一次手工复用历史 payload 的运行因自动化 App 的二次启动/轮询链未产生 summary 而中止，归档保留在 `build/automation-logs/core-r20261101-130000/`。

当前候选仍需要 Linux 构建机完成完整构建和 ASan/UBSan 回归，不能仅凭本机 host 结果标记为完工。
