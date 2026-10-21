#include "frame_composer.h"

#include "desktop_compositor.h"
#include "frame_pipeline.h"
#include "common/perf_utils.h"
#include "toplevel_manager.h"

#include <hilog/log.h>

#undef LOG_DOMAIN
#undef LOG_TAG
#define LOG_DOMAIN 0x0000
#define LOG_TAG "WL_Server"

// ============================================================================
// DesktopRootFrameComposer: Desktop root 帧整屏合成
// (原 DesktopCompositor::TakeToplevelFrame 的 desktop 分支, 逐行等价)
//
// 阶段拆分 (重构第 2A 步, 纯结构拆分行为平价): 桌面分支的"锁内规划 / 锁外
// 绘制"两阶段在 frame_pipeline.{h,cpp} — FramePlanner 锁内按原内联段顺序
// 执行 (dirty 门控 → 全屏仲裁 → 覆盖检测 → 直传判定 → 签名/基底 → damage R
// → 基底落盘 → 快照) 产出 FramePlan, FrameBlitter 锁外纯像素消费。锁边界/
// 计时点/日志门控与原单函数实现逐段对应。
// ============================================================================
bool DesktopRootFrameComposer::Compose(uint32_t id, std::vector<uint8_t>& out,
                                       PresentedFrame& frame, bool frameTrace) {
    const auto takeStarted = TakeClock::now();
    auto lk = comp_.tmgr_.Lock();
    const auto lockAcquired = TakeClock::now();

    FramePlan plan;
    FramePlanner planner(comp_, frameTrace);
    const FramePlanOutcome outcome =
        planner.PlanDesktopLocked(id, takeStarted, lockAcquired, out, frame, plan);
    if (outcome != FramePlanOutcome::kCompose) {
        if (outcome != FramePlanOutcome::kNoFrame) frame.pixels = out.data();
        return outcome != FramePlanOutcome::kNoFrame;
    }
    lk.unlock();  // ── 锁到此为止, 以下 blit 不持锁 ──
    FrameBlitter blitter(frameTrace);
    blitter.Composite(id, takeStarted, lockAcquired, plan, out);
    frame.pixels = out.data();
    return true;
}

