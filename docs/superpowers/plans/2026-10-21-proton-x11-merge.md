# proton-x11 合并实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合并 Proton 引擎线与 x11 显示路线为 `feature/proton-x11`（主仓库 + submodule 同名分支），支撑 Steam 按决策 0005 口径运行。

**Architecture:** 三层递进——层 1 submodule（快进移指针 / wine-valve 移植 / mesa 树内合并），层 2 主仓库 merge，层 3 指针收口、构建与真机验证、推送。spec：`docs/superpowers/specs/2026-10-21-proton-x11-merge-design.md`。

**Tech Stack:** git 多仓库编排（主仓库 + 12 submodule）、wine 交叉构建（musl/OHOS）、hdc 真机验证。

**关键约定：**
- 源分支：`origin/feature/proton-wine-ohos`（基底）、`origin/feature/display-route-m0`（合入方）
- 主 worktree：`/data/share/wine-arm64`；**进入 submodule 前先确认目录**（同名路径两个仓库）
- commit message 不写 co-author；推送前须用户确认（Task 11）
- 两棵 wine 树：`thirdparty/wine`（参考实现，21 个 x11 提交在此）、`thirdparty/wine-valve`（移植目标）

---

## Task 1: 前置处置与分支建立

**Files:** 无新文件；处置 5 个未提交诊断文件。

- [ ] **Step 1: WIP 提交诊断改动留档**

```bash
cd /data/share/wine-arm64
git add entry/src/main/cpp/compositor/frame/frame_composer.cpp \
        entry/src/main/cpp/compositor/frame/frame_pipeline.cpp \
        entry/src/main/cpp/compositor/toplevel/toplevel_manager.cpp \
        entry/src/main/cpp/compositor/toplevel/toplevel_manager.h \
        entry/src/main/cpp/compositor/wl_core.cpp
git commit -m "wip(diag): war3 黑屏排查诊断日志 (MW-COMP/SRC/DST + EnsureFrameBase)

任务 #35 未闭环, 诊断改动以 WIP 提交携带, 不混入合并提交。"
```

- [ ] **Step 2: 开 feature/proton-x11 分支**

```bash
git checkout -b feature/proton-x11
git log --oneline -3
```
Expected: 顶端两个提交 = `0afe57e4 docs(spec)...` 与 WIP 提交。

- [ ] **Step 3: 记录 submodule 基线状态**

```bash
cd /data/share/wine-arm64 && mkdir -p .temp
git submodule status | tee .temp/proton-x11-submodule-baseline.txt
```
（`.temp/` 已 gitignore。此快照用于回滚对照。）

## Task 2: 快进类 submodule 就位（工作区 checkout 到收口指针）

**Files:** 无代码改动；仅 submodule 工作区移指针（主仓库 gitlink 在 Task 6 merge 中落定）。

- [ ] **Step 1: 逐个 fetch 并 checkout（对象缺失时才 fetch 对应远程）**

```bash
# 逐条执行, 每条 verify:
for spec in "wine 9f28b45d406" "wayland 87cc8a872" "virglrenderer bb33e52aa0" \
            "dxvk 7c5cc47f77" "dxvk-modern 05a0a66d74" "box64 e970ee6f21" "fex 86ff33bbe2"; do
  set -- $spec
  if ! git -C thirdparty/$1 cat-file -e $2^{commit} 2>/dev/null; then
    echo "FETCH NEEDED: $1 -> $2"
  else
    git -C thirdparty/$1 checkout --detach $2 && echo "OK: $1 -> $(git -C thirdparty/$1 rev-parse --short HEAD)"
  fi
done
```
Expected: 全部 `OK` 或列出需要 fetch 的项。对 FETCH NEEDED 的项：`git -C thirdparty/<sm> fetch origin`（wine/wayland/virglrenderer/dxvk 等远程 = github winehua org 或上游）后重跑 checkout。

- [ ] **Step 2: 验证收口指针与祖先关系**

