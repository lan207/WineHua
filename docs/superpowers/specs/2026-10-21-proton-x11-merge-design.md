# 合并设计：feature/proton-x11 —— Proton 引擎 × x11 显示路线

> 状态：已批准（2026-10-21 用户确认方案 A）
> 目标：合并 `feature/proton-wine-ohos`（Proton 引擎线）与 `feature/display-route-m0`（x11 显示路线），
> 以新分支 `feature/proton-x11` 承载（主仓库与涉及合并的 submodule 同名），支撑 Steam 按
> 决策 0005 口径在 OHOS 上运行。
> 上游决策：[0005-proton-trunk-roadmap](../../../docs/decisions/0005-proton-trunk-roadmap.md)（m0 分支）、
> [x11 wlroots 设计](2026-09-27-display-route-x11-wlroots-design.md)（m0 分支）

## 1. 背景与实测事实

merge-base = `1ec7c0c5`；两分支各自演进：proton 侧 +66 提交（merge master + wine-valve
指针 + 部署脚本修复），m0 侧 +335 提交（x11 路线 M0→M4d 全程）。

| | proton 分支 | m0 分支 |
|---|---|---|
| 定位 | Proton 引擎：wine-valve（proton_11.0）+ FEX + ARM64EC | x11 承载：winex11 → Xwayland（纯 shm）→ wlroots → OHOS 薄适配层 |
| Steam | 能装/能登/出界面；卡 CEF webhelper BrowserReady + 内容区黑（09-20 证据） | 未接触 |
| 活跃度 | 09-24 后停更 | x11 缺省主线（2026-10-10 拍板），21 套件钉 x11 基线 |

- m0 的 `display/`、`display_route/` 为纯新增（cpp 侧 +15008/−460）；wayland incumbent
  的 compositor 仅 +124/−11——主仓库冲突面集中在双方都改的少数文件。
- m0 wine 树（`thirdparty/wine` @ `9f28b45d40`）= proton 记录指针（`cf39fdf1df`）+ 21 个
  x11 定制提交；x11 定制一行都不在 wine-valve 里，两树基线不同（proton_11.0 vs 11.10），
  只能语义重放、不能机械 cherry-pick。
- 图形加速链（VirGL/Venus/DXVK vtest）两分支共用，m0 仅重接 present 落点（Vulkan 私有面
  SURFACE_ID 重锚 X window id，M2 已实测）。

## 2. 已定裁决（用户拍板）

1. **引擎载体**：Steam/游戏统一走 wine-valve，x11 定制直接移植（一步收口），不经 wine 树试探。
2. **合并基底**：新分支 `feature/proton-x11`（从 proton 分出，merge m0）；两条源分支继续
   独立演进，集成验证成熟后再指认主干。
3. **承载方式**：submodule 与主仓库统一用 `feature/proton-x11` 承载合并结果；涉及新提交的
   submodule 各自开同名分支并推送远程，主仓库指针指向合并后引用。

## 3. 层 1 —— submodule 合并

### 3.1 快进类（实测祖先关系，直接移指针，不开分支）

| submodule | 收口指针 | 依据（实测） |
|---|---|---|
| `wine` | m0 `9f28b45d40` | = proton 指针 + 21 x11 提交，纯超集 |
| `wayland` | m0 `87cc8a872` | m0 领先 = 上游 1.26.0 升级 |
| `virglrenderer` | proton `bb33e52aa0` | merge-base 判定 = m0 指针（含 fence 修复） |
| `dxvk` | proton `7c5cc47f` | merge-base = m0 指针 |
| `dxvk-modern` | proton `05a0a66d7` | proton 含 m0 |
| `box64` | proton `e970ee6f2` | proton 含 m0 |
| `fex` | proton `86ff33bbe2` | m0 已删除，取 proton 恢复 |
| `wlroots` | m0 `d783533489` | m0 新增 |
| `xserver` | m0 `c5a47fda89` | m0 新增 |

### 3.2 移植类：wine-valve 的 feature/proton-x11（唯一新代码工作）

基于 `8b5bee4433`（含 master 7 条特性移植），把 m0 wine 树 21 提交中的 x11 定制按语义重放：

1. 构建系统：DISPLAY 分支直载 winex11 + 无 GLX 构建豁免（wine `2783492e84f`）；
   configure `--with-x --without-xshm`，头/库来自主仓库 display-libs 链（xcb 栈→libX11）。
2. 驱动选择：`WINEHUA_DISPLAY_ROUTE=x11` 进程级驱动覆盖（`e02e368348f`）；双驱动同树
   共存，wayland incumbent（winewayland OHOS 改造）不动。
3. GL 呈现：winex11 OpenGL 私有呈现桥 `opengl_winehua.c`（`27f6a5eafa4` + 修复
   `cb65b9cf6bb`）——pbuffer drawable + X window id，绕开无 GLX 与 Xwayland shmat SIGSYS。