// ============================================================================
// WindowFrameComposer: PC 单窗口帧
// (原 DesktopCompositor::TakeWindowFrameLocked, 逐行等价)
//
// 窗口内层序 (阶段 3, 多窗口模式 — PC 窗口模式与 Pad 多窗口模式共用, 两者
// DisplayPolicy::desktop 均为 false): Root(窗口帧) < 内嵌客户区 Subsurface
// (窗口局部坐标, route=InlineClient) < ZC 层(最顶)。窗口间层序由系统合成器
// 保证, 不在此合成。Popup 类 subsurface (菜单/越界浮层) 不在本容器 — 走
// 伪 toplevel + 独立 OHOS 子窗口, 见 DisplayPolicy::RouteForSubsurface。
// ZC 层 (zcActive) 合成跳过 — GPU 内容由 renderer 自绘覆盖, CPU 帧保留 SHM
// 内容不抠除 (与 desktop 模式同语义: GPU 帧不透明时覆盖等价, fallback
// 窗口期显示旧内容比黑屏稳)。
// ============================================================================
bool WindowFrameComposer::Compose(uint32_t id, std::vector<uint8_t>& out,
                                  PresentedFrame& frame, bool frameTrace) {
    // 全程持 tmgr 锁 (RAII, 出函数解锁): 本路径直接消费共享层 — layer.sub
    // 指向 subsurfaceLayers_ 元素 (BuildWindowLayerListLocked), blit 会就地
    // 写其 opaque/opaqueCheckedSerial 缓存, st/st->Pixels()/ClearDirty 亦为
    // 锁内契约 (见 CompositorLayer 注释)。无锁时与 WL_Server 线程的
    // UpsertSubsurfaceLayer (持锁; 首次 push_back 扩容 / 更新 move 换 pixels
    // 缓冲) 并发 → layer.sub->pixels 悬垂 → 渲染线程 SIGSEGV (Pad 实测:
    // 内嵌客户区 smoke 跑 ~25s 必崩, cppcrash tid=渲染线程)。按类分流前
    // 窗口内层列表恒空 (PC 模式 subsurface 全转 popup), 该缺陷未暴露。
    // 注: desktop 路径的"锁内规划/锁外绘制"之所以安全, 是因为 FramePlan 已
    // 快照像素; 本路径无快照阶段, 故 blit 必须留在锁内 (窗口内层数据量小)。
    auto lk = comp_.tmgr_.Lock();
    auto* st = comp_.tmgr_.FindToplevelLocked(id);
    if (!st || !st->IsDirty()) return false;
    int winW = st->Width();
    int winH = st->Height();
    if (winW <= 0 || winH <= 0) return false;
    static uint32_t diagN = 0;  // 渲染线程单线程调用 (见上方锁契约注释)
    /*
     * 全屏窗口的帧尺寸取客户区内容尺寸: client subsurface 承载画面时父表面
     * 只有一次占位提交 (见 ToplevelManager::SyncFullscreenContentSizeLocked),
     * 帧停在窗口尺寸会让画面贴在帧左上角。w_/h_ (窗口尺寸) 保持不动 — 输入
     * 坐标逆映射等消费方仍按屏幕基准工作。
     */
    if (st->IsFullscreen()) {
        const int cw = st->ClientContentW();
        const int ch = st->ClientContentH();
        if (cw > 0 && ch > 0 && (cw < winW || ch < winH)) {
            winW = cw;
            winH = ch;
        }
    }

    const auto layers = comp_.BuildWindowLayerListLocked(id, winW, winH);
    // 帧基底: 尺寸一致时以窗口基底起手 (保留 GDI 装饰内容); 不一致时说明
    // 帧尺寸已跟随客户区内容 (全屏窗口, 见 SyncFullscreenContentSizeLocked),
    // 旧基底的行跨距与新尺寸不符 — 直接重建空白基底, 同时省掉每帧把 6.5MB
    // 窗口基底拷进来再丢弃的无效拷贝。全屏窗口无装饰, 占位基底本也只有 GDI
    // 装饰内容, 丢弃无副作用。
    const size_t needSz = static_cast<size_t>(winW) * winH * 4;
    if (st->Pixels().size() == needSz) {
        out = st->Pixels();
    } else {
        out.assign(needSz, 0);
    }
    for (const auto& layer : layers) {
        switch (layer.type) {
            case CompositorLayer::Type::Root:
                break;  // 基底已在 out = st->pixels 拷贝
            case CompositorLayer::Type::Toplevel:
                break;  // 窗口内 ZC 整窗口层: GPU 自绘, CPU 帧跳过
            case CompositorLayer::Type::Subsurface:
                if (layer.ShouldSkipCpu()) {
                    // 跳过原因诊断 (每 300 脏轮一条): 区分不可见 vs ZC —
                    // 两者都产出全黑 CPU 帧, 表现同为"游戏在跑屏幕全黑"
                    if (diagN % 300 == 0)
                        OH_LOG_INFO(LOG_APP, "[MW-COMP] skip sub vis=%{public}d zc=%{public}d win=%{public}dx%{public}d",
                                    layer.visible ? 1 : 0, layer.zcActive ? 1 : 0, winW, winH);
                    break;
                }
                FrameBlitter::BlitWindowSubsurface(layer, winW, winH, out);
                break;
        }
    }
    if (diagN % 300 == 0) {
        OH_LOG_INFO(LOG_APP, "[MW-COMP] tl=%{public}u layers=%{public}zu fmt=%{public}u min=%{public}d bg=%{public}d",
                    id, layers.size(), st->ShmFormat(),
                    st->IsMinimized() ? 1 : 0, st->IsBackground() ? 1 : 0);
        // 源/目标采样: 定位黑帧产生点 — 源层像素本身黑 (wine 侧) vs blit
        // 几何/混合把它变黑 (合成侧)。带 shmFormat 与 viewport 显示尺寸。
        for (const auto& layer : layers) {
            if (layer.type != CompositorLayer::Type::Subsurface || !layer.sub) continue;
            const auto& spx = layer.sub->pixels;
            const size_t total = spx.size() / 4;
            if (total == 0) {
                OH_LOG_INFO(LOG_APP, "[MW-COMP-SRC] sub EMPTY size=%{public}zu", spx.size());
                break;
            }
            const uint8_t* mid = &spx[(total / 2) * 4];
            const int dispW = DisplaySizeAfterViewport(layer.sub->vpDstW, layer.sub->w);
            const int dispH = DisplaySizeAfterViewport(layer.sub->vpDstH, layer.sub->h);
            OH_LOG_INFO(LOG_APP, "[MW-COMP-SRC] sub %{public}dx%{public}d fmt=%{public}u disp=%{public}dx%{public}d at(%{public}d,%{public}d) midRGBA=(%{public}u,%{public}u,%{public}u,%{public}u)",
                        layer.sub->w, layer.sub->h, layer.sub->shmFormat, dispW, dispH,
                        layer.x, layer.y, mid[0], mid[1], mid[2], mid[3]);
            break;
        }
        if (out.size() >= 8) {
            const uint8_t* m = &out[out.size() / 2 - 4];
            OH_LOG_INFO(LOG_APP, "[MW-COMP-DST] out %{public}dx%{public}d midRGBA=(%{public}u,%{public}u,%{public}u,%{public}u)",
                        winW, winH, m[0], m[1], m[2], m[3]);
        }
    }
    ++diagN;
    // 帧交付契约: PC 窗口帧 — 窗口局部空间, buffer = 内容 = 窗口尺寸
    frame.kind = PresentedFrame::Kind::Composed;
    frame.baseSpace = PresentedFrame::BaseSpace::Window;
    frame.w = winW;
    frame.h = winH;
    frame.contentW = winW;
    frame.contentH = winH;
    frame.opaque = (st->ShmFormat() != 0);
    frame.pixels = out.data();
    st->ClearDirty();
    lk.unlock();  // ── 锁到此为止, 以下日志/返回不持锁 ──
    if (frameTrace) {
        OH_LOG_INFO(LOG_APP, "[MW-TAKE] toplevel #%{public}u frame %{public}dx%{public}d px=%{public}zu",
                    id, frame.w, frame.h, out.size());
    }
    return true;
}
