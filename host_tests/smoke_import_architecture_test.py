#!/usr/bin/env python3
"""Import archives follow the effective compiler ISA, including explicit probes."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smoke_import_gate', ROOT/'automation/smoke.py')
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)

class ImportArchitecture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'BUILD_DIR': self.tmp.name, 'LLVM_MINGW': '/toolchain'}
        self.root = Path(self.tmp.name)/'wine-ohos-aarch64/dlls/vulkan-1'
        self.stack = patch.multiple(gate, WINE_ARCH='aarch64', WINE_BUILD_DIRNAME='wine-ohos-aarch64')
        self.stack.start(); self.addCleanup(self.stack.stop)

    def test_existing_archives(self):
        for cpu, directory in [('i686', 'i386'), ('x86_64', 'x86_64'),
                               ('aarch64', 'aarch64'), ('arm64ec', 'arm64ec')]:
            archive = self.root/(directory+'-windows')/'libvulkan-1.a'
            archive.parent.mkdir(parents=True); archive.write_bytes(b'archive')
            with patch.object(gate.subprocess, 'check_output', return_value=cpu+'-w64-mingw32') as query:
                self.assertEqual(gate.resolve_vulkan_import(self.env, 'cc', ['--target='+cpu]), archive)
                self.assertIn('--target='+cpu, query.call_args.args[0])

    def test_amd64_facade_exports(self):
        with patch.object(gate.subprocess, 'check_output', side_effect=[
                'x86_64-w64-mingw32', 'Format: COFF-ARM64X\n  Name: vkAlpha\n  ForwardedTo: winevulkan.vkAlpha\n  Name: vkBeta\n']), \
                patch.object(gate.subprocess, 'run') as run:
            archive = gate.resolve_vulkan_import(self.env, 'cc')
            definition = archive.with_name('vulkan-1.def').read_text()
            self.assertEqual(definition, 'LIBRARY vulkan-1.dll\nEXPORTS\n  vkAlpha\n  vkBeta\n')
            self.assertIn('i386:x86-64', run.call_args.args[0])
            self.assertTrue(run.call_args.kwargs['check'])

    def test_reject_unsafe_fallbacks(self):
        for outputs in [['i686-w64-mingw32'], ['riscv64-w64-mingw32'],
                        ['x86_64-w64-mingw32', 'Format: COFF-ARM64\n  Name: vkA\n'],
                        ['x86_64-w64-mingw32', 'Format: COFF-ARM64X\n  Name: vkA\n  Name: vkA\n']]:
            with self.subTest(outputs=outputs), patch.object(gate.subprocess, 'check_output', side_effect=outputs), self.assertRaises(SystemExit):
                gate.resolve_vulkan_import(self.env, 'cc')

if __name__ == '__main__': unittest.main()