4. Vulkan 呈现：SURFACE_ID 重锚 X window id（`a1e0d5868e8` + 驱动预加载 `9f7a73d5b46`）；
   宿主路由键 `(clientPid<<32)|surfaceId` 不变。
5. 语义补丁按需：D31 客户区内缩声明（`9bee42c9e07`）/ D33 HWND_BOTTOM
   （`4c3a018b137`）/ D34 SetCapture grab（`a56e91c8c3a`）。
6. 顺带核对：WHGP 断连退避（`6f11ac5dc8c`、`e578efa8d1b`）在 wine-valve 的 bus_ohos.c
   上是否有同样问题，有则一并重放。

### 3.3 树内合并类

- `mesa`：真分叉（merge-base `2939cbb81`；proton 侧 vtest 诊断 / m0 侧 VTEST_PRESENT
  值感知，各 1-2 提交）→ mesa 仓库开 feature/proton-x11 树内 merge。
- `libxkbcommon`：`7a31e3585` vs `d1442aaa6`，实施时跑祖先判定（预计快进，x11 链依赖）。

## 4. 层 2 —— 主仓库合并

`feature/proton-x11` merge `origin/feature/display-route-m0`。冲突解法：

| 文件 | 解法 |
|---|---|
| `.gitmodules` | 拼接：proton 的 wine-valve/fex 登记 + m0 的 wlroots/xserver 登记；wine branch 字段对齐实际 pin 分支 |
| `Makefile` | 拼接：proton 的 `WINE_SRC=thirdparty/wine-valve` + WINE_ARCH 隔离，加 m0 的 display-libs/display-route 构建链；wine configure 参数取并集 |
| `scripts/build_wine.sh` | 拼接：proton 的补丁应用机制 + WINE_ARCH 目录隔离 + llvm-mingw PATH 修复，加 m0 的 x11 configure 参数与 DISPLAY 分支 DLL 装载 |
| `wine_child.cpp` / `wine_env*` | 功能归属拼接：proton 的 steam/FEX env 章 + m0 的 DISPLAY route env 章 |
| `Index.ets` / `EntryAbility.ets` | 逐段核对拼接；路线切换单点 `applyRoute`（m0）保持唯一入口；GameContainer/SteamHost 归 wayland incumbent 形态，Steam 主承载走 x11 |
| `compositor/` | m0 侧仅 +124/−11，逐段解；硬约束 = wayland incumbent 行为不变 |
| `automation/smoke` + `smoke/` | proton 的 v2 通道/WINE_ARCH 参数化 + m0 的 21 套件 x11 基线 |
| `docs/` | 两边全保留：0005 决策、steam-win64 证据链、x11 spec/plan 全套 |

## 5. 层 3 —— 指针收口与推送

1. 主仓库指针落定为层 1 产物；wine-valve 指向其 feature/proton-x11 移植完成点。
2. 有新提交的 submodule（wine-valve、mesa，必要时 libxkbcommon/wayland）推送同名分支。
3. 主仓库 feature/proton-x11 推送 origin。
4. `.gitmodules` branch 字段收口推迟到主干切换（决策 0005 P3）；本阶段允许指向 feature 分支。

## 6. 验证门禁（每层独立）

| 层 | 门禁 |
|---|---|
| 1 | wine-valve x11 构建产出 winex11.drv + opengl_winehua 桥符号；wayland 路线 smoke core 全绿（incumbent 未破坏） |
| 2 | 完整 `make NATIVE_ARCH=arm64-v8a`；双路线真机烟测（x11 缺省 + wayland 对照）；A 类回归（modal/ARGB/多窗口/PC resize） |
| 3 | 从零 make 演练；Steam 验收按决策 0005 卡点 B：四项口径（vulkan-1.dll 原位 / 自检不反复下载 / CEF GPU 不进崩溃循环 / 界面实际操作有响应）+ 三次冷启动 |

## 7. 风险登记

1. x11 对 CEF 卡点（BrowserReady）是否有效无实证——本合并的门禁即验证项。
2. wine-valve 移植两树语义差（winex11 在 11.0/11.10 间有上游演进），逐条核对重放。
3. war3 黑屏排查（任务 #35）未闭环：wayland incumbent 保留 proton 现状，问题照旧，
   诊断 WIP 改动以 WIP 提交随分支携带，不混入合并提交。

## 8. 前置处置

当前 worktree（feature/proton-wine-ohos）有 5 个未提交诊断文件
（frame_composer.cpp / frame_pipeline.cpp / toplevel_manager.{cpp,h} / wl_core.cpp）：
先做 WIP 提交留档，再开 feature/proton-x11，合并过程中不与本设计改动混淆。
