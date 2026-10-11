import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';

const DOMAIN: number = 0x0000;
const STORE_NAME: string = 'display_route';
const KEY_ROUTE: string = 'route';
export const ROUTE_WAYLAND: string = 'wayland';
export const ROUTE_X11: string = 'x11';
// 缺省 x11 (2026-10-10 用户拍板: x11 为当前主线, 默认即 x11 方便手工随时测试)
const DEFAULT_ROUTE: string = ROUTE_X11;

// 显示路线裁决 (wayland=原生路线对照 / x11=主线): 三级优先 —
// ① want 参数 winehua.displayRoute (内存覆盖, 最高优先, smoke/自动化钉档位用)
// ② 设置页「显示路线（实验）」持久化选择 (2026-10-11 起, 落 preferences)
// ③ 缺省 x11。
// 原「不持久化」约束 (spec 2026-10-03 §2.2) 被 ② 取代: 选择在设置页可见
// (非隐性僵尸态), 且缺省已是 x11。生效时机 = 冷启动解析一次 (EntryAbility),
// 引擎"重启 Wine"等应用内会话操作不重置。
// 消费点白名单 (spec 2026-10-03 §2.2): DesktopWindow surface 分发 / 输入
// 分发 / native env 汇集点 (经 NAPI 镜像) / 窗口装饰形态 (任务 #129 方向①:
// 顶条与系统装饰只在 x11 形态渲染, 判据单点 = FusionWindowManager.stripPxOf,
// WWA decor 分支同理 —— wayland incumbent 行为不变是硬约束, 装饰必须
// route 分叉)。新增消费点先改本注释并给单点判据, 再加代码。
export class DisplayRouteService {
  private static instance: DisplayRouteService | null = null;

  static getInstance(): DisplayRouteService {
    if (!DisplayRouteService.instance) {
      DisplayRouteService.instance = new DisplayRouteService();
    }
    return DisplayRouteService.instance;
  }

  private route: string = DEFAULT_ROUTE;      // 已应用值 (EntryAbility 冷启动裁决后写)
  private preferred: string = DEFAULT_ROUTE;  // 持久化的设置页选择
  private store: preferences.Preferences | null = null;

  init(ctx: common.Context): void {
    if (this.store) {
      return;
    }
    try {
      this.store = preferences.getPreferencesSync(ctx, { name: STORE_NAME });
      const v = this.store.getSync(KEY_ROUTE, DEFAULT_ROUTE) as string;
      if (v === ROUTE_WAYLAND || v === ROUTE_X11) {
        this.preferred = v;
      }
    } catch (e) {
      hilog.error(DOMAIN, 'wine', 'display route load fail: %{public}s', JSON.stringify(e));
    }
  }

  // 设置页选择: 落盘持久化, 冷启动生效 (本会话已应用的 route 不变)
  setPreferred(v: string): void {
    if (v !== ROUTE_WAYLAND && v !== ROUTE_X11) {
      hilog.warn(DOMAIN, 'wine', 'display route preferred ignored: %{public}s', v);
      return;
    }
    this.preferred = v;
    if (!this.store) {
      hilog.warn(DOMAIN, 'wine', 'display route persist skipped (no store)');
      return;
    }
    try {
      this.store.putSync(KEY_ROUTE, this.preferred);
      this.store.flush();
      hilog.info(DOMAIN, 'wine', 'display route preferred set: %{public}s', v);
    } catch (e) {
      hilog.error(DOMAIN, 'wine', 'display route persist fail: %{public}s', JSON.stringify(e));
    }
  }

  preferredRoute(): string {
    return this.preferred;
  }

  setOverrideMode(v: string): void {
    if (v === ROUTE_WAYLAND || v === ROUTE_X11) {
      this.route = v;
      hilog.info(DOMAIN, 'wine', 'display route override set: %{public}s', v);
    } else {
      hilog.warn(DOMAIN, 'wine', 'display route override ignored: %{public}s', v);
    }
  }

  isX11(): boolean {
    return this.route === ROUTE_X11;
  }

  routeName(): string {
    return this.route;
  }
}
