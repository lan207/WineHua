# Submodule 可维护性专项报告

> 更新：2026-08-01（重新梳理，同步当前落地状态）
> 复核：2026-09-24（D/E 落地状态、符号名与行号引用按当前代码重新核对；基线 commit 数与文件级改动量按当前 submodule 重算）
> 审计：2026-10-14（新增 §七 定制必要性审计：221 笔定制判定、loader/图形平台层改动的场景归因、可删除面与收口顺序）
> 初版：2026-07-31，评审时基于 `feature/render-element-completeness`（已合入 master，PR #47）
> 目的：作为分支评审（长期可维护性维度）的依据文档。记录各 submodule 与上游的合并风险现状、改进路线图与验收标准。
> 关联文档：[PHASE2_DXVK_STATUS_MEMO.md](../archive/PHASE2_DXVK_STATUS_MEMO.md) / [0002-d3d-backend-profiles.md](../decisions/0002-d3d-backend-profiles.md) / [CODE_IMPROVEMENT_PLAN.md](../archive/CODE_IMPROVEMENT_PLAN.md)

---

## 0. 落地状态速览（2026-08-01）

| 改进项 | 优先级 | 状态 | 说明 |
|--------|--------|------|------|
| C 基线锁定 | P1 | ✅ 已落地 | 基线快照 + 重算命令入本文档 §1.1；`scripts/setup-upstream-remotes.sh` 随仓库分发（commit `a753d15`）；6 个 fork 全部可追溯；幽灵分支已清理（18 个） |
| D dxvk 双轨 | P1 | ✅ 已落地 | 两条通道都在 `.gitmodules` 声明并进 master：`thirdparty/dxvk`（branch `dxvk-legacy-1.10.3`）与 `thirdparty/dxvk-modern`（branch `dxvk-modern-2.6`） |
| B 补丁清单 | P0 | ✅ 已落地 | `docs/customization/` 清单完成（2026-08-01 起，2026-09-25 迁入并增补 dxvk-modern 等），见 §2.4 |
| H CI submodule job | P0 | ⏳ 部分 | build.yml 仍只有 build/release 两个 job；已有的检查是「嵌套 submodule 是否完整」（`submodules: recursive` + dxvk/vkd3d 的 `submodule status`），缺的是「submodule 的提交有没有推到它自己的远程」这项 |
| E Profile 单一数据源 | P0 | ✅ 已落地 | 收口在 `entry/src/main/cpp/wine/env_profiles.cpp`（commit `f3370b0`，重构第 3 步）；未建 `shadow_profiles.h` |
| A 物理隔离 | P0 | ⏳ 未开始 | `vkr_winehua_shadow.c` 未建 |
| G 诊断分离 | P1 | ⏳ 未开始 | `vkr_winehua_perf.h` 未建 |
| I known-regressions | P1 | ⏳ 未开始 | `scripts/qa/` 未建 |
| F env var 目录 | P1 | ⏳ 未开始 | `docs/ENV_VAR_CATALOG.md` 未建 |
| J smoke 治理 | P2 | ⏳ 部分 | 主仓库的回归设施已按 v2 方案重建（用例目录化 + 载荷独立通道，见 [../engineering/testing-design.md](../engineering/testing-design.md)）；wine fork 里的 `programs/winehua_d3d11_smoke/main.c` **仍是 5869 行单文件**，未拆 |

---

## 一、总览：重合并风险矩阵

合并成本 = 侵入深度 × 上游活跃度 × 与我们基线的差距。

| Submodule | 上游基线 | 侵入模式 | 新增文件 | 合并方向 | 风险 |
|-----------|---------|---------|---------|---------|------|
| virglrenderer | freedesktop `main` | **深嵌**：`vkr_device_memory.c` +2464（37 处 winehua 引用、`#ifdef __OHOS__`）；`vkr_queue.c` +1190（数十个 `vkr_ohos_perf_*` atomic） | 少 | 我们合上游（上行） | 🔴 高 |
| mesa | **OpenHarmony mesa**（tag `OpenHarmony-v6.0-Beta1`），不是 mesa main | 中：`vn_ring.c` +423，**512 槽 perf 数组直接嵌进 `struct vn_ring` 热路径**；`vn_renderer_vtest.c` +393 为新文件（好模式） | 部分 | 我们合上游（上行） | 🔴 高 |
| dxvk | doitsujin `v1.10.3` tag（**上游死线**） | 深嵌：`dxvk_context.cpp` +1827、`dxbc_compiler.cpp` +506；已有独立层先例：`dxvk_winehua_trace.h` +508、`d3d11_bc.cpp` +203 | 6 个（含 `WINEHUA_FORK.md`） | **上游 backport 进来（下行）** | 🟡 中-高 |
| wine | wine `master` | **良好**：改动几乎全是新增文件（smoke 程序、`wineohos.drv`、`mciqtz32`），修改上游文件极少 | 多 | 我们合上游（上行） | 🟢 低 |
| box64 | ptitSeb `main` | **良好**：新增文件为主（`musl_fts.c` +1255、`musl_obstack.c` +378），修改集中在 `wrappedlibc` 系列函数包装 | 少 | 我们合上游（上行） | 🟢 低 |
| libepoxy | anholt mirror `master` | 极浅：仅 1 个独有 commit（`gl-dev` 已随上游演进，无 fork 内容） | 0 | 我们合上游（上行） | 🟢 极低 |

