# x11 多窗窗口装饰（顶条 UI 化）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, 单 agent 全程) 实施。

**Goal:** x11 多窗形态补齐窗口装饰——Pad 子窗顶条可视化（标题+三键），PC WWA 形态开系统装饰；关闭出路盘点；known-issues §2.15 装饰行改写。

**Architecture（核心设计判断，M4d 实测支撑）:** x11drv 的 wine X 窗 = win32 rect 减 WM 装饰区（caption+border 偏移，M4d 实测 D52 created 坐标即证）——**ArkTS 顶条占用的正是被减掉的装饰区**：承载窗总高 = guest h + STRIP_PX，XComponent 下移 STRIP_PX，guest 帧几何不变，wine 零感知。三键直接驱动 M4b 已验证的承载动作链（hide/show→FusionWindowManager、destroy→既有关窗链），不新增任何 native 通道。

**Tech Stack:** ArkTS（FusionWindowManager/WineWindow 页面布局、WWA 装饰开关）。

**Spec:** 任务 #129；known-issues §2.15 装饰行（M4d review Minor#2/文档 gate 关联项）。

## Global Constraints

- **禁止 wine 侧改动**（零 x11drv/wine 源码触碰——方向 ① 的定义即此）；禁合成器装饰（方向 ② 明确不做）
- incumbent 对齐红线：wayland 路线行为不变（顶条/装饰改动只落 x11 分叉或 x11 形态判定内）
- STRIP_PX = 20 × getEffectiveScale()（M4d Minor#3 教训，禁止硬编码 scale）
- 判定：真机手测清单 + 截图归档 .temp/decor-*；fusion 套件回归不回归（5 checks + popup）
- 设备纪律照旧（POC 优先、限时前台、帧污染作废重跑）

## Review Focus

1. **顶条与 guest 首帧时序**：子窗高度补偿（w, h+STRIP）要在 created/resize 事件的尺寸进 FusionWindowManager.resize 前完成换算——否则 onSurfaceChanged 反馈环（M4a T2 教训）会把 40px 差回写 wine
2. **PC WWA 系统装饰开关的视觉核实**：setWindowDecorVisible(true) 在 x11 PC 形态的实际渲染（系统装饰样式/标题文字来源/windowTitle 与 wine title 事件的同步——WWA 现有 setWindowTitleButtonVisible(false) 三连要先恢复）
3. **关闭键的语义链**：close 键 = 子窗 destroyWindow 路径（FusionWindowManager.destroy）→ destroyed 事件缺失（子窗主动销毁不发 wine destroyed——wine 侧窗口残留的处置，执行时核实 sendToplevelClose 是否需要补发）
4. **顶条出现后的 hit-test**：M4d 顶条是手势判定（tap 直通 guest），UI 化后顶条区变成 OHOS 控件——guest 顶部内容被盖 + 点击被顶条吃掉是**预期行为**（装饰区语义），但要验证 wine 客户区 hit-test（HTCLIENT 判定）不含顶条区——wine 不知道装饰存在，它的菜单栏 y=0 从 XComponent 顶开始，点菜单 = 点 XComponent 区域 ✓ 应自洽，实测确认

---

### Task 1: Pad 子窗顶条 UI（几何补偿式）

**Files:** `entry/src/main/ets/pages/WineWindow.ets`（顶条 Row：标题 Text + ─ □ × 三键，仅 multiwindow+fusion 子窗形态渲染）、`entry/src/main/ets/service/FusionWindowManager.ets`（resize 尺寸补偿 h+STRIP、定位/restore 同步）、`entry/src/main/ets/service/WineWindowManager.ets`（title 事件 → 顶条标题同步，若 WineWindow 已订阅则复用）

- [ ] T1.1 布局：WineWindow 页 Stack 顶部加顶条 Row（高 STRIP_PX，背景深色、标题白字、三键），XComponent 约束下移 STRIP_PX；仅 fusion 子窗形态启用（PC WWA 走 T2 系统装饰）
- [ ] T1.2 尺寸补偿：FusionWindowManager resize/ensure 的承载窗尺寸 = guest h + STRIP_PX（created/resize 事件换算单点）；created 的初始定位同补偿
- [ ] T1.3 三键接线：─ = FusionWindowManager.hide（M4b minimized 链）、□ = fullscreen/restore 切换（幂等位已有）、× = destroy 链（核实 wine 侧残留处置——Review Focus #3）
- [ ] T1.4 标题同步：title 事件 → 顶条 Text（entry.title 已有）
- [ ] T1.5 构建 + 真机：双窗截图（.temp/decor-pad-1.jpeg）+ 三键逐一操作 + 拖动仍跟手（顶条即拖把手，f43c764 的手势区与顶条重合——确认共存）+ fusion 套件回归 5 checks
- [ ] T1.6 Commit

### Task 2: PC WWA 系统装饰

**Files:** `entry/src/main/ets/entryability/WineWindowAbility.ets`（decor 开关恢复——现有 setWindowDecorVisible(false) 改 true、标题按钮恢复、D52 定位块适配装饰高）

- [ ] T2.1 x11 形态判定内开装饰（wayland 不动——incumbent 红线）：decor visible + 标题按钮，实测视觉（.temp/decor-pc-1.jpeg）
- [ ] T2.2 D52 定位块与装饰高的适配（若有偏移）+ fusion 套件 PC 形态复跑（--extra-ps winehua.fusionHost ability，M4d gate 的用法）
- [ ] T2.3 Commit

### Task 3: 关闭出路盘点 + known-issues 改写

- [ ] T3.1 盘点清单逐项实测：顶条 × 键 / Alt+F4（MM key 注入链，Ctrl+Alt 组合的可达性实测）/ Pad 任务卡片滑动关闭 / 应用自身退出（notepad 菜单）——每项截图或日志归档
- [ ] T3.2 known-issues §2.15 装饰行改写（装饰补齐后的状态 + 各出路结论）+ §2.14 关联更新
- [ ] T3.3 Commit + push

## Self-Review

Spec 覆盖：任务 #129 三方向落 T1（顶条）/T2（PC 装饰）/T3（出路）；几何补偿的设计判断有 M4d 实测锚点；RF 四条均有核实步骤。占位符：无 TBD；「执行时核实」点（close 键 wine 残留、decor 视觉）都在步骤内给锚点。
