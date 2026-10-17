#!/usr/bin/env python3
"""Compile production launch parsing and environment policy without device APIs."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / 'entry/src/main/cpp'

def block(text, marker):
    start = text.index(marker)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

native = (CPP / 'bridge/napi_init.cpp').read_text()
parsing = native[native.index('    if (argc >= 10) {'):native.index('    // 向后兼容: 旧调用未传 homeDir')]
profiles = (CPP / 'wine/env_profiles.cpp').read_text()
wine_env = (CPP / 'wine/wine_env.cpp').read_text()
code = r'''
#include "graphics/graphics_profile.h"
#include "wine/env_profiles.h"
#include "wine/dll_overrides.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
using napi_value = int;
constexpr int napi_ok = 0;
int napi_get_value_bool(int, int value, bool* out) { if(value != 0 && value != 1) return 1; *out=value; return 0; }
int napi_get_value_int32(int, int value, int* out) { *out=value; return 0; }
void napi_create_int32(int, int value, int* out) { *out=value; }
struct Params { bool directNcpSession=false, desktopVulkanCompositor=false; int desktopStallSeconds=0; };
int launch(int argc, int direct, int desktop, int stall) {
 int env=0; int args[12]={}; args[9]=direct; args[10]=desktop; args[11]=stall;
 auto* p=new Params;
'''+parsing+r'''
 int result=(p->directNcpSession?1:0)|(p->desktopVulkanCompositor?2:0)|(p->desktopStallSeconds<<2);
 delete p; return result;
}
namespace winehua {
template<class... Args> std::vector<std::string> BuildWineEnv(Args&&...) {return {};}
template<class... Args> void AppendD3dBackendEnv(Args&&...) {}
template<class... Args> void AppendStableDxvkEnv(Args&&...) {}
template<class... Args> void AppendVulkanRuntimeEnv(Args&&...) {}
'''+block(wine_env, 'void UpsertEnvLine(')+'\n'+block(profiles, 'static std::string FindEnvValue(')+'\n'+block(profiles, 'std::vector<std::string> BuildSessionEnv(')+r'''
}
int main() {
 using namespace winehua;
 for(const char* profile : {"", "unknown", "product-vulkan", "isolate-vulkan-direct"}) {
  setenv("WINEHUA_GRAPHICS_PROFILE",profile,1);
  for(int direct=0;direct<2;++direct) for(int desktop=0;desktop<2;++desktop) {
   assert(launch(12,direct,desktop,0)==(direct|(desktop<<1)));
   assert(launch(12,direct,desktop,120)==(direct|(desktop<<1)|(120<<2)));
  }
  assert(launch(9,1,1,0)==0);
  assert(launch(10,1,1,0)==1);
  assert(launch(11,1,1,0)==3);
  assert(launch(12,2,0,0)==-1);
  assert(launch(12,0,2,0)==-1);
  assert(launch(12,0,0,-1)==-1);
  assert(launch(12,0,0,121)==-1);
  for(const char* backend : {"wined3d","dxvk_legacy","dxvk_modern_2_6"}) {
   SessionEnvPolicy p; p.d3dBackend=backend;
   auto defaults=BuildSessionEnv(p);
   if(!*profile || std::string(profile)=="unknown")
    assert(FindEnvValue(defaults,"WINEHUA_VULKAN_BACKEND").empty());
   for(const char* transport : {"direct","venus"}) {
    p.extraEnv={std::string("WINEHUA_VULKAN_BACKEND=")+transport,
                "WINEHUA_GRAPHICS_PROFILE=target-explicit", "WINEHUA_VK_PRECISE_MAP=1"};
    auto env=BuildSessionEnv(p);
    assert(FindEnvValue(env,"WINEHUA_VULKAN_BACKEND")==transport);
    assert(FindEnvValue(env,"WINEHUA_GRAPHICS_PROFILE")=="target-explicit");
    assert(FindEnvValue(env,"WINEHUA_VK_PRECISE_MAP")=="1");
   }
  }
 }
 unsetenv("WINEHUA_GRAPHICS_PROFILE");
 assert(launch(12,1,0,0)==1);
 SessionEnvPolicy plain; plain.d3dBackend="dxvk_legacy";
 assert(FindEnvValue(BuildSessionEnv(plain),"WINEHUA_VULKAN_BACKEND").empty());
 setenv("WINEHUA_GRAPHICS_PROFILE","isolate-vulkan-direct",1);
 assert(FindEnvValue(BuildSessionEnv(plain),"WINEHUA_VULKAN_BACKEND")=="direct");
 puts("PASS target independent launch switches, invalid/default arguments, opt-in profiles and explicit transport precedence");
}
'''
with tempfile.TemporaryDirectory(prefix='winehua-target-policy-') as folder:
    path=Path(folder)
    (path/'test.cpp').write_text(code)
    subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(CPP),str(path/'test.cpp'),str(CPP/'graphics/graphics_profile.cpp'),str(CPP/'wine/dll_overrides.cpp'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)

# The two caller-controlled presentation paths must not infer the guest driver
# from the independent desktop consumer switch.
launch=(CPP/'wine/wine_launch.cpp').read_text()
assert 'SetVulkanPresentMode(UsesVulkanD3dBackend(params.d3dBackend));' in launch
assert 'SetVulkanPresentMode(UsesVulkanD3dBackend(p->d3dBackend));' in launch
exe=(CPP/'wine/wine_exe.cpp').read_text()
assert '"WINEHUA_PRESENT_BACKEND=" + options.presentBackend' in exe
assert 'const std::string presentBackend = vulkanD3d' not in exe
assert 'MakeLaunchResult' not in exe
assert 'size_t argc = 5;' in block(exe,'napi_value RunWineExe(')