**关键认知**：

1. mesa 的"上游"是 OpenHarmony 官方 mesa 分支（`.gitmodules` 中 `libdrm.branch = OpenHarmony-6.0-Beta1` 印证 OH 版本体系），基线取 OH 发布 tag，与 mesa 主线无关。
2. dxvk 是唯一"下行合并"（上游 → 我们）：v1.10.3 已冻结，无新修复可拉，fork 处于"稳定但停滞"状态；未来切 2.x 时 6147 行 WineHua 改动是**重写不是合并**。
3. virglrenderer / mesa 上游活跃 → 深嵌改动每合一次都是人工手术，是本分支最大负债。
4. wine / box64 侵入度虽低，但改动量在持续增长（wine 155 个文件 +24045/-343 行），新增文件仍需逐个确认与上游无命名冲突。

---

## 二、Fork/Upstream 重合并

### 2.1 上游识别与基线锁定（改进 C，P1）✅ 已落地

| Submodule | 上游仓库/分支 | 基线记录（当前快照） | 合并节奏建议 |
|-----------|--------------|---------------------|-------------|
| virglrenderer | freedesktop/virglrenderer `main` | merge-base `8cb58e478`（2026-06-10） | **每季度尝试一次**，落后超两个大版本不可收拾 |
| mesa | OpenHarmony mesa（OH 发布体系） | tag `OpenHarmony-v6.0-Beta1`（merge-base e5d8c3f2，2025-06-13） | 跟随 OH 发布节奏，记录 OH 的升级周期 |
| wine | wine `master` | merge-base `13289668fd1`（2026-06-07，winehua 独有 118 commit） | 每次合 wine 时**先合 WineHua 侧新文件**（与上游无冲突，先落地减少 diff 堆积），再处理修改文件 |
| box64 | ptitSeb/box64 `main` | merge-base `8f445d9a0`（2026-06-12，winehua 独有 15 commit） | 跟随 ptitSeb 发布节奏（ohos 兼容补丁多为新文件，冲突面小） |
| dxvk | doitsujin/dxvk `v1.10.3` | tag `v1.10.3`（2022-08-02，winehua 独有 33 commit） | 无需节奏；每次 backport 上游 2.x bugfix 记录来源 commit |
| libepoxy | anholt/libepoxy `master` | merge-base `d1f952c45`（2026-04-03，winehua 独有 1 commit） | 贴上游头，可随 wine 合并顺带更新 |

**基线为派生数据（merge-base 可随时重算），本表只记录当前快照**：每次合并/升级后更新。升级本身是项目级事件（涉及构建 + 回归验证），不是 git 操作。重算命令：

```bash
MB=$(git -C thirdparty/<name> merge-base HEAD upstream/<branch>)
git -C thirdparty/<name> log -1 --format="%h %ad %s" --date=short $MB
git -C thirdparty/<name> rev-list --count $MB..HEAD   # winehua 独有 commit 数
```

上游 remote 用 `./scripts/setup-upstream-remotes.sh` 配置（新 clone 环境必跑，URL 与本表一致；mesa 上游为 gitee，受限网络下可能无法 fetch，此时用本地 tag 离线追溯）。

### 2.2 侵入度量化（2026-09-24 重算，相对 §2.1 基线）

- **virglrenderer**（+8942 行 / 53 文件，较初版 +6215/34 增长）：
  - `vkr_device_memory.c`：上游 ~57 行 → +2464 行，37 处 winehua 引用，`#ifdef __OHOS__` 守卫
  - `vkr_queue.c`：+1190 行，文件顶部数十个 `vkr_ohos_perf_*` atomic 计数器
  - `vkr_command_buffer.c` +778 / `vkr_descriptor_set.c` +535 / `vkr_pipeline.c` +449 / `vkr_renderer.c` +346
