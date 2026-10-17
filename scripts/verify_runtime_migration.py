#!/usr/bin/env python3
"""Verify the WineHua capability migration without importing VPP product/UI contracts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'docs/migration/proton-runtime.lock.json'

def digest(path, normalized=False):
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b'\r\n', b'\n') if normalized else data).hexdigest()

def verify_product(lock):
    for name, expected in lock['protectedProductFiles'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Target product/UI changed: ' + name)
    for excluded in ('entry/src/main/ets/service/valueadded', 'entry/src/main/ets/service/WineEngineService.ets',
                     'entry/src/main/cpp/steam_decompress', 'entry/src/main/cpp/common/performance_monitor.cpp',
                     'scripts/steam_legacy_zstd'):
        if (ROOT / excluded).exists():
            raise ValueError('Excluded source product dependency exists: ' + excluded)
    package = (ROOT / 'scripts/package.sh').read_text()
    if 'com.vintage.pomelopro' in package or 'local device="${1:?' not in package or 'bm uninstall -n app.hackeris.winehua' not in package:
        raise ValueError('Target deployment identity or explicit device requirement changed')
    print('PASS target UI, resources, package identity and existing ArkTS interfaces unchanged')

def verify_patches(lock):
    for name, expected in lock['managedPatches'].items():
        if digest(ROOT / name, True) != expected:
            raise ValueError('Managed overlay differs from reviewed migration: ' + name)
    for directory, count in (('vkd3d-proton', 23), ('mesa', 9), ('virglrenderer', 5)):
        names = sorted(p.name for p in (ROOT / 'patches' / directory).glob('*.patch'))
        prefixes = [name.split('-', 1)[0] for name in names]
        if prefixes != [f'{n:04d}' for n in range(1, count + 1)]:
            raise ValueError('Incomplete, duplicated or unordered patch series: ' + directory)
    print('PASS overlay identities and unambiguous Mesa/VirGL/VKD3D patch order')

def verify_native_interface():
    header = (ROOT / 'entry/src/main/cpp/types/libentry/Index.d.ts').read_text()
    native = (ROOT / 'entry/src/main/cpp/bridge/napi_init.cpp').read_text()
    for name in ('launchClient', 'runWineProgram', 'captureNativePerformance', 'setHostShadowProfile'):
        if name not in header or '"' + name + '"' not in native:
            raise ValueError('Existing native API missing: ' + name)
    for fragment in ('size_t argc = 12;', 'args[5], d3dBackend', 'args[6], dxvkBackend', 'args[7], wineLang', 'argc >= 12'):
        if fragment not in native:
            raise ValueError('WineHua launch/policy compatibility missing: ' + fragment)
    if native.count('EXTERN_C_START') != 1 or native.count('EXTERN_C_END') != 1:
        raise ValueError('Native C-linkage wrapper must remain balanced')
    cmake = (ROOT / 'entry/src/main/cpp/CMakeLists.txt').read_text()
    for source in re.findall(r'^\s+([\w/.-]+\.(?:cpp|c))\s*$', cmake, re.M):
        if not (ROOT / 'entry/src/main/cpp' / source).is_file():
            raise ValueError('Native build source missing: ' + source)
    print('PASS retained native API and CMake source closure')

def verify_gitlinks(lock, index):
    if index:
        output = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--stage', 'thirdparty'], text=True)
        actual = {line.split('\t')[1]:line.split()[1] for line in output.splitlines() if line.startswith('160000 ')}
    else:
        output = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', 'HEAD', 'thirdparty/'], text=True)
        actual = {line.split('\t')[1]:line.split()[2] for line in output.splitlines() if line.startswith('160000 ')}
    for name, expected in lock['gitlinks'].items():
        if actual.get(name) != expected:
            raise ValueError(f'Gitlink mismatch: {name}: {actual.get(name)} != {expected}')
        if not (ROOT / name / '.git').exists():
            raise ValueError('Submodule not initialized: ' + name)
        checked_out = subprocess.check_output(['git', '-C', str(ROOT / name), 'rev-parse', 'HEAD'], text=True).strip()
        if checked_out != expected:
            raise ValueError('Submodule checkout mismatch: ' + name)
        staged = subprocess.check_output(['git', '-C', str(ROOT / name), 'diff', '--cached', '--name-only'], text=True).strip()
        tracked = subprocess.check_output(['git', '-C', str(ROOT / name), 'ls-files'], text=True).strip()
        if staged or not tracked:
            raise ValueError('Submodule checkout/index incomplete or altered: ' + name)
    print('PASS exact committed/index and populated submodule identities')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', action='store_true', help='Check staged gitlinks before committing')
    parser.add_argument('--product-only', action='store_true', help='Run only independent UI/API boundary gates')
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    verify_product(lock)
    verify_native_interface()
    if not args.product_only:
        verify_patches(lock)
        verify_gitlinks(lock, args.index)
