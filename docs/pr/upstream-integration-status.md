# PR #78 与最新主线集成

核实日期：2026-11-01。集成基线为官方 `master` / `a001e6d0ca277d5a5fb2b4bd6a030ac52e5e132e`，分支为 `integration/pr78-upstream`。这是集成检查点，尚未具备可合并的完整验证。

## 已完成

- 合并 PR 的 `6bf3abe` 候选变更，处理全部 21 个文本/删除冲突；保留主线 X11 路线、CreatedAt/Restored/Modal 契约、XKB/X11 构建接线及桌面退出状态。
- DesktopWindow 沿用主线的 DesktopLayer 组件承载。PR 的直接按住、相对鼠标和虚拟按键经 DesktopInputSink 分发，Wayland 保留 surface 身份和键盘焦点，X11 保留原有注入通道。
- 八组 Node/TypeScript 回归通过，包括直接/相对鼠标、共享按键、取消/释放、游戏库、输出策略和冷暖 smoke 前台准备。X11 smoke 的 root=0 使用 canvas 就绪条件。
- 本地包依赖安装完成；未把此集成版安装到设备。

## 当前构建门槛

完整 HAP 构建在 Native 链接前失败：`entry/libs/arm64-v8a/libX11.so.6` 缺失。最新主线还需要 `build/host-ext/arm64-v8a` 的 wlroots/X11 依赖，这些不在旧基线候选的 28 库包中。

源子模块正在按主线 gitlink 初始化。依赖齐全后仍需完整构建、重跑 host 与设备套件；不能用旧基线的通过记录作为本集成版的验收结论。应用库/产品界面仍需按 master/main-ui 规范拆分。

## 旧基线候选的证据边界

独立的 `fix/compatibility-history-rollup` 分支已有单设备 core 4/4、wine-vulkan 4/4、dxvk 3/3、d3d12 3/3 主机判定，以及 Linux 27 阶段 ASan/UBSan 回归记录。Native/ArkTS 为本轮构建，Wine/Mesa/VirGL 复用现有产物，未完成完整运行时从零重建；也未完成多设备、完整 IME 和真实游戏长跑验收。

原开发工作树与已通过验收的候选工作树均保留独立；本分支的构建失败不改变那些历史记录的范围。