- **mesa**（+2093 / 24 文件）：`vn_ring.c` +423（含 VN_RING_PERF_COMMAND_TYPE_COUNT 512 槽数组嵌入 ring 热路径结构体）、`vn_queue.c` +413、`vn_renderer_vtest.c` +393（**新文件，好模式**）、`virgl_vtest_socket.c` +203、`vn_device_memory.c` +162
- **dxvk**（+6147 / 66 文件，按 `v1.10.3` tag 计算）：仅 6 个新文件，核心改动深嵌 `dxvk_context.cpp` +1827、`dxvk_winehua_trace.h` +508、`dxbc_compiler.cpp` +506、`d3d11_context.cpp` +386、`dxvk_shader.cpp` +251
- **wine**（+24045 / 155 文件，较初版 +8411/24 大幅增长）：几乎全部是**新增文件**——`programs/winehua_d3d11_smoke/main.c` +5869、`dlls/wineohos.drv/`（ohos.c +2366、tsf.h +2079、ohos_midi.c +840）、`dlls/mciqtz32/`（minimp3.h +1865、mciqtz_waveout.c +639）；修改上游文件极少
- **box64**（+3775 / 38 文件）：新增为主——`musl_fts.c` +1255、`musl_obstack.c` +378（OHOS musl 兼容补丁）；修改集中在 `wrappedlibc`/`wrappedlibdl` 函数包装（-1172 删除主要来自清理调试残留）
- **libepoxy**：独有 1 commit，可忽略

### 2.3 物理隔离：新代码进新文件（改进 A，P0）⏳ 未开始

缓解合并冲突的唯一有效机制是**物理隔离**。dxvk 已证明可行（`dxvk_winehua_trace.h`、`d3d11_bc.cpp` 独立成文件），virglrenderer 未做到。

**目标结构**（不改行为，纯结构重构，A/B 构建验证）：

```
src/venus/vkr_winehua_shadow.c/.h   ← shadow alloc / dirty-tracking / coverage-sort / msync 全部移入
vkr_device_memory.c                 ← 每文件仅保留 ≤3 处 hook：
    #ifdef __OHOS__
    vkr_winehua_shadow_init_for_allocation(mem, alloc_info);
    #endif
src/venus/vkr_winehua_perf.h        ← 性能计数器独立层，产品代码只留 VKR_PERF_INC(name)
```

**mesa 必须做**：`vn_ring.c` 的 512 槽 perf 数组移出热路径结构体（当前每个 ring 都背着 512×3 的数组，且合并冲突噪音大）。

**试点顺序**：`vkr_device_memory.c` → `vn_ring.c` → `vkr_queue.c`。

**验收标准**：上游升级时，每个文件只需确认 1-3 个 hook 位置，冲突从"手术级"降为"核对级"。

### 2.4 补丁清单：patch manifest（改进 B，P0）✅ 已落地（2026-08-01）

合并冲突时最痛苦的是不知道"这个 hunk 对应我们的哪个改动、为什么存在、丢了它的后果"。

**已完成**：`docs/customization/` 下的模块清单（virglrenderer / mesa / wine / box64 / dxvk-legacy / dxvk-modern / libepoxy / build-adaptations，另有一篇总览 README），每篇按以下结构记录：

```
docs/customization/<submodule>.md
├── 变更总览：修改 vs 新增文件的分类统计
├── 变更明细：文件:函数 | 为什么存在 | 依赖的上游行为 | 不变式 | 验证方法
└── 合并注意点（冲突敏感度分级 / 上游变化检查要点 / CRLF 噪音提示）
```

**不变式是清单的灵魂**——合并时只要不变式不破坏，实现怎么改都可以。清单同时是新人入职文档与合并操作手册。

**梳理中沉淀的关键事实**（合并时直接引用）：
- mesa / box64 的大部分变更为运行时 env opt-in 或 `#ifdef __OHOS__` 守卫，默认关闭时行为与上游一致——合并冲突时最容易误删的部分
- virglrenderer 的 meson.build / vrend_winsys.c diff 大部分是 **CRLF 假改动**（真实功能改动仅 15-17 行），合并用 `git diff -w`
- wine 的 45 个修改文件中 22 个是纯追加（低风险重放），冲突敏感的是 23 个含删除行的
- dxvk 的 ABI 契约点（bool spec 冻结、combined-sampler、bcdec.h 相对包含路径）是 2.x 重写时的先确认项

