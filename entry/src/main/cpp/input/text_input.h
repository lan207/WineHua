#pragma once
#include <wayland-server-core.h>
#include <cstdint>
#include <functional>
#include <mutex>
#include <unordered_map>

// zwp_text_input_manager_v3 / zwp_text_input_v3 compositor 侧实现。
//
// 职责:
//   - 注册 zwp_text_input_manager_v3 global (Wine 的 wayland_text_input.c 绑定)
//   - 接收 Wine 请求: enable/disable/set_cursor_rectangle/set_content_type/commit
//   - 主动发事件: enter/leave/preedit_string/commit_string/delete_surrounding_text/done
//   - 激活判定: keyboard enter 后 Wine enable+commit(0,0,0,0); 文本框聚焦时
//     Windows 应用调 SetIMECompositionRect → set_cursor_rectangle(非零) →
//     commit 时判定激活 → 回调通知 ArkTS 弹软键盘
//
// 事件注入与 seat 绑定参照 Seat/InputManager 模式; 状态用 mutex 保护
// (wayland dispatch 线程 vs ArkTS NAPI 注入线程)。

class TextInput {
public:
    using ActivateCb = std::function<void(bool active, int x, int y, int w, int h)>;

    static TextInput* GetInstance();

    void Register(wl_display* display);
    void Unregister();

    void SetActivateCallback(ActivateCb cb) { activateCb_ = std::move(cb); }

    // InputManager keyboard enter/leave → 同步 text-input enter/leave
    void OnKeyboardEnter(wl_resource* surface);
    void OnKeyboardLeave(wl_resource* surface);
    // surface 销毁 (wl_core surface_destroy 调): 清该 surface 的矩形记忆
    void ForgetSurface(wl_resource* surface);

    // ArkTS 桥接: 输入法文本注入 → Wine (UTF-8)
    void SendCommitString(const char* utf8);
    void SendPreeditString(const char* utf8, int32_t cursorBegin, int32_t cursorEnd);
    void SendDeleteSurrounding(uint32_t before, uint32_t after);

    // 软键盘被用户手动收起后重新武装激活边沿 (同窗内文本框重聚焦无 seat
    // 事件, activated 恒真则永不重弹; 见 text_input.cpp commit 注释)
    void RearmActivation();

    // -- 协议 impl (wayland dispatcher 调用) --
    static void manager_bind(wl_client* client, void* data, uint32_t version, uint32_t id);
    static void manager_destroy(wl_client* client, wl_resource* res);
    static void manager_get_text_input(wl_client* client, wl_resource* res, uint32_t id, wl_resource* seat);
    static void text_input_destroy(wl_client* client, wl_resource* res);
    static void text_input_enable(wl_client* client, wl_resource* res);
    static void text_input_disable(wl_client* client, wl_resource* res);
    static void text_input_set_surrounding_text(wl_client* client, wl_resource* res,
                                                const char* text, int32_t before, int32_t after);
    static void text_input_set_text_change_cause(wl_client* client, wl_resource* res, uint32_t cause);
    static void text_input_set_content_type(wl_client* client, wl_resource* res,
                                            uint32_t hint, uint32_t purpose);
    static void text_input_set_cursor_rectangle(wl_client* client, wl_resource* res,
                                                int32_t x, int32_t y, int32_t w, int32_t h);
    static void text_input_commit(wl_client* client, wl_resource* res);

private:
    struct State {
        wl_resource* res = nullptr;     // zwp_text_input_v3 资源
        wl_resource* surface = nullptr; // enter 的 surface (对应键盘焦点)
        bool enabled = false;
        bool activated = false;         // 已回调激活 (防重复)
        int32_t cursorX = 0, cursorY = 0, cursorW = 0, cursorH = 0;
    };

    TextInput() = default;
    void NotifyActivated(bool active);  // 统一收口激活/失活回调
    void ResetState();                  // enter 时重置 pending 状态

    // 每个 Wine 进程 (wl_client) 一个 zwp_text_input_v3 对象。多个 Wine 进程
    // (wineboot/explorer/用户程序) 各自 get_text_input, 单实例 state_.res 只存
    // 最后一个会导致 keyboard enter 发错对象 → 目标进程收不到 enter 不 enable。
    // OnKeyboardEnter 按 surface 所属 client 路由到对应对象。
    std::unordered_map<wl_client*, wl_resource*> textInputs_;

    // per-surface 最后一次非零光标矩形 (激活门回退用, 见 text_input.cpp
    // text_input_commit 注释)。wine enter 批次恒发 0,0,0,0, 重聚焦后不保证
    // 重发非零矩形; 记忆它使重聚焦激活不依赖应用 IME 链路。
    struct RectMemo {
        int32_t x = 0, y = 0, w = 0, h = 0;
    };
    std::unordered_map<wl_resource*, RectMemo> surfaceRects_;

    wl_global* global_ = nullptr;
    wl_display* display_ = nullptr;
    State state_;
    std::mutex mutex_;
    ActivateCb activateCb_;
    uint32_t serial_ = 0;
};
