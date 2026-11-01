# PR #78 与最新主线集成

核实日期：2026-11-01。集成基线为官方 `master` / `a001e6d0ca277d5a5fb2b4bd6a030ac52e5e132e`，分支为 `integration/pr78-upstream`。这是集成检查点，尚未具备可合并的完整验证。

## 已完成

- 合并 PR 的 `6bf3abe` 候选变更，处理全部 21 个文本/删除冲突；保留主线 X11 路线、CreatedAt/Restored/Modal 契约、XKB/X11 构建接线及桌面退出状态。
- DesktopWindow 沿用主线的 DesktopLayer 组件承载。PR 的直接按住、相对鼠标和虚拟按键经 DesktopInputSink 分发，Wayland 保留 surface 身份和键盘焦点，X11 保留原有注入通道。
- 八组 Node/TypeScript 回归通过，包括直接/相对鼠标、共享按键、取消/释放、游戏库、输出策略和冷暖 smoke 前台准备。X11 smoke 的 root=0 使用 canvas 就绪条件。
- ARM64 display-route 链已在隔离 Linux 目录完成编译与 wlroots 试链接，包括新编的 Wayland、VirGL、X11、wlroots 和 Xwayland。补齐干净构建所需的 scanner、libffi/FreeType 元数据、协议枚举头及 EGL 补丁头文件依赖。
- 集成版 Native/ArkTS HAP 构建成功，包内 68 个原生库以及 16 个 DXVK DLL 的完整性检查通过；调试签名包已覆盖安装，未卸载或重置 prefix。
- 修复集成版首启闪退：系统 SIGSEGV 栈定位到 EGL 导入探针把裸 `OH_NativeBuffer*` 传入驱动。探针现仅使用 `OHNativeWindowBuffer*` 包装，实机标记为 `pass:payload=OHNativeWindowBuffer`，应用保持运行。主机回归执行实际导入代码，旧源码对照会触发错误载荷断言。

## 当前构建门槛

当前集成 HAP SHA-256：`5e0aeb018caa499dc31b62440b1521ab5b81777983e848d7b1e2bb06a455c568`；libentry SHA-256：`83b56f81de915e428e4c723c12a291ff2a4b428c558982dd4a8cc0613e9ad733`。运行时载荷为增量重建 DXVK 的 `138733418e6deb7b525606805a1fe0e9526a53567ec377e92b0904eebd899b3e`，Wine/guest Mesa 仍复用旧产物，因此不是完整运行时从零重建。

当前源码探针下的 Wayland core 已通过主机判定 4/4，归档 `build/automation-logs/core-integration-current-core-5e0aeb/`，payload 版本 `smoke-v2-14fad0447506`。两架构图形/DNS 探针由当前 Wine gitlink 源码独立编译；此独立编译不代表 Wine 引擎重建。普通 DXVK 在同一集成 HAP 下通过 3/3，归档 `build/automation-logs/dxvk-integration-dxvk-5e0aeb/`。显式显示路线现在同时决定主机验收期望，job 声明路线仍独立核验。

D3D9 后续候选仅更改显式兼容模式的可选 Vulkan 特性请求：不向驱动请求缺失的 BC/multiViewport，默认严格行为保留，未实现的压缩格式仍由格式能力检查拒绝。两架构 DLL 已重新编译；x64 D3D9 实机用例完成 623 帧且截图通过。该次只选了一个用例，套件覆盖检查仍为 FAIL，不能当成完整 D3D9 套件通过。候选 HAP SHA-256 为 `df84c2d9b9dadd8b112c4132c4c27feed2c819c8a1dff72c3d46ceb69f45ad44`，载荷 SHA-256 为 `0aa1eac9b72376ea5094441b5d5b27067b1266dcd275c442d5148e0960404e0c`；已按相同的备份/回读步骤更新管理运行库，未重置 prefix。Wine loader 的专用 D3D9/D3D10 overlay 搜索补丁已通过主机 WoW64/档位隔离测试，仍需重建 Wine 后实机验证 x86。

仍需当前探针下的完整设备回归、最新 Wine/guest Mesa 运行时构建和 X11 默认路线验收。DXVK 专用 D3D9 档位仍未通过。应用库/产品界面仍需按 master/main-ui 规范拆分。

## 旧基线候选的证据边界

独立的 `fix/compatibility-history-rollup` 分支已有单设备 core 4/4、wine-vulkan 4/4、dxvk 3/3、d3d12 3/3 主机判定，以及 Linux 27 阶段 ASan/UBSan 回归记录。Native/ArkTS 为本轮构建，Wine/Mesa/VirGL 复用现有产物，未完成完整运行时从零重建；也未完成多设备、完整 IME 和真实游戏长跑验收。

原开发工作树与已通过验收的候选工作树均保留独立；本分支的构建失败不改变那些历史记录的范围。