### 2.5 dxvk 双轨战略（改进 D，P1）✅ 已落地

- 当前 v1.10.3 是上游死线，fork 稳定但停滞；`docs/decisions/0002-d3d-backend-profiles.md` 已评估 920 可试点 2.x，但 2.x 与 1.10.3 结构差异巨大，**现有改动是重写不是迁移**。
- 两条通道（均在 `.gitmodules` 声明、均已进 master）：
  - `thirdparty/dxvk`（branch `dxvk-legacy-1.10.3`）：legacy 产品分支，只收 cherry-pick 的上游 bugfix，每次记录来源 commit
  - `thirdparty/dxvk-modern`（branch `dxvk-modern-2.6`）：modern 通道，构建入口 `make dxvk-modern`（`scripts/build_dxvk_modern.sh`），按 `dxvk_modern_2_6` 档位消费（合并决策记录见 [PHASE2_DXVK_MERGE_REPORT.md](../archive/PHASE2_DXVK_MERGE_REPORT.md)）
- **禁止两条通道在同一分支共存**——那会把一次升级变成两次迁移。

---

## 三、持续迭代：降低每次改动的成本

### 3.1 Profile 映射单一数据源（改进 E，P0）✅ 已落地

**落地形式**（commit `f3370b0`）：guest 侧 profile→env 映射收口在 `entry/src/main/cpp/wine/env_profiles.cpp` / `env_profiles.h`，对外只有两个入口——`AppendStableDxvkEnv()` 与 `BuildSessionEnv(SessionEnvPolicy)`；spawn 点声明 `SessionEnvPolicy` 拿成品，不再各自追加策略行。收敛的是 guest 侧 env；host 侧渲染开关仍由 `napi_init.cpp:121` 的 `SetHostShadowProfile` 单独 setenv。

一致性靠**单一入口**保证：`env_profiles.cpp` 是唯一的会话 env 管线定义点。

### 3.2 Env Var 目录与 guest/host 握手（改进 F，P1）⏳ 未开始

- **现状**：约 30 个 env var 无 schema、无版本。fingerprint 已接入两处（`graphics_broker.cpp:1313,1356` 启动日志、`:1281` 运行中配置变更强制报错"App restart required"）——但它是 **host 侧自检**，解决不了"guest 侧 DXVK 收到的 env 与 host 侧配置漂移"（两侧由不同代码生成，各自算出各自的 hash，握手不上去）。
- **第一步（低成本）**：建 `docs/ENV_VAR_CATALOG.md`——全部 env var 表格：读取者（guest DXVK / host virglrenderer / box64 / 主仓库）、默认值、由哪个 profile 字段派生、引入版本。这张表本身就是升级手册。
- **第二步（中期）**：把 `VirglHostLaunchConfig.fingerprint` 升级为跨 IPC 握手：guest 侧把 DXVK 实际生效的 env 组合回传，host 对比期望值，不匹配打 `WL-ERR` 级错误而不是静默跑。

### 3.3 诊断与产品代码分离（改进 G，P1）⏳ 未开始

- **现状**：`vn_ring.c` 的 512 槽 perf 数组、`vkr_queue.c` 顶部数十个 `vkr_ohos_perf_*` atomic、`VKR_WINEHUA_UBO_TRACE_LIMIT 200000` 等 trace 常量全部嵌在产品热路径里。
- **问题**：读代码需跳过它们；perf 层 bug 可能污染产品路径；且它们出现在合并 diff 中增加冲突噪音（上游改热路径时 perf 行与逻辑行纠缠在同一个 hunk）。
- **方案**：独立 `*_winehua_perf.*` 文件 + 条件编译宏，产品代码只留零成本 `VKR_PERF_INC()` 调用（同改进 A）。

---

## 四、质量保证

### 4.1 现状盘点

| 项 | 状态 |
|----|------|
| CI 构建门禁 | ✅ `build.yml` 已有 `pull_request: branches: [master]` + push + tag + workflow_dispatch；gitlink 精确校验 step 已存在（`ci: verify exact submodule gitlinks before push`） |
| KNOWN_GOOD/UNKNOWN/REJECTED 分类系统 | ✅ STATUS_MEMO 机制，业界少见，**必须保留** |
| submodule 一致性检查入 CI | ❌ `scripts/check-submodules.sh` 只在本地跑 |
| 已知坑自动化回归 | ❌ 0x887a0004 / Crysis3 DllPath / steam_api64 SAFEFLAGS 依赖人工记忆 |
| Smoke 测试结构 | ⚠️ 单文件 5869 行（winehua_d3d11_smoke/main.c），无测试清单文档 |
| 基线冻结验证 | 🔄 进行中：automation 已重写为 smoke v2 设施（`automation/smoke.py`：build / push / run / check / install / devices / gate；套件在 `smoke/suites/`，判定器在 `automation/checks/`），KNOWN_GOOD 归档待建 |