```bash
git -C thirdparty/wine rev-list --count cf39fdf1df6..9f28b45d406        # Expected: 21
git -C thirdparty/wayland merge-base --is-ancestor b2649cb3e 87cc8a872 && echo wayland-ok
git -C thirdparty/virglrenderer merge-base --is-ancestor 6627c0314f bb33e52aa0 && echo virgl-ok
git -C thirdparty/dxvk merge-base --is-ancestor 5058927a74 7c5cc47f77 && echo dxvk-ok
```

- [ ] **Step 3: 不 commit**——主仓库 gitlink 落定在 Task 6 merge 冲突解决中统一 `git add`。

## Task 3: wine-valve 移植 —— feature/proton-x11（层 1 核心工作）

**Files（wine-valve 树内，全部路径相对 `thirdparty/wine-valve`）:**
- Modify: `configure.ac`、`dlls/win32u/driver.c`、`dlls/win32u/Makefile.in`、`dlls/win32u/winehua_present.c`(新)、`dlls/win32u/{d3dkmt.c,opengl.c,sysparams.c,vulkan.c,win32u_private.h,window.c}`、`dlls/winex11.drv/{Makefile.in,opengl.c,opengl_winehua.c(新),vulkan.c,window.c,x11drv.h,x11drv_main.c}`、`dlls/winewayland.drv/opengl_readback.c`、`dlls/winebus.sys/bus_ohos.c`
- 参考提交（`thirdparty/wine` 树内 `git show <sha>` 取全文）：
  `2783492e84f`(构建/直载) `e02e368348f`(驱动覆盖) `27f6a5eafa4`(GL桥) `cb65b9cf6bb`(GL修复)
  `a1e0d5868e8`(Vulkan面) `9f7a73d5b46`(预加载) `9bee42c9e07`(D31) `4c3a018b137`(D33) `a56e91c8c3a`(D34)

- [ ] **Step 1: 开分支**

```bash
cd /data/share/wine-arm64/thirdparty/wine-valve
git checkout --detach 8b5bee44334
git checkout -b feature/proton-x11
```

- [ ] **Step 2: 逐提交语义重放（按依赖序，每条 = 提取 diff → 核对上下文 → 应用）**

对每个源提交：
```bash
cd /data/share/wine-arm64/thirdparty/wine            # 参考树
git show <sha>                                        # 提取完整 diff
cd ../wine-valve                                      # 目标树
```
按顺序重放，每条的**两树差异核对点**（执行者必查）：
1. `2783492e84f`：`configure.ac` 的 X11 检测段在 11.0/11.10 间行号漂移——按语义放同位置；`dlls/win32u/driver.c` 的 DISPLAY 分支直载逻辑核对 wine-valve 侧已有的 winehua 改造（`winehua_readback_surface_create` 注册点）不冲突。
2. `e02e368348f`：驱动覆盖 env 读取点（driver.c）——确认 wine-valve 的 `__wine_init_unix_lib` 流程一致。
3. `27f6a5eafa4` + `cb65b9cf6bb`（合成重放，后者修前者四处缺陷）：新文件 `win32u/winehua_present.c`、`winex11.drv/opengl_winehua.c` 整文件搬运；`winex11.drv/opengl.c`、`win32u/driver.c`、`Makefile.in` 的接线段手工对位；`winewayland.drv/opengl_readback.c` 的改动**跳过**（wine-valve 该文件已有自己的 OHOS readback 改造，diff 里的改动若与 GL 桥共用符号再按需核对）。
4. `a1e0d5868e8`：`winex11.drv/vulkan.c` 整段——wine-valve 侧 vulkan.c 是否已有 WineHua SURFACE_ID 私有面（proton 分支的 venus 链改过 winewayland 的 vulkan 路径；winex11 侧应为上游原版）——若是原版直接应用。
5. `9f7a73d5b46`：win32u 六文件的预加载改动——driver.c 会与 1/2 的重放叠加，按最终态整理。
6. D31/D33/D34（`9bee42c9e07`/`4c3a018b137`/`a56e91c8c3a`）：winex11 window.c/x11drv* 与 win32u window.c——win32u/window.c 在两树有差异（如 wine-valve 的 `window_clip_client_surfaces`），只取与 x11 语义相关的 hunk。

