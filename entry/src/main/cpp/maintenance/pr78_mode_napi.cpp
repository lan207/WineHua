// Task-only helper: executable bits may change only on owned staged files.
#include <napi/native_api.h>
#include <fcntl.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string>

static bool MakeStagedExecutable(const std::string &relative)
{
    const char *base = "/data/storage/el2/base/files/.pr78-runtime-stage/wine";
    if (relative.empty() || relative.size() >= 1024 || relative.front() == '/' ||
        relative.find('\\') != std::string::npos || relative.find(':') != std::string::npos ||
        relative.find('\0') != std::string::npos) return false;
    size_t cursor = 0;
    while (cursor < relative.size()) {
        size_t end = relative.find('/', cursor);
        if (end == std::string::npos) end = relative.size();
        const std::string part = relative.substr(cursor, end - cursor);
        if (part.empty() || part == "." || part == "..") return false;
        cursor = end + 1;
    }
    char realFiles[PATH_MAX], realBase[PATH_MAX], realTarget[PATH_MAX];
    struct stat baseInfo;
    if (lstat(base, &baseInfo) != 0 || !S_ISDIR(baseInfo.st_mode) || S_ISLNK(baseInfo.st_mode) ||
        !realpath("/data/storage/el2/base/files", realFiles) || !realpath(base, realBase) ||
        std::string(realBase) != std::string(realFiles) + "/.pr78-runtime-stage/wine" ||
        !realpath((std::string(base) + "/" + relative).c_str(), realTarget)) return false;
    const std::string prefix = std::string(realBase) + "/";
    if (std::string(realTarget).compare(0, prefix.size(), prefix) != 0) return false;
    const int fd = open(realTarget, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return false;
    struct stat info;
    const bool allowed = fstat(fd, &info) == 0 && S_ISREG(info.st_mode) &&
                         info.st_uid == getuid() && info.st_nlink == 1;
    const bool result = allowed && fchmod(fd, 0755) == 0;
    close(fd);
    return result;
}

static napi_value MakeExecutable(napi_env env, napi_callback_info callback)
{
    napi_value arg, result;
    size_t count = 1, length = 0;
    bool ok = false;
    if (napi_get_cb_info(env, callback, &count, &arg, nullptr, nullptr) == napi_ok && count == 1 &&
        napi_get_value_string_utf8(env, arg, nullptr, 0, &length) == napi_ok && length > 0 && length < 1024) {
        char value[1024];
        size_t copied = 0;
        if (napi_get_value_string_utf8(env, arg, value, sizeof(value), &copied) == napi_ok && copied == length)
            ok = MakeStagedExecutable(std::string(value, copied));
    }
    napi_get_boolean(env, ok, &result);
    return result;
}

static napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor property = {"makeExecutable", nullptr, MakeExecutable, nullptr, nullptr, nullptr, napi_default, nullptr};
    napi_define_properties(env, exports, 1, &property);
    return exports;
}

static napi_module module = {1, 0, nullptr, Init, "pr78_maintenance", nullptr, {0}};
extern "C" __attribute__((constructor)) void RegisterPr78Maintenance() { napi_module_register(&module); }