### 4.2 CI submodule 门禁 job（改进 H，P0）⏳ 未开始

纯脚本，可立即落地：

```yaml
jobs:
  submodule-check:   # 快速 job，与 build 并行，PR/push 都跑
    steps:
      - checkout（recursive）
      - ./scripts/check-submodules.sh            # gitlink 可达性 + 指针一致性
      - 分支约定检查：每个 submodule 当前指针在
        .gitmodules 声明分支（wine=master, box64=main, virglrenderer=master,
        libepoxy=master, mesa=main, libdrm=OpenHarmony-6.0-Beta1,
        dxvk=dxvk-legacy-1.10.3, dxvk-modern=dxvk-modern-2.6）的远程历史中
      - submodule 工作树干净检查（无未提交改动）
```

这直接把 Maintainer 检查清单的"打回"条件（见 `.claude/rules/submodule-workflow.md`）变成机器判断。

### 4.3 已知坑回归脚本（改进 I，P1）⏳ 未开始

```
scripts/qa/known-regressions.sh
├── 01_env_protocol：验证 SPAWN\n 协议 env 注入生效（回归 0x887a0004）
├── 02_crysis_dllpath：启动 Crysis 3 → 断言无 0xC0000135
├── 03_safeflags：启动 steam_api64 目标 → 断言无 AV
└── 每次运行把 hilog 证据 + HAP hash 归档到带时间戳目录
```

配合 STATUS_MEMO 已立的"KNOWN_GOOD 归档签名 HAP"规则，落成脚本即流程闭环。

### 4.4 Smoke 测试治理（改进 J，P2）⏳ 未开始

5869 行单文件不要求立刻拆（拆动可能引入新 bug 且无功能收益），但定规则：**新测试进新文件**（按主题 present/shadow/format/sync），并在清单里记录"每个测试验证的不变式"——与补丁清单（2.4）呼应：**测试是补丁清单不变式的执行者**。

---

## 五、路线图与优先级（2026-08-01 更新，2026-09-24 复核）

| 阶段 | 动作 | 成本 | 解决 | 状态 |
|------|------|------|------|------|
| **已落地** | C：基线锁定（快照 + 脚本 + 分支清理） | 已完成 | 重合并可操作性 | ✅ 2026-07-31 |
| **已落地** | B：补丁清单 ×6 submodule | 已完成 | 重合并可操作性 | ✅ 2026-08-01 |
| **合并前** | H：CI submodule job | 低（纯 yml + 脚本） | 质量门禁 | ⏳ |
| **已落地** | E：profile 单一数据源（收口到 `env_profiles.cpp`，`f3370b0`） | 已完成 | 迭代成本 | ✅ 2026-08-26 |
| **下个迭代** | I：known-regressions 脚本 | 中 | 回归 | ⏳ |
| **Q3** | A：物理隔离试点（vkr_device_memory → vkr_winehua_shadow.c，然后 vn_ring） | 中-高（不改行为，A/B 验证） | 重合并根治 | ⏳ |
| **已落地** | D：dxvk-modern 通道（`thirdparty/dxvk-modern`，branch `dxvk-modern-2.6`，已进 master） | 高 | dxvk 2.x 迁移 | ✅ 2026-08-20 |
| **长期** | C：合并节奏制度化（每季度） | 中 | 重合并可操作性 | ⏳ |

**顺序逻辑**：文档类先做（成本≈0、可立即合并、为后续重构提供语义锚点）；代码类按合并窗口排序——virglrenderer/mesa 上游一旦发新版本，物理隔离（A）的紧迫性从 Q3 提到当下。

---

## 六、证据索引

评审核对用，全部为本分支实际代码（2026-08-01 建立，2026-09-24 按当前 master 复核）：

