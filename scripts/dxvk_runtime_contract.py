#!/usr/bin/env python3
"""Pair locally built Modern DXVK bytes with reviewed source and generated identity."""
import argparse
import hashlib
import io
import json
import struct
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / 'docs/graphics/dxvk-runtime.lock.json'


def load_modern_lock():
    lock = json.loads(LOCK_PATH.read_text())
    expected = {a + '/' + f for a in ('arm64x', 'x64', 'x86') for f in ('d3d11.dll', 'dxgi.dll')}
    if lock.get('schemaVersion') != 1 or set(lock.get('files', {})) != expected:
        raise ValueError('Modern DXVK lock must pin all six reviewed DLLs')
    return lock


def source_digest(source):
    files = {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(source.rglob('*')) if path.is_file()}
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_modern_runtime(archive, lock=None):
    pinned = load_modern_lock()
    if lock is not None and lock['submodules']['dxvk-modern'] != pinned['commit']:
        raise ValueError('Modern DXVK source pin differs from its runtime lock')
    runtime = json.loads(archive.read('dxvk/manifest.json'))['runtimes']['modern-2.6']
    if runtime.get('commit') != pinned['commit']:
        raise ValueError('Modern DXVK packaged commit differs from the graphics lock')
    if runtime.get('sourceSha256') != pinned['sourceSha256']:
        raise ValueError('Modern DXVK packaged source digest differs from reviewed source')
    for member in pinned['files']:
        architecture, filename = Path(member).parts
        data = archive.read('dxvk/modern-2.6/' + member)
        actual = hashlib.sha256(data).hexdigest()
        if runtime.get(architecture, {}).get(filename) != actual:
            raise ValueError('stale or unpaired Modern DXVK payload: ' + member)
        if len(data) < 64 or data[:2] != b'MZ':
            raise ValueError('Modern DXVK payload is not PE: ' + member)
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        if offset + 6 > len(data) or data[offset:offset+4] != b'PE\0\0':
            raise ValueError('Modern DXVK PE header is invalid: ' + member)
        expected_machine = 0x14c if architecture == 'x86' else 0xaa64
        if struct.unpack_from('<H', data, offset+4)[0] != expected_machine:
            raise ValueError('Modern DXVK architecture mismatch: ' + member)
        if filename == 'd3d11.dll' and b'FP32 DenormFlushToZero disabled' not in data:
            raise ValueError('Modern DXVK lacks the reviewed Maleoon shader repair: ' + member)

    for filename in ('d3d11.dll', 'dxgi.dll'):
        if archive.read('dxvk/modern-2.6/x64/' + filename) != archive.read('dxvk/modern-2.6/arm64x/' + filename):
            raise ValueError('Modern DXVK compatibility alias differs: ' + filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-zip', type=Path)
    parser.add_argument('--hap', type=Path)
    args = parser.parse_args()
    if source_digest(ROOT / 'thirdparty/dxvk-modern/src') != load_modern_lock()['sourceSha256']:
        raise SystemExit('Modern DXVK source differs from the reviewed runtime')
    if args.hap:
        with ZipFile(args.hap) as hap:
            members = [n for n in hap.namelist() if n.endswith('/rawfile/wine-data.zip')]
            if len(members) != 1:
                raise ValueError('HAP must contain exactly one Wine runtime')
            with ZipFile(io.BytesIO(hap.read(members[0]))) as runtime:
                validate_modern_runtime(runtime)
    else:
        with ZipFile(args.runtime_zip or ROOT / 'entry/src/main/resources/rawfile/wine-data.zip') as runtime:
            validate_modern_runtime(runtime)
    print('Modern DXVK reviewed source, generated manifest and six packaged DLLs PASS')
