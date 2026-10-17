#!/usr/bin/env python3
"""Check local-build identity independently of old reviewed binary hashes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dxvk_gate', ROOT/'scripts/dxvk_runtime_contract.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

class Archive:
    def __init__(self, entries): self.entries=entries
    def read(self, name): return self.entries[name]

def pe(machine, salt=b'local-toolchain-build'):
    data=bytearray(128)
    data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,64)
    data[64:68]=b'PE\0\0';struct.pack_into('<H',data,68,machine)
    return bytes(data)+b'FP32 DenormFlushToZero disabled'+salt

class Identity(unittest.TestCase):
    def setUp(self):
        pinned=gate.load_modern_lock()
        self.runtime={'commit':pinned['commit'],'sourceSha256':pinned['sourceSha256']}
        self.entries={}
        for arch in ('x86','x64','arm64x'):
            self.runtime[arch]={}
            for name in ('d3d11.dll','dxgi.dll'):
                data=pe(0x14c if arch=='x86' else 0xaa64)
                self.entries[f'dxvk/modern-2.6/{arch}/{name}']=data
                self.runtime[arch][name]=hashlib.sha256(data).hexdigest()
    def check(self):
        self.entries['dxvk/manifest.json']=json.dumps({'runtimes':{'modern-2.6':self.runtime}}).encode()
        gate.validate_modern_runtime(Archive(self.entries))
    def test_rebuilt_bytes_not_old_binary_hashes(self): self.check()
    def test_payload_tamper(self):
        self.entries['dxvk/modern-2.6/x86/d3d11.dll']+=b'tamper'
        with self.assertRaisesRegex(ValueError,'stale or unpaired'): self.check()
    def test_source_digest_mismatch(self):
        self.runtime['sourceSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source digest'): self.check()
    def test_source_commit_mismatch(self):
        self.runtime['commit']='0'*40
        with self.assertRaisesRegex(ValueError,'packaged commit'): self.check()
    def test_architecture_mismatch_even_with_matching_hash(self):
        data=pe(0x8664)
        self.entries['dxvk/modern-2.6/x86/d3d11.dll']=data
        self.runtime['x86']['d3d11.dll']=hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(ValueError,'architecture mismatch'): self.check()
    def test_alias_mismatch_even_with_matching_hash(self):
        data=pe(0xaa64,b'other-build')
        self.entries['dxvk/modern-2.6/x64/d3d11.dll']=data
        self.runtime['x64']['d3d11.dll']=hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(ValueError,'alias differs'): self.check()
    def test_required_fix_marker_missing(self):
        data=pe(0x14c).replace(b'FP32 DenormFlushToZero disabled',b'not-the-reviewed-shader-fix!!!')
        self.entries['dxvk/modern-2.6/x86/d3d11.dll']=data
        self.runtime['x86']['d3d11.dll']=hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(ValueError,'shader repair'): self.check()

if __name__=='__main__': unittest.main()