- `scripts/setup-upstream-remotes.sh` — upstream remote 幂等配置（commit `a753d15`）
- `scripts/check-submodules.sh` — gitlink 可达性 + 指针一致性（本地脚本，未入 CI）
- `automation/smoke.py` — 回归设施 v2（build / push / run / check / install / devices / gate；套件 `smoke/suites/`，判定器 `automation/checks/`；`automation/README.md` 有完整用法），取代 v1 的 `run_regression.py` + `validate_frame.py`（v1 设施已由 commit `5d105c3` 拆除）
- `entry/src/main/cpp/bridge/napi_init.cpp:121-317` — `SetHostShadowProfile`（~200 行条件分支）
- `entry/src/main/cpp/wine/env_profiles.cpp` — profile→env 映射单一入口（`AppendStableDxvkEnv`、`BuildSessionEnv`）；原 `wine_launch.cpp:AppendStableDesktopDxvkEnv` 已随 `f3370b0` 迁移并删除
- `entry/src/main/cpp/wine/wine_launch.cpp` — `CopyFileIfNeeded`（mkstemp+fsync+rename 原子写，`:157`）、`EnsureWow64Files`（`:234`）
- `entry/src/main/cpp/graphics/graphics_broker.cpp:1313,1356` — fingerprint 启动日志（phone in-process / IPC NCP 各一条，另见 `:241` 线程内日志）；`:1281` — 配置变更强制校验（"App restart required"）
- `entry/src/main/cpp/graphics/virgl_host_config.h:26,30-34` — `fingerprint` 字段 + Validate/Fingerprint/Build 三函数
- `entry/src/main/cpp/graphics/virgl_child.cpp:477,502` — launch fingerprint 透传（`BuildVirglHostLaunchConfig` → 启动日志）
- 基线锚点（§2.1）：virglrenderer `8cb58e478` / mesa tag `OpenHarmony-v6.0-Beta1`（e5d8c3f2）/ wine `13289668fd1` / box64 `8f445d9a0` / dxvk tag `v1.10.3` / libepoxy `d1f952c45`
- `.gitmodules` — branch 约定：wine=master, box64=main, virglrenderer=master, libepoxy=master, mesa=main, libdrm=OpenHarmony-6.0-Beta1, dxvk=dxvk-legacy-1.10.3, dxvk-modern=dxvk-modern-2.6
- `.github/workflows/build.yml` — 已含 PR 触发 + gitlink 校验 step（`2c0d219`）
- `docs/decisions/0002-d3d-backend-profiles.md` — 设备能力矩阵（920 phone Vulkan 1.3.309 vs 910 tablet 1.2.275）

---

## 七、定制必要性审计（2026-10-14）

> 范围：master 当前引用的 7 个 fork（共 221 笔定制提交）与 17 个上游直接引用。
> 与 §2.4 补丁清单互补：补丁清单回答「改了什么、为什么」，本节回答「是否仍然必要、哪里可以收口、删除的边界在哪」。

### 7.1 底数

| 模块 | 定制提交 | 基线 | 说明 |
|---|---|---|---|
| wine | 115 | wine-11.10（merge-base `13289668fd1`，2026-06-07） | 上游已 11.17 |
| virglrenderer | 38 | upstream/main（2026-06-10） | |
| dxvk（legacy） | 33 | v1.10.3（上游死线） | |
| mesa | 16 | OpenHarmony-v6.0-Beta1 | 跟随 OH 发布节奏 |
| box64 | 15 | v0.4.3 | 另有一笔注释提交未进 master 指针（见 7.5 #2） |
| dxvk-modern | 3 | v2.6.2 | |
| libepoxy | 1 | 1.5.10 | |
| 17 个直接引用 | 0 | 全部上游 tag 原样 | 逐条 `tag@HEAD` 核验 |

- 全部 fork 的定制提交均已推送各自远程仓库。
- glib / gstreamer / pcre2 工作区的「未提交修改」为构建脚本补丁与自动生成副产物的正常应用态，非失控改动。

### 7.2 判定一：图形档位（profile）系统——临时措施长期化

**现状事实**：

- `entry/src/main/ets/service/WineEnvService.ets:322-328` 写死档位 `shadow-precise-dirty-ring-inline-upload-coverage-sort` 并忽略持久化值；注释自述为「[实验-设备验证]」，成因是 vkd3d（D3D12）缺提交前发布路径下的黑屏规避（上传堆常驻映射无 flush 时机），并给出恢复方法与治本方向「补提交前发布」。
- 宿主侧 `entry/src/main/cpp/bridge/napi_init.cpp:121-317`（`SetHostShadowProfile`）以约 200 行字符串匹配翻译 40 余个档位名；除生产写死使用的 1 个外，其余在仓库内无任何注入入口（ArkTS 与 cpp 全量检索核实）。
- guest 侧 `entry/src/main/cpp/wine/wine_env.cpp:186` 注入 `WINEHUA_PERF_PROFILE=shadow-precise` 契约；`env_profiles.cpp` 另有一层默认值逻辑；`DXVK_WINEHUA_PRECISE_SHADOW=1`、`VN_WINEHUA_STRONG_RING_BARRIER=1` 恒定注入。
- guest / host 两侧档位由不同代码生成、无一致性握手（§3.2 已记录）。