规则：**不能机械 apply 就改到 apply 成功为止**——每个 hunk 先读懂再落位（spec §7.2）；重放完一个提交立即 commit（独立可回滚）：
```bash
git add -A && git commit -m "feat(x11): 重放 wine 树 <sha> —— <一句话语义>"
```

- [ ] **Step 3: WHGP 退避核对**

```bash
# 参考: thirdparty/wine 的 6f11ac5dc8c + e578efa8d1b (bus_ohos.c)
grep -n "last_drop_ms\|reconnect\|退避" dlls/winebus.sys/bus_ohos.c
```
若 wine-valve 的 bus_ohos.c 无退避逻辑且有同样的断连重连路径 → 按 wine 树最终态重放；已有等价物则记录跳过。

- [ ] **Step 4: commit 全部移植工作**（Step 2 已逐提交 commit；确认 `git log --oneline 8b5bee44334..HEAD` 每个源提交有对应落点）

## Task 4: mesa 树内合并

- [ ] **Step 1: 开分支并 merge**

```bash
cd /data/share/wine-arm64/thirdparty/mesa
git checkout --detach 330124bf18
git checkout -b feature/proton-x11
git merge e975a70730          # m0 侧: WINEHUA_VTEST_PRESENT 值感知
```

- [ ] **Step 2: 解冲突**

预期冲突极小（两侧各 1-2 提交：proton 侧 vtest 诊断 / m0 侧 VTEST_PRESENT 值感知）。原则：两侧都要（功能不同主题）；若同一函数则值感知语义优先、诊断打点跟随。`git status` 逐文件核对后 `git add` 并 commit。

## Task 5: libxkbcommon 祖先判定

```bash
p=$(git -C /data/share/wine-arm64 ls-tree origin/feature/proton-wine-ohos thirdparty/libxkbcommon | awk '{print $3}')
m=$(git -C /data/share/wine-arm64 ls-tree origin/feature/display-route-m0 thirdparty/libxkbcommon | awk '{print $3}')
cd thirdparty/libxkbcommon
git fetch origin 2>/dev/null; git merge-base $p $m
```
- merge-base = m → 快进，收口取 `p`（proton），无分支
- merge-base = p → 快进，收口取 `m`，无分支
- 真分叉 → 仿 Task 4 开 feature/proton-x11 树内合并（x11 链依赖，预期 m0 侧为准）

## Task 6: 主仓库 merge（层 2）

**Files:** 冲突解决涉及 `.gitmodules`、`Makefile`、`scripts/build_wine.sh`、`entry/src/main/cpp/wine_child.cpp`、`entry/src/main/cpp/wine/wine_env*`、`entry/src/main/ets/pages/Index.ets`、`entry/src/main/ets/entryability/EntryAbility.ets`、`entry/src/main/ets/smoke/*`、`automation/smoke.py`、gitlink × 若干。

- [ ] **Step 1: 执行 merge**

```bash
cd /data/share/wine-arm64
git merge origin/feature/display-route-m0
```
预期大量冲突（335 提交）。先 `git status --short | grep ^UU` 清点。

- [ ] **Step 2: gitlink 冲突按收口表 add**

```bash
# 快进类: 工作区已在收口指针 (Task 2), 直接 add
git add thirdparty/wine thirdparty/wayland thirdparty/virglrenderer \
        thirdparty/dxvk thirdparty/dxvk-modern thirdparty/box64 thirdparty/fex
# m0 新增: 自动进入或 add
git add thirdparty/wlroots thirdparty/xserver
# mes/libxkbcommon: 按 Task 4/5 结论
```
- `thirdparty/wine-valve`：m0 侧是删除（D），**保留我们的版本**——工作区 submodule 已在
  Task 3 的 feature/proton-x11 分支（8b5bee4433+），直接：
```bash
git add thirdparty/wine-valve
```

- [ ] **Step 3: .gitmodules 拼接**

