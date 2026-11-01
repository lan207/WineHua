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

首轮 Wayland core 原始结果 4/4 通过，但主机只判 2/4：旧图形探针缺少主线要求的 expectedRoute/presentedRoute。已从当前 Wine gitlink 源码独立编译两架构图形/DNS 探针用于重验；此独立编译不代表 Wine 引擎重建。另已修复显式 `--display-route wayland` 时主机期望仍为 X11 的编排错误，并保留 job 声明路线的独立检查。

仍需当前探针下的完整设备回归、最新 Wine/guest Mesa 运行时构建和 X11 默认路线验收。DXVK 专用 D3D9 档位仍未通过。应用库/产品界面仍需按 master/main-ui 规范拆分。

## 旧基线候选的证据边界

独立的 `fix/compatibility-history-rollup` 分支已有单设备 core 4/4、wine-vulkan 4/4、dxvk 3/3、d3d12 3/3 主机判定，以及 Linux 27 阶段 ASan/UBSan 回归记录。Native/ArkTS 为本轮构建，Wine/Mesa/VirGL 复用现有产物，未完成完整运行时从零重建；也未完成多设备、完整 IME 和真实游戏长跑验收。

原开发工作树与已通过验收的候选工作树均保留独立；本分支的构建失败不改变那些历史记录的范围。