**判定**：一次标注规范的止血长期化——治本（vkd3d 提交前发布）悬空，临时写死成为常态；40 余个档位变体中仅 1 个有产品入口。此为当前维护成本最集中的单点（合并冲突面、阅读负担、字符串错位静默降级三类成本叠加）。

**收口顺序（顺序敏感）**：① 治本（vkd3d 补提交前发布）→ ② 恢复 .ets 的产品语义（其注释已写明恢复方法）→ ③ 删除无入口变体、档位选择结构化为表驱动 → ④ 恒定注入的开关逐个定性（A/B 结论已出者固化实现、删开关与另一分支）。

### 7.3 判定二：诊断/埋点框架存量（约 46 笔 / 约 9000 行插入）

**分布**：virglrenderer 17 笔（约 5000 行）、dxvk-legacy 15 笔（约 2300 行）、mesa 6 笔（约 1000 行）、wine 若干（Heaven 追踪 / Gate C / 探针类）。

**形态核实（两个事实）**：

- 抽查发现「diagnostic」提交中混有默认关闭的 opt-in 行为实验（如 `c0df6b51` 的「每 submit 代至多等一次」等待节流、`39344384` 的影子代际加锁序列化）——**删除前必须逐笔剥离行为部分**，不能按标题整批删。
- 代码体量主要来自打点支撑结构（计数、哈希、环形记录），删除复杂度在于拆共享框架。

**使用频率**：重型框架集中建于 2026-07 下旬～08 上旬（Heaven / Instancing 调试期）；此后无新增诊断提交，新问题排查（红警 2、企业微信黑窗）采用轻量打点方式。**判定为疑似休眠**，是否删除取决于 Heaven / Instancing 调试线是否仍在计划内（待决，见 7.8）。

### 7.4 loader 及图形平台层改动审查（场景归因）

对 `dlls/ntdll/loader.c`（+154）、`dlls/winevulkan/loader.c`（+38）、`dlls/win32u/opengl.c`（+39）等平台层改动逐一审查（相对 merge-base `13289668fd1`），结论按性质分四类：

| 改动 | 性质 | 结论 |
|---|---|---|
| DXVK/vkd3d overlay 搜索（`search_winehua_dxvk_overlay`，3 个 dll 名 + env 门控 + 失败回落） | 产品架构差异 | 上游/Proton 生态惯例是「装进 prefix」（Proton 借 per-game prefix 实现按游戏切版）；本项目为「共享 prefix + 按程序档位 + 应用内运行时」架构，装 prefix 不成立，进程级 overlay 是唯一解；实现已是最小形态 |
| overlay 位于 exe 目录**之前** | 有意语义覆盖 | 保证运行经验证的渲染链路（游戏自带 d3d11/dxgi 时仍用我们的版本）；打破 Windows「exe 目录第一」规则，**应确认为设计决定并补「游戏自带 DLL」场景验证** |
| exe 目录搜索恢复（`build_module` / `loader_init` 各一处从 NT 名反推） | 本项目移植偏差 | 「exe 目录优先」是上游完整维护的核心语义；本项目 OHOS 启动链（broker spawn、跳过 reexec）丢失了 load_path。上游同类问题的修法在入口传对路径，loader 内反推属兜底；同一逻辑两处重复，应抽 helper；根因（入口为何传 NULL）未查，登记技术债 |
| `default_load_path` 补搜 | 配套修复 | exe 目录恢复的配套（vulkan-1.dll 等系统依赖回落）；与上一条互相依赖，合并上游时需整体对待 |
| winevulkan swapchain 谎报 + 8 入口绕过 host 查询 | 平台场景差异 | 上游宿主有真 WSI（X11/Wayland），不存在此问题；本项目宿主为 Venus（无 WSI），自实现呈现链是同类平台（Winlator 的 vortekrenderer）的共同解法；责任边界闭环（win32u 在 host vkCreateDevice 前剥离该扩展） |
| `WINEHUA_EGL_LIBRARY_PATH` 覆盖 + 依赖预载 | 已有机制扩展 | 上游按标准系统路径加载 libEGL；本项目库为应用内私有路径。改动为库名可覆盖 + 预载，不涉搜索逻辑重写 |
| `dlls/winevulkan/loader.c` 中 `#if 1` 包裹 swapchain 分支 | 清理项 | 无意义的条件编译痕迹，应删除或改为真实开关 |