两侧都要：proton 的 wine-valve/fex 登记 + m0 的 wlroots/xserver 登记。核对 `git diff origin/feature/proton-wine-ohos origin/feature/display-route-m0 -- .gitmodules` 的每一 hunk，逐段取舍后验证：
```bash
git config -f .gitmodules --list | grep -E 'wine-valve|fex|wlroots|xserver|wine\.'
```

- [ ] **Step 4: Makefile 拼接**

原则（spec §4）：proton 的 `WINE_SRC = thirdparty/wine-valve` + `WINE_ARCH` 隔离原样保留；引入 m0 的 display-libs / display-route 构建段（`Makefile:409-446` 一带：build_xcb_stack.sh / build_x11_client.sh / build_wlroots.sh / build_xwayland.sh 依赖链）；两段互不嵌套。冲突处两侧行都要时拼接、都要不冲突时合并成一段。

- [ ] **Step 5: scripts/build_wine.sh 拼接**

proton 侧保留：patches/wine/0001/0002 补丁应用段、WINE_ARCH 构建目录隔离、llvm-mingw PATH 修复。m0 侧引入：`--with-x --without-xshm --with-opengl --with-vulkan` configure 参数、ac_cv cache 变量段、DISPLAY 分支 DLL 装载清单（winex11.drv/opengl_winehua 相关 so 安装）。注意：合并分支构建树 = wine-valve，m0 段里引用 `thirdparty/wine` 的路径一律改指 `WINE_SRC`（=wine-valve）。

- [ ] **Step 6: cpp/ets 语义冲突逐文件解**

- `wine_child.cpp` / `wine_env*`：proton 的 steam/FEX env 章 + m0 的 DISPLAY route env 章，两段并存，无覆盖。
- `Index.ets` / `EntryAbility.ets`：路线切换单点 `applyRoute`（m0 DisplayRouteService）保持唯一入口；GameContainer/SteamHost（proton）归 wayland incumbent 形态分支。
- `compositor/`：m0 侧仅 +124/−11（wayland incumbent 行为不变是硬约束）；与 proton 侧 war3 期间改动逐段核对。
- smoke：proton 的 v2 通道/WINE_ARCH 参数化 + m0 的 21 套件 x11 基线共存。

- [ ] **Step 7: docs 全保留**

冲突的 docs 一律两侧内容都保留（0005 决策、steam-win64、x11 spec/plan 三套文档体系并存）。

- [ ] **Step 8: 完成 merge commit**

```bash
git commit    # 默认 merge message; 不加 co-author
git log --oneline -2
```

## Task 7: 指针收口（层 3 前半）

- [ ] **Step 1: 逐 submodule 核对主仓库 gitlink = 收口值**

```bash
for sm in wine wine-valve virglrenderer mesa dxvk dxvk-modern box64 wayland fex wlroots xserver libxkbcommon; do
  echo "$sm -> $(git ls-tree HEAD thirdparty/$sm | awk '{print substr($3,1,10)}')"
done
```
对照收口表（spec §3.1）；wine-valve = Task 3 完成点、mesa = Task 4 完成点。不符的：
```bash
git update-index --cacheinfo 160000,<完整sha>,thirdparty/<sm>
git commit -m "submodule: <sm> 指针收口到 proton-x11"
```

- [ ] **Step 2: 新增 submodule 初始化**

```bash
git submodule update --init thirdparty/wlroots thirdparty/xserver
```

## Task 8: 完整构建

- [ ] **Step 1: 后台跑完整 make（约 40 分钟）**

```bash
cd /data/share/wine-arm64
nohup make NATIVE_ARCH=arm64-v8a > .temp/proton-x11-build1.log 2>&1 &
```
等完成通知（不要 sleep 轮询）。失败则读日志尾部修断点（常见断点：Makefile 拼接错漏、display-libs 依赖缺失、wine-valve 重放漏文件），修复后重跑。

- [ ] **Step 2: 构建断言**

