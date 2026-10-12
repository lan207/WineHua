/* xim_bridge.c — XIM 桥主进程侧 (通道客户端, XIM spec §3 NCP 承载)。
 *
 * 架构 (X1 实测修正, 2026-10-07): app 主进程 XOpenDisplay 挂起不返回 (X
 * socket 对主进程 mount namespace 不可达, 提交 1392d60), XIM server 跑在
 * NCP 子进程 (display/ncp/xim_server_child.cpp, 与 Xwayland 同 namespace,
 * 连接面已证)。本文件只管主进程侧通道:
 *   xim_bridge_channel_init() — socketpair, 子端交 spawn 传给子进程
 *   xim_bridge_send_text()    — drain 线程转投 commit 请求
 * 通道协议: {magic u32 = 0x57485349 ('WHSI'), len u32, utf8 bytes}
 */
#include "xim_bridge.h"

#include <pthread.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <sys/socket.h>
#include <unistd.h>

#include <hilog/log.h>

#define TAG "xim-bridge"
#define OHLOG(...) OH_LOG_INFO(LOG_APP, __VA_ARGS__)
#define OHERR(...) OH_LOG_ERROR(LOG_APP, __VA_ARGS__)

#define XIM_CHAN_MAGIC 0x57485349u

static int g_chan_fd = -1;      /* 主端; 子端所有权随 spawn 转移 */
static pthread_mutex_t g_chan_mutex = PTHREAD_MUTEX_INITIALIZER;

int xim_bridge_channel_init(void)
{
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0)
    {
        OHERR("socketpair failed errno=%{public}d", errno);
        return -1;
    }
    g_chan_fd = sv[0];
    OHLOG("channel paired main_fd=%{public}d child_fd=%{public}d", sv[0], sv[1]);
    return sv[1]; /* 调用方 (spawn) 持有并转移所有权 */
}

/* 全量写: MSG_NOSIGNAL + 短写/EINTR 循环。
 * MSG_NOSIGNAL 是硬需求 (2026-10-13 加固): 对端 (XIM 子进程) 已死时, 裸
 * write 会发 SIGPIPE 把**主进程直接写死** (默认信号动作, cppcrash —— 表现
 * 是"用户打字时应用闪退"); 带上它以 EPIPE 失败返回即可。消息小且互斥串行,
 * 不引入 NONBLOCK/队列 —— 失败即丢本次 commit 并报错。 */
static int write_all(int fd, const void *buf, size_t len)
{
    const uint8_t *p = (const uint8_t *)buf;
    while (len > 0)
    {
        ssize_t n = send(fd, p, len, MSG_NOSIGNAL);
        if (n < 0)
        {
            if (errno == EINTR)
                continue;
            return -1;
        }
        p += n;
        len -= (size_t)n;
    }
    return 0;
}

int xim_bridge_send_text(const char *utf8)
{
    if (!utf8 || g_chan_fd < 0)
        return -1;
    size_t len = strlen(utf8);
    if (len == 0 || len > 64 * 1024)
        return -1;

    uint32_t hdr[2] = {XIM_CHAN_MAGIC, (uint32_t)len};
    pthread_mutex_lock(&g_chan_mutex);
    int ok = write_all(g_chan_fd, hdr, sizeof(hdr)) == 0 &&
             write_all(g_chan_fd, utf8, len) == 0;
    pthread_mutex_unlock(&g_chan_mutex);
    if (!ok)
    {
        OHERR("send failed errno=%{public}d (peer gone? EPIPE=32)", errno);
        return -1;
    }
    return 0;
}