### 7.5 个体问题清单

| # | 项 | 状态/结论 |
|---|---|---|
| 1 | box64 指针不在 `.gitmodules` 声明分支（原钉在 feature 分支提交上） | **已修**（origin/main 已 fast-forward 到该提交，无分叉） |
| 2 | box64 `mallochook.c` 文件头注释与生产现状矛盾 | 注释已修正（直通实现 + 已知能力损失），提交 `e9300bc07` 已推远程；**master 指针未更新，去留待决**（7.8 #1） |
| 3 | wine `tools/makedep.c` 两处改动（原标 [待确认]） | **已核实**：install 规则去重跳过 dest 条目 + 断言前置打印上下文；动机为打包期 install 规则冲突。当前构建不经 make install，但删除有打包期回归风险且仅 12 行，**保留**（wine.md 已同步） |
| 4 | wine `unix_wgl.c` 同一修复提交两遍 | 注明即可（历史不改） |
| 5 | wine `is_window_managed` 三条未验证边界（tooltip / IME 候选窗 / 拖拽预览） | 验证清单 |
| 6 | wine `hlsl_codegen.c` half 支持是否与上游 vkd3d 重复 | 合并 11.17 时 diff（`unix_wgl.c` 已核实上游未修，保留） |
| 7 | box64 `rint` wrap 无背景说明 | 验证清单 |
| 8 | box64 `threads.c` `real_pthread_cleanup_push_defer` 裸调用（无 NULL 守卫） | 低概率路径，建议加守卫 |
| 9 | virglrenderer 上游注释被误截断（"mapped buffe"） | 合并时恢复 |
| 10 | glib / gstreamer / pcre2 工作区状态 | 正常态（见 7.1） |
| 11 | 测试程序未进产品包 | 已核实健康（`assemble.sh` 显式排除 + `from_wine` 载荷机制） |

### 7.6 对 §五 路线图的修正建议

1. 现有 A–J 均为「保留 + 整理」维度，缺「删除 / 收口」；建议增补 profile 收口（7.2）与诊断框架退役（7.3）两类，并把 7.7 的行动分级并入路线图。
2. 「物理隔离」（A）治标：hook 调用点仍留在上游文件中，上游改动时冲突依旧发生，只是冲突块变小；删除与收口才是让冲突消失的手段。
3. 「默认关闭 = 无成本」的隐含假设不成立：运行时零开销，但合并冲突面、阅读负担、构建时间三类成本仍在，判定休眠代码去留时应计入。
4. F 项（env 目录）升级为「开关生命周期管理」：引入 → 定论 → 固化实现 → 删开关；当前缺的不是目录，是退役机制。
5. 新增流程建议：止血类改动（如 7.2 的写死档位）需在集中位置登记治本待办，避免悬空。

### 7.7 行动分级

- **L1（低风险，可立即）**：box64 `e9300bc07` 去留决定并同步指针；补 submodule 检查脚本 / CI（指针在声明分支 + 已推送，即 §4.2 H 项——box64 事件证明其必要性）；7.5 涉及的文档更新（wine.md 已同步）。
- **L2（需设计方案）**：profile 治本 → 恢复产品语义 → 收口变体的完整链（7.2）；生产恒定注入开关逐个「固化或回退」。
- **L3（需确认前提）**：诊断框架删除（前提见 7.8 #2；执行时逐笔剥离 opt-in 行为）；7.5 验证清单项（#5 / #7 / #8）。
- **L4（合并窗口）**：`hlsl_codegen.c` half 上游核对（#6）、"mapped buffe" 注释恢复（#9）、loader 三块改动整体合并对待（7.4）。

### 7.8 待决事项

1. box64 注释提交 `e9300bc07`：加进 master 指针，或 revert。
2. 诊断框架（7.3）：Heaven / Instancing 调试线是否仍在计划内——决定整组休眠代码的去留。
3. profile 治本（vkd3d 提交前发布）是否排期——它决定 7.2 收口链的启动时点。
4. overlay 搜索顺位（7.4）确认为设计决定，并补「游戏自带 d3d11/dxgi」场景验证。