```bash
grep -E 'wineex11|winex11|opengl_winehua' .temp/proton-x11-build1.log | head
test -f build/wine-ohos-arm64-v8a/dlls/winex11.drv/winex11.so && echo X11-DRV-OK
```
Expected: winex11.so 产出且链接了 opengl_winehua 符号；wayland 路线产物照旧。

## Task 9: 真机双路线烟测 + A 类回归

设备 `192.168.1.5:44959`；部署遵循 rules/build-and-log.md（`bm uninstall` → `file send` → `bm install` 分步执行；改 wine 后首启点「立即应用→确定」）。

- [ ] **Step 1: 部署**

```bash
bash scripts/package.sh deploy 192.168.1.5:44959
```
（若脚本报 `[Fail]Not match`，手动分步：`hdc -t 192.168.1.5:44959 shell bm uninstall -n app.hackeris.winehua` → sleep → `file send` → `bm install`。）

- [ ] **Step 2: x11 路线（缺省）烟测**

```bash
hdc -t 192.168.1.5:44959 shell "aa start -a EntryAbility -b app.hackeris.winehua --ps winehua.program 'C:\windows\system32\cmd.exe'"
```
判据：x11 链出图（wlroots/Xwayland 链日志 + 画面非黑）；`hilog` 过滤 `display route` 确认 x11 生效。

- [ ] **Step 3: wayland incumbent 对照**

```bash
# want 参数钉路线, 重启会话
hdc -t 192.168.1.5:44959 shell "aa start -a EntryAbility -b app.hackeris.winehua --ps winehua.displayRoute wayland --ps winehua.program 'C:\windows\system32\cmd.exe'"
```
判据：wayland 路线行为与 proton 分支现状一致（incumbent 未破坏）。

- [ ] **Step 4: smoke core 套件**

```bash
python3 automation/smoke.py install && python3 automation/smoke.py run --suite core
```
判据：全绿（套件基线以 m0 的 x11 套件为准，wayland 用例按 incumbent 现状）。

- [ ] **Step 5: A 类回归（人工）**：modal 对话框、ARGB 透明、多窗口客户区、PC 拖拽 resize——逐项真机操作确认，异常则回 Task 6/7 定位。

## Task 10: 从零 make 演练

- [ ] **Step 1: 干净演练（构建可复现原则）**

```bash
git -C /data/share/wine-arm64 stash list   # 确认无未提交
rm -rf build/wine-ohos-arm64-v8a build/.stamps/wine-arm64-v8a   # 仅清 wine 段; 全量演练用干净 clone 更佳
make NATIVE_ARCH=arm64-v8a > .temp/proton-x11-build-rebuild.log 2>&1
```
判据：全绿无人工干预。

## Task 11: 推送（需用户确认后执行）

- [ ] **Step 1: 向用户确认推送范围**（wine-valve、mesa 的 feature/proton-x11 + 主仓库 feature/proton-x11）
- [ ] **Step 2: submodule 先推（指针才有意义），再推主仓库**

```bash
git -C thirdparty/wine-valve push origin feature/proton-x11
git -C thirdparty/mesa push origin feature/proton-x11   # 若 Task 5 产生了 libxkbcommon 分支同样处理
git push -u origin feature/proton-x11
```

## Task 12: Steam 验收（决策 0005 卡点 B 口径）

- [ ] **Step 1: x11 路线安装并登录 Steam**（沿用 proton 分支 steam-win64 的安装剧本，`docs/steam-win64/STEAM_WIN64_HANDOFF_20260919.md` 环境套路）
- [ ] **Step 2: 四项口径判定**：原 vulkan-1.dll 保持原位 / 自检不反复下载 / CEF GPU 不进崩溃循环 / 界面实际操作有响应
- [ ] **Step 3: 三次冷启动**全部通过
- [ ] **Step 4: 结果落档** `docs/steam-win64/`（新增 PROTON_X11_<日期>.md，证据 + hilog 落盘）

## 回滚

- 层 1：submodule 各自 `git checkout --detach <基线 sha>`（Task 1 Step 3 快照）
- 层 2/3：主仓库 `git reset --hard fcc7db10`（proton 前沿）；分支删除即可
